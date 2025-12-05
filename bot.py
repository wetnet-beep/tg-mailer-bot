#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ТЕЛЕГРАМ БОТ ДЛЯ РАССЫЛКИ v4.0
Работает от личного аккаунта (не бот-аккаунт)
Установка: bash install.sh
"""

import os
import sys
import json
import time
import random
import threading
import asyncio
from datetime import datetime
from pathlib import Path
from telethon import TelegramClient, events, errors
from telethon.tl.types import PeerUser, PeerChat, PeerChannel
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty
import colorama
from colorama import Fore, Back, Style

colorama.init(autoreset=True)

# ===================== КОНСТАНТЫ =====================
VERSION = "4.0"
CONFIG_FILE = "config.json"
FAVORITES_FILE = "favorites.json"
FOLDERS_FILE = "folders.json"
TEMPLATES_FILE = "templates.json"
STATS_FILE = "stats.json"
HISTORY_FILE = "history.json"
BLACKLIST_FILE = "blacklist.json"

# ===================== КЛАСС ДЛЯ ХРАНЕНИЯ ДАННЫХ =====================
class DataManager:
    def __init__(self):
        self.config = self.load_json(CONFIG_FILE, {
            "api_id": "",
            "api_hash": "",
            "phone": "",
            "default_delay": 2,
            "pause_between_cycles": 5,
            "language": "ru"
        })
        
        self.favorites = self.load_json(FAVORITES_FILE, [])
        self.folders = self.load_json(FOLDERS_FILE, {})
        self.templates = self.load_json(TEMPLATES_FILE, [])
        self.stats = self.load_json(STATS_FILE, {
            "total_sent": 0,
            "total_errors": 0,
            "total_chats": 0,
            "sessions": []
        })
        self.history = self.load_json(HISTORY_FILE, [])
        self.blacklist = self.load_json(BLACKLIST_FILE, [])
        
        # Текущая рассылка
        self.mailing_active = False
        self.mailing_thread = None
        self.stop_mailing = False
        self.current_stats = {
            "started": None,
            "sent": 0,
            "errors": 0,
            "current_chat": None,
            "cycle": 0,
            "total_cycles": 0
        }
    
    def load_json(self, filename, default):
        try:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            pass
        return default
    
    def save_json(self, filename, data):
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except:
            return False
    
    def save_all(self):
        self.save_json(CONFIG_FILE, self.config)
        self.save_json(FAVORITES_FILE, self.favorites)
        self.save_json(FOLDERS_FILE, self.folders)
        self.save_json(TEMPLATES_FILE, self.templates)
        self.save_json(STATS_FILE, self.stats)
        self.save_json(HISTORY_FILE, self.history)
        self.save_json(BLACKLIST_FILE, self.blacklist)
    
    def add_to_history(self, chat_name, message, status):
        self.history.append({
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "chat": chat_name,
            "message": message[:50] + "..." if len(message) > 50 else message,
            "status": status
        })
        if len(self.history) > 1000:
            self.history = self.history[-1000:]
        self.save_json(HISTORY_FILE, self.history)
    
    def update_stats(self, sent=0, errors=0):
        if sent:
            self.stats["total_sent"] += sent
        if errors:
            self.stats["total_errors"] += errors
        self.save_json(STATS_FILE, self.stats)

# ===================== ОСНОВНОЙ КЛАСС БОТА =====================
class TelegramMailer:
    def __init__(self):
        self.data = DataManager()
        self.client = None
        self.me = None
        self.chats = []
        self.running = True
        
        # Проверка наличия другого запущенного экземпляра
        self.pid_file = "bot.pid"
        self.check_running_instance()
    
    def check_running_instance(self):
        if os.path.exists(self.pid_file):
            with open(self.pid_file, 'r') as f:
                old_pid = f.read().strip()
            try:
                # Проверяем, работает ли процесс
                os.kill(int(old_pid), 0)
                print(f"{Fore.RED}⚠️ Бот уже запущен (PID: {old_pid})!")
                print(f"{Fore.YELLOW}Завершите предыдущий процесс или удалите файл bot.pid")
                sys.exit(1)
            except:
                # Процесс не существует, удаляем старый PID
                os.remove(self.pid_file)
        
        # Создаем новый PID файл
        with open(self.pid_file, 'w') as f:
            f.write(str(os.getpid()))
    
    def clean_exit(self):
        if os.path.exists(self.pid_file):
            os.remove(self.pid_file)
        self.data.save_all()
        print(f"\n{Fore.GREEN}✅ Бот завершил работу. Данные сохранены.")
        sys.exit(0)
    
    def print_header(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"{Fore.CYAN}╔══════════════════════════════════════════════╗")
        print(f"{Fore.CYAN}║    ТЕЛЕГРАМ БОТ РАССЫЛКИ v{VERSION}         ║")
        print(f"{Fore.CYAN}╚══════════════════════════════════════════════╝")
        
        if self.data.mailing_active:
            elapsed = ""
            if self.data.current_stats["started"]:
                elapsed = time.strftime("%H:%M:%S", time.gmtime(
                    time.time() - self.data.current_stats["started"]
                ))
            
            print(f"{Fore.RED}🔥 Рассылка активна: {self.data.current_stats['sent']} отправлено | "
                  f"Ошибок: {self.data.current_stats['errors']} | Время: {elapsed}")
            print(f"{Fore.YELLOW}📌 Текущий чат: {self.data.current_stats['current_chat']}")
            print(f"{Fore.MAGENTA}🔄 Цикл: {self.data.current_stats['cycle']}/{self.data.current_stats['total_cycles']}")
            print()
    
    def print_menu(self):
        menu_items = [
            ("[1]", "📋 Мои чаты"),
            ("[2]", "📤 Отправить одно сообщение"),
            ("[3]", "🚀 Обычная рассылка"),
            ("[4]", "♾️ БЕСКОНЕЧНАЯ рассылка"),
            ("[5]", "🛑 Остановить рассылку"),
            ("[6]", "📁 Папки с чатами"),
            ("[7]", "💾 Избранные чаты"),
            ("[8]", "📝 Шаблоны текстов"),
            ("[9]", "📊 Статистика"),
            ("[10]", "⚫ Черный список"),
            ("[11]", "📜 История отправки"),
            ("[0]", "⚙️ Настройки"),
            ("[x]", "🚪 Выход")
        ]
        
        for key, item in menu_items:
            print(f"{Fore.GREEN}{key:4} {Fore.WHITE}{item}")
    
    async def setup_client(self):
        """Настройка клиента Telegram"""
        if not self.data.config["api_id"] or not self.data.config["api_hash"]:
            print(f"{Fore.YELLOW}=== НАСТРОЙКА АККАУНТА ===")
            api_id = input(f"{Fore.CYAN}Введите API ID (с my.telegram.org): {Fore.WHITE}")
            api_hash = input(f"{Fore.CYAN}Введите API Hash: {Fore.WHITE}")
            phone = input(f"{Fore.CYAN}Введите номер телефона (с кодом страны): {Fore.WHITE}")
            
            self.data.config["api_id"] = api_id
            self.data.config["api_hash"] = api_hash
            self.data.config["phone"] = phone
            self.data.save_json(CONFIG_FILE, self.data.config)
        
        try:
            self.client = TelegramClient(
                "session",
                int(self.data.config["api_id"]),
                self.data.config["api_hash"]
            )
            
            await self.client.connect()
            
            if not await self.client.is_user_authorized():
                print(f"{Fore.YELLOW}Отправка кода подтверждения...")
                await self.client.send_code_request(self.data.config["phone"])
                code = input(f"{Fore.CYAN}Введите код из Telegram: {Fore.WHITE}")
                await self.client.sign_in(self.data.config["phone"], code)
            
            self.me = await self.client.get_me()
            print(f"{Fore.GREEN}✅ Успешный вход как: {self.me.first_name} (@{self.me.username})")
            
            # Загружаем чаты
            await self.load_chats()
            return True
            
        except Exception as e:
            print(f"{Fore.RED}❌ Ошибка подключения: {e}")
            return False
    
    async def load_chats(self):
        """Загрузка списка чатов/диалогов"""
        try:
            result = await self.client(GetDialogsRequest(
                offset_date=None,
                offset_id=0,
                offset_peer=InputPeerEmpty(),
                limit=200,
                hash=0
            ))
            
            self.chats = []
            for chat in result.chats:
                chat_info = {
                    "id": chat.id,
                    "title": getattr(chat, 'title', ''),
                    "username": getattr(chat, 'username', ''),
                    "type": "channel" if hasattr(chat, 'broadcast') else "group"
                }
                self.chats.append(chat_info)
            
            print(f"{Fore.GREEN}✅ Загружено чатов: {len(self.chats)}")
            
        except Exception as e:
            print(f"{Fore.RED}❌ Ошибка загрузки чатов: {e}")
            self.chats = []
    
    def show_chats(self):
        """Показать список чатов"""
        self.print_header()
        print(f"{Fore.CYAN}=== 📋 МОИ ЧАТЫ ({len(self.chats)}) ===\n")
        
        for i, chat in enumerate(self.chats[:50], 1):
            status = ""
            if chat["id"] in self.data.favorites:
                status = f"{Fore.YELLOW}★ "
            
            if chat["id"] in self.data.blacklist:
                status = f"{Fore.RED}✗ "
            
            chat_name = chat["title"] or chat["username"] or f"Чат {chat['id']}"
            print(f"{Fore.CYAN}[{i:2}] {status}{Fore.WHITE}{chat_name[:40]:40} {Fore.GREEN}{chat['type']}")
        
        if len(self.chats) > 50:
            print(f"\n{Fore.YELLOW}... и еще {len(self.chats) - 50} чатов")
        
        print(f"\n{Fore.CYAN}Действия:")
        print(f"[a] Добавить в избранное")
        print(f"[b] Добавить в черный список")
        print(f"[c] Создать папку из выбранных")
        print(f"[m] Вернуться в меню")
        
        choice = input(f"\n{Fore.CYAN}Выберите действие: {Fore.WHITE}").lower()
        
        if choice == 'a':
            self.add_to_favorites()
        elif choice == 'b':
            self.add_to_blacklist()
        elif choice == 'c':
            self.create_folder_from_selected()
    
    def add_to_favorites(self):
        """Добавить чат в избранное"""
        try:
            num = int(input(f"{Fore.CYAN}Введите номер чата: {Fore.WHITE}"))
            if 1 <= num <= len(self.chats):
                chat = self.chats[num-1]
                if chat["id"] not in self.data.favorites:
                    self.data.favorites.append(chat["id"])
                    self.data.save_json(FAVORITES_FILE, self.data.favorites)
                    print(f"{Fore.GREEN}✅ Чат добавлен в избранное!")
                else:
                    print(f"{Fore.YELLOW}⚠️ Чат уже в избранном")
            else:
                print(f"{Fore.RED}❌ Неверный номер")
        except:
            print(f"{Fore.RED}❌ Ошибка ввода")
    
    def add_to_blacklist(self):
        """Добавить чат в черный список"""
        try:
            num = int(input(f"{Fore.CYAN}Введите номер чата: {Fore.WHITE}"))
            if 1 <= num <= len(self.chats):
                chat = self.chats[num-1]
                if chat["id"] not in self.data.blacklist:
                    self.data.blacklist.append(chat["id"])
                    self.data.save_json(BLACKLIST_FILE, self.data.blacklist)
                    print(f"{Fore.GREEN}✅ Чат добавлен в черный список!")
                else:
                    print(f"{Fore.YELLOW}⚠️ Чат уже в черном списке")
            else:
                print(f"{Fore.RED}❌ Неверный номер")
        except:
            print(f"{Fore.RED}❌ Ошибка ввода")
    
    def send_single_message(self):
        """Отправка одного сообщения"""
        self.print_header()
        print(f"{Fore.CYAN}=== 📤 ОТПРАВКА ОДНОГО СООБЩЕНИЯ ===\n")
        
        # Выбор чата
        print(f"{Fore.YELLOW}Способы выбора чата:")
        print(f"[1] Из списка чатов")
        print(f"[2] По ссылке/username")
        print(f"[3] Из избранного")
        
        choice = input(f"\n{Fore.CYAN}Выберите способ: {Fore.WHITE}")
        
        chat_id = None
        chat_name = ""
        
        if choice == "1":
            self.show_chats()
            try:
                num = int(input(f"{Fore.CYAN}Введите номер чата: {Fore.WHITE}"))
                if 1 <= num <= len(self.chats):
                    chat = self.chats[num-1]
                    chat_id = chat["id"]
                    chat_name = chat["title"] or chat["username"] or str(chat["id"])
            except:
                pass
        
        elif choice == "2":
            link = input(f"{Fore.CYAN}Введите ссылку или @username: {Fore.WHITE}")
            # Здесь можно добавить логику поиска чата по ссылке
            print(f"{Fore.YELLOW}⚠️ Функция в разработке")
            return
        
        elif choice == "3":
            if not self.data.favorites:
                print(f"{Fore.RED}❌ Нет избранных чатов")
                return
            # Показать избранные чаты
            pass
        
        if not chat_id:
            print(f"{Fore.RED}❌ Чат не выбран")
            return
        
        # Выбор текста
        print(f"\n{Fore.YELLOW}Источник текста:")
        print(f"[1] Ввести текст")
        print(f"[2] Выбрать шаблон")
        
        text_choice = input(f"{Fore.CYAN}Выберите: {Fore.WHITE}")
        message_text = ""
        
        if text_choice == "1":
            print(f"{Fore.CYAN}Введите текст (Ctrl+D для завершения):")
            lines = []
            try:
                while True:
                    line = input()
                    lines.append(line)
            except EOFError:
                pass
            message_text = "\n".join(lines)
        
        elif text_choice == "2":
            if not self.data.templates:
                print(f"{Fore.RED}❌ Нет сохраненных шаблонов")
                return
            for i, template in enumerate(self.data.templates, 1):
                print(f"{Fore.CYAN}[{i}] {template[:50]}...")
            try:
                t_num = int(input(f"{Fore.CYAN}Выберите шаблон: {Fore.WHITE}"))
                if 1 <= t_num <= len(self.data.templates):
                    message_text = self.data.templates[t_num-1]
            except:
                pass
        
        if not message_text:
            print(f"{Fore.RED}❌ Текст не введен")
            return
        
        # Отправка
        print(f"\n{Fore.YELLOW}Отправляю сообщение в {chat_name}...")
        try:
            asyncio.run(self.send_message_async(chat_id, message_text))
            print(f"{Fore.GREEN}✅ Сообщение отправлено!")
            self.data.add_to_history(chat_name, message_text, "success")
            self.data.update_stats(sent=1)
        except Exception as e:
            print(f"{Fore.RED}❌ Ошибка отправки: {e}")
            self.data.add_to_history(chat_name, message_text, f"error: {e}")
            self.data.update_stats(errors=1)
    
    async def send_message_async(self, chat_id, text):
        """Асинхронная отправка сообщения"""
        try:
            await self.client.send_message(chat_id, text)
            return True
        except Exception as e:
            raise e
    
    def start_mailing(self, infinite=False):
        """Запуск рассылки"""
        if self.data.mailing_active:
            print(f"{Fore.RED}❌ Рассылка уже запущена!")
            return
        
        self.print_header()
        mode = "♾️ БЕСКОНЕЧНАЯ РАССЫЛКА" if infinite else "🚀 ОБЫЧНАЯ РАССЫЛКА"
        print(f"{Fore.CYAN}=== {mode} ===\n")
        
        # Выбор чатов
        print(f"{Fore.YELLOW}Выберите чаты для рассылки:")
        print(f"[1] Из списка чатов")
        print(f"[2] Из избранного")
        print(f"[3] Из папки")
        print(f"[4] Все чаты (кроме черного списка)")
        
        chat_choice = input(f"{Fore.CYAN}Выберите: {Fore.WHITE}")
        
        target_chats = []
        
        if chat_choice == "1":
            self.show_chats()
            nums = input(f"{Fore.CYAN}Введите номера чатов через запятую (1,3,5): {Fore.WHITE}")
            try:
                for num in nums.split(','):
                    idx = int(num.strip()) - 1
                    if 0 <= idx < len(self.chats):
                        target_chats.append(self.chats[idx])
            except:
                print(f"{Fore.RED}❌ Ошибка ввода номеров")
                return
        
        elif chat_choice == "2":
            if not self.data.favorites:
                print(f"{Fore.RED}❌ Нет избранных чатов")
                return
            # Фильтруем чаты по ID избранных
            fav_ids = set(self.data.favorites)
            target_chats = [chat for chat in self.chats if chat["id"] in fav_ids]
        
        elif chat_choice == "4":
            blacklist_ids = set(self.data.blacklist)
            target_chats = [chat for chat in self.chats if chat["id"] not in blacklist_ids]
        
        if not target_chats:
            print(f"{Fore.RED}❌ Не выбрано ни одного чата")
            return
        
        # Выбор текста
        print(f"\n{Fore.YELLOW}Введите текст сообщения (Ctrl+D для завершения):")
        lines = []
        try:
            while True:
                line = input()
                lines.append(line)
        except EOFError:
            pass
        message_text = "\n".join(lines)
        
        if not message_text:
            print(f"{Fore.RED}❌ Текст не введен")
            return
        
        # Настройки
        print(f"\n{Fore.YELLOW}Настройки рассылки:")
        
        delay = input(f"{Fore.CYAN}Задержка между сообщениями (сек) [{self.data.config['default_delay']}]: {Fore.WHITE}")
        delay = float(delay) if delay else self.data.config["default_delay"]
        
        pause = input(f"{Fore.CYAN}Пауза между циклами (сек) [{self.data.config['pause_between_cycles']}]: {Fore.WHITE}")
        pause = float(pause) if pause else self.data.config["pause_between_cycles"]
        
        if infinite:
            cycles = 0
        else:
            cycles_input = input(f"{Fore.CYAN}Количество циклов [1]: {Fore.WHITE}")
            cycles = int(cycles_input) if cycles_input else 1
        
        # Рандомизация текста
        randomize = input(f"{Fore.CYAN}Рандомизировать текст? (y/n) [n]: {Fore.WHITE}").lower()
        variants = []
        if randomize == 'y':
            print(f"{Fore.YELLOW}Введите варианты текста (пустая строка для завершения):")
            variant_count = 1
            while True:
                variant = input(f"{Fore.CYAN}Вариант {variant_count}: {Fore.WHITE}")
                if not variant:
                    break
                variants.append(variant)
                variant_count += 1
        
        # Подтверждение
        print(f"\n{Fore.RED}=== ПОДТВЕРЖДЕНИЕ РАССЫЛКИ ===")
        print(f"{Fore.YELLOW}Чатов: {len(target_chats)}")
        print(f"{Fore.YELLOW}Задержка: {delay} сек")
        print(f"{Fore.YELLOW}Пауза между циклами: {pause} сек")
        print(f"{Fore.YELLOW}Циклов: {'∞' if cycles == 0 else cycles}")
        print(f"{Fore.YELLOW}Рандомизация: {'Да' if variants else 'Нет'}")
        
        confirm = input(f"\n{Fore.RED}Начать рассылку? (y/n): {Fore.WHITE}").lower()
        
        if confirm != 'y':
print(f"{Fore.YELLOW}❌ Рассылка отменена")
            return
        
        # Запуск рассылки в отдельном потоке
        self.data.mailing_active = True
        self.data.stop_mailing = False
        self.data.current_stats = {
            "started": time.time(),
            "sent": 0,
            "errors": 0,
            "current_chat": None,
            "cycle": 0,
            "total_cycles": cycles
        }
        
        mailing_thread = threading.Thread(
            target=self.mailing_worker,
            args=(target_chats, message_text, delay, pause, cycles, variants)
        )
        mailing_thread.daemon = True
        mailing_thread.start()
        
        print(f"\n{Fore.GREEN}✅ Рассылка запущена!")
        print(f"{Fore.YELLOW}Для остановки выберите [5] в меню")
        time.sleep(2)
    
    def mailing_worker(self, chats, text, delay, pause, cycles, variants):
        """Рабочий поток для рассылки"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        current_cycle = 0
        
        try:
            while (cycles == 0 or current_cycle < cycles) and not self.data.stop_mailing:
                current_cycle += 1
                self.data.current_stats["cycle"] = current_cycle
                
                print(f"{Fore.CYAN}[Цикл {current_cycle}] Начало рассылки...")
                
                for chat in chats:
                    if self.data.stop_mailing:
                        break
                    
                    # Пропускаем чаты из черного списка
                    if chat["id"] in self.data.blacklist:
                        continue
                    
                    self.data.current_stats["current_chat"] = chat["title"] or chat["username"]
                    
                    # Выбираем текст
                    if variants:
                        message_to_send = random.choice(variants)
                    else:
                        message_to_send = text
                    
                    try:
                        # Отправка сообщения
                        loop.run_until_complete(
                            self.client.send_message(chat["id"], message_to_send)
                        )
                        
                        self.data.current_stats["sent"] += 1
                        self.data.add_to_history(
                            chat["title"] or chat["username"],
                            message_to_send,
                            "success"
                        )
                        
                        print(f"{Fore.GREEN}[+] Отправлено в {chat['title'][:20] if chat['title'] else chat['id']}")
                        
                    except Exception as e:
                        self.data.current_stats["errors"] += 1
                        print(f"{Fore.RED}[-] Ошибка в {chat['title'] if chat['title'] else chat['id']}: {e}")
                        self.data.add_to_history(
                            chat["title"] or chat["username"],
                            message_to_send,
                            f"error: {e}"
                        )
                    
                    # Задержка между сообщениями
                    if delay > 0:
                        time.sleep(delay)
                
                # Пауза между циклами
                if pause > 0 and not self.data.stop_mailing:
                    if cycles == 0 or current_cycle < cycles:
                        print(f"{Fore.YELLOW}[Пауза {pause} сек...]")
                        time.sleep(pause)
            
            # Обновляем общую статистику
            self.data.update_stats(
                sent=self.data.current_stats["sent"],
                errors=self.data.current_stats["errors"]
            )
            
        except Exception as e:
            print(f"{Fore.RED}❌ Критическая ошибка в потоке рассылки: {e}")
        
        finally:
            self.data.mailing_active = False
            self.data.current_stats["current_chat"] = None
            print(f"{Fore.YELLOW}✅ Рассылка завершена")
    
    def stop_mailing_now(self):
        """Остановка текущей рассылки"""
        if not self.data.mailing_active:
            print(f"{Fore.YELLOW}⚠️ Рассылка не активна")
            return
        
        confirm = input(f"{Fore.RED}Остановить рассылку? (y/n): {Fore.WHITE}").lower()
        if confirm == 'y':
            self.data.stop_mailing = True
            print(f"{Fore.GREEN}✅ Команда остановки отправлена...")
            time.sleep(1)
    
    def show_stats(self):
        """Показать статистику"""
        self.print_header()
        print(f"{Fore.CYAN}=== 📊 СТАТИСТИКА ===\n")
        
        stats = self.data.stats
        print(f"{Fore.GREEN}📈 ОБЩАЯ СТАТИСТИКА:")
        print(f"{Fore.WHITE}Всего отправлено: {Fore.GREEN}{stats['total_sent']}")
        print(f"{Fore.WHITE}Всего ошибок: {Fore.RED}{stats['total_errors']}")
        print(f"{Fore.WHITE}Всего чатов в базе: {Fore.CYAN}{len(self.chats)}")
        print(f"{Fore.WHITE}Избранных чатов: {Fore.YELLOW}{len(self.data.favorites)}")
        print(f"{Fore.WHITE}Шаблонов текста: {Fore.MAGENTA}{len(self.data.templates)}")
        
        if self.data.mailing_active:
            current = self.data.current_stats
            elapsed = time.time() - current["started"]
            print(f"\n{Fore.RED}🔥 ТЕКУЩАЯ РАССЫЛКА:")
            print(f"{Fore.WHITE}Отправлено: {Fore.GREEN}{current['sent']}")
            print(f"{Fore.WHITE}Ошибок: {Fore.RED}{current['errors']}")
            print(f"{Fore.WHITE}Цикл: {Fore.CYAN}{current['cycle']}/{current['total_cycles'] if current['total_cycles'] > 0 else '∞'}")
            print(f"{Fore.WHITE}Время работы: {Fore.YELLOW}{time.strftime('%H:%M:%S', time.gmtime(elapsed))}")
        
        print(f"\n{Fore.CYAN}Действия:")
        print(f"[c] Очистить статистику")
        print(f"[e] Экспорт в файл")
        print(f"[m] Вернуться")
        
        choice = input(f"\n{Fore.CYAN}Выберите: {Fore.WHITE}").lower()
        
        if choice == 'c':
            if input(f"{Fore.RED}Очистить ВСЮ статистику? (y/n): {Fore.WHITE}").lower() == 'y':
                self.data.stats = {
                    "total_sent": 0,
                    "total_errors": 0,
                    "total_chats": 0,
                    "sessions": []
                }
                self.data.save_json(STATS_FILE, self.data.stats)
                print(f"{Fore.GREEN}✅ Статистика очищена!")
    
    def manage_templates(self):
        """Управление шаблонами текстов"""
        self.print_header()
        print(f"{Fore.CYAN}=== 📝 ШАБЛОНЫ ТЕКСТОВ ===\n")
        
        if not self.data.templates:
            print(f"{Fore.YELLOW}Нет сохраненных шаблонов")
        else:
            for i, template in enumerate(self.data.templates, 1):
                print(f"{Fore.CYAN}[{i}] {template[:60]}...")
        
        print(f"\n{Fore.CYAN}Действия:")
        print(f"[a] Добавить шаблон")
        print(f"[d] Удалить шаблон")
        print(f"[e] Экспорт шаблонов")
        print(f"[m] Вернуться")
        
        choice = input(f"\n{Fore.CYAN}Выберите: {Fore.WHITE}").lower()
        
        if choice == 'a':
            print(f"{Fore.CYAN}Введите текст шаблона (Ctrl+D для завершения):")
            lines = []
            try:
                while True:
                    line = input()
                    lines.append(line)
            except EOFError:
                pass
            template_text = "\n".join(lines)
            
            if template_text:
                self.data.templates.append(template_text)
                self.data.save_json(TEMPLATES_FILE, self.data.templates)
                print(f"{Fore.GREEN}✅ Шаблон сохранен!")
        
        elif choice == 'd' and self.data.templates:
            try:
                num = int(input(f"{Fore.CYAN}Введите номер шаблона для удаления: {Fore.WHITE}"))
                if 1 <= num <= len(self.data.templates):
                    del self.data.templates[num-1]
                    self.data.save_json(TEMPLATES_FILE, self.data.templates)
                    print(f"{Fore.GREEN}✅ Шаблон удален!")
            except:
                print(f"{Fore.RED}❌ Ошибка ввода")
    
    def settings_menu(self):
        """Меню настроек"""
        self.print_header()
        print(f"{Fore.CYAN}=== ⚙️ НАСТРОЙКИ ===\n")
        
        config = self.data.config
        print(f"{Fore.YELLOW}ТЕКУЩИЕ НАСТРОЙКИ:")
        print(f"{Fore.WHITE}1. API ID: {Fore.GREEN}{config['api_id']}")
        print(f"{Fore.WHITE}2. API Hash: {Fore.GREEN}{config['api_hash'][:10]}...")
        print(f"{Fore.WHITE}3. Номер телефона: {Fore.GREEN}{config['phone']}")
        print(f"{Fore.WHITE}4. Задержка по умолчанию: {Fore.CYAN}{config['default_delay']} сек")
        print(f"{Fore.WHITE}5. Пауза между циклами: {Fore.CYAN}{config['pause_between_cycles']} сек")
        print(f"{Fore.WHITE}6. Язык: {Fore.MAGENTA}{config['language']}")
        
        print(f"\n{Fore.CYAN}Действия:")
        print(f"[1] Изменить задержку")
        print(f"[2] Изменить язык")
        print(f"[3] Сбросить настройки")
        print(f"[4] Экспорт всех данных")
        print(f"[5] Импорт данных")
        print(f"[m] Вернуться")
        
        choice = input(f"\n{Fore.CYAN}Выберите: {Fore.WHITE}").lower()
        
        if choice == '1':
            try:
                delay = float(input(f"{Fore.CYAN}Новая задержка (сек): {Fore.WHITE}"))
                if 0.5 <= delay <= 60:
                    config['default_delay'] = delay
                    self.data.save_json(CONFIG_FILE, config)
                    print(f"{Fore.GREEN}✅ Задержка изменена!")
                else:
                    print(f"{Fore.RED}❌ Задержка должна быть от 0.5 до 60 секунд")
            except:
                print(f"{Fore.RED}❌ Ошибка ввода")
        
        elif choice == '3':
            if input(f"{Fore.RED}Сбросить ВСЕ настройки? (y/n): {Fore.WHITE}").lower() == 'y':
                os.remove(CONFIG_FILE) if os.path.exists(CONFIG_FILE) else None
                print(f"{Fore.GREEN}✅ Настройки сброшены. Перезапустите бота.")
                time.sleep(2)
                self.clean_exit()
    
    def create_folder_from_selected(self):
        """Создание папки из выбранных чатов"""
        print(f"{Fore.CYAN}=== 📁 СОЗДАНИЕ ПАПКИ ===\n")
        
        folder_name = input(f"{Fore.CYAN}Введите название папки: {Fore.WHITE}")
        if not folder_name:
            return
        
        print(f"{Fore.YELLOW}Введите номера чатов через запятую:")
        self.show_chats()
        nums = input(f"{Fore.CYAN}Номера: {Fore.WHITE}")
        
        chat_ids = []
        try:
            for num in nums.split(','):
                idx = int(num.strip()) - 1
                if 0 <= idx < len(self.chats):
                    chat_ids.append(self.chats[idx]["id"])
        except:
            print(f"{Fore.RED}❌ Ошибка ввода")
            return
        
        if chat_ids:
            self.data.folders[folder_name] = chat_ids
            self.data.save_json(FOLDERS_FILE, self.data.folders)
            print(f"{Fore.GREEN}✅ Папка '{folder_name}' создана!")
        else:
            print(f"{Fore.RED}❌ Не выбрано ни одного чата")
    
    async def main_menu(self):
        """Главное меню"""
        while self.running:
            self.print_header()
            self.print_menu()
            
            choice = input(f"\n{Fore.CYAN}Выберите пункт меню: {Fore.WHITE}").lower()
            
            if choice == '1':
                self.show_chats()
            elif choice == '2':
                self.send_single_message()
            elif choice == '3':
                self.start_mailing(infinite=False)
            elif choice == '4':
                self.start_mailing(infinite=True)
            elif choice == '5':
                self.stop_mailing_now()
            elif choice == '7':
                self.show_chats()  # Избранные показываются в общем списке
            elif choice == '8':
                self.manage_templates()
            elif choice == '9':
                self.show_stats()
            elif choice == '0':
                self.settings_menu()
            elif choice == 'x':
                if self.data.mailing_active:
                    if input(f"{Fore.RED}Рассылка активна! Все равно выйти? (y/n): {Fore.WHITE}").lower() == 'y':
                        self.data.stop_mailing = True
                        print(f"{Fore.YELLOW}Завершаю...")
                        time.sleep(2)
                        break
                else:
                    break
            
            # Пауза для чтения сообщений
            if choice not in ['x', '']:
                input(f"\n{Fore.YELLOW}Нажмите Enter для продолжения...")
    
    async def run(self):
        """Основной запуск"""
        try:
            print(f"{Fore.CYAN}Инициализация Telegram клиента...")
            
            if await self.setup_client():
                print(f"{Fore.GREEN}✅ Бот готов к работе!")
                time.sleep(1)
                
                await self.main_menu()
            else:
                print(f"{Fore.RED}❌ Не удалось подключиться к Telegram")
                
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}⚠️ Прервано пользователем")
            
        except Exception as e:
            print(f"{Fore.RED}❌ Критическая ошибка: {e}")
            
        finally:
            if self.client:
                await self.client.disconnect()
            self.clean_exit()

# ===================== ЗАПУСК ПРОГРАММЫ =====================
if __name__ == "__main__":
    bot = TelegramMailer()
    
    try:
        # Запускаем асинхронную основную функцию
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}👋 Завершение работы...")
        if os.path.exists(bot.pid_file):
            os.remove(bot.pid_file)
