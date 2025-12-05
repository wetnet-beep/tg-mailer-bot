#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ТЕЛЕГРАМ БОТ ДЛЯ РАССЫЛКИ - МНОГОПОЛЬЗОВАТЕЛЬСКАЯ ВЕРСИЯ
Каждый пользователь вводит СВОЙ номер и API данные
"""

import os
import sys
import json
import time
import random
import threading
import asyncio
from datetime import datetime
from telethon import TelegramClient
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty
import colorama
from colorama import Fore, Style

colorama.init(autoreset=True)

VERSION = "5.0"
CONFIG_FILE = "config.json"
TEMPLATES_FILE = "templates.json"
STATS_FILE = "stats.json"

class TelegramMailer:
    def __init__(self):
        self.client = None
        self.me = None
        self.chats = []
        self.all_chats = []  # Все чаты
        self.running = True
        
        self.mailing_active = False
        self.stop_mailing = False
        self.current_stats = {
            "started": None, "sent": 0, "errors": 0,
            "current_chat": None, "cycle": 0, "total_cycles": 0
        }
        
        # Загружаем настройки
        self.config = self.load_json(CONFIG_FILE, {})
        self.templates = self.load_json(TEMPLATES_FILE, [])
        self.stats = self.load_json(STATS_FILE, {
            "total_sent": 0, "total_errors": 0, "users": []
        })
    
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
    
    def print_header(self):
        os.system('clear')
        print(f"{Fore.CYAN}╔══════════════════════════════════════════════╗")
        print(f"{Fore.CYAN}║  ТЕЛЕГРАМ РАССЫЛКА v{VERSION} (ДЛЯ ВСЕХ)    ║")
        print(f"{Fore.CYAN}╚══════════════════════════════════════════════╝")
        
        if self.mailing_active:
            elapsed = ""
            if self.current_stats["started"]:
                elapsed = time.strftime("%H:%M:%S", time.gmtime(
                    time.time() - self.current_stats["started"]
                ))
            print(f"{Fore.RED}🔥 Рассылка: {self.current_stats['sent']} | Ошибок: {self.current_stats['errors']}")
            print(f"{Fore.YELLOW}⏱️ Время: {elapsed} | Цикл: {self.current_stats['cycle']}")
            print()
    
    def print_menu(self):
        print(f"\n{Fore.GREEN}=== ГЛАВНОЕ МЕНЮ ===")
        print(f"{Fore.CYAN}[1]  📋 Показать ВСЕ чаты ({len(self.all_chats)})")
        print(f"{Fore.CYAN}[2]  🔍 Поиск чатов")
        print(f"{Fore.CYAN}[3]  📤 Отправить одно сообщение")
        print(f"{Fore.CYAN}[4]  🚀 Быстрая рассылка")
        print(f"{Fore.CYAN}[5]  ♾️ Бесконечная рассылка")
        print(f"{Fore.CYAN}[6]  🛑 Остановить рассылку")
        print(f"{Fore.CYAN}[7]  📝 Шаблоны текстов")
        print(f"{Fore.CYAN}[8]  📊 Статистика")
        print(f"{Fore.CYAN}[9]  🔄 Перезагрузить чаты")
        print(f"{Fore.CYAN}[10] 👤 Сменить аккаунт")
        print(f"{Fore.CYAN}[0]  ⚙️ Настройки")
        print(f"{Fore.RED}[x]  🚪 Выход")
    
    async def setup_client(self, force_new=False):
        """Настройка клиента - каждый пользователь свои данные"""
        
        # Если уже есть сессия и не принудительная смена
        if os.path.exists("session.session") and not force_new:
            try:
                if not self.config:
                    print(f"{Fore.RED}❌ Нет сохраненных настроек")
                    return await self.setup_client(force_new=True)
                
                print(f"{Fore.YELLOW}📱 Используется сохраненная сессия...")
                self.client = TelegramClient(
                    "session",
                    int(self.config.get("api_id", 0)),
                    self.config.get("api_hash", "")
                )
                
                await self.client.connect()
                
                if not await self.client.is_user_authorized():
                    print(f"{Fore.YELLOW}Сессия устарела, нужен новый вход")
                    return await self.setup_client(force_new=True)
                
                self.me = await self.client.get_me()
                print(f"{Fore.GREEN}✅ Вход выполнен: {self.me.first_name}")
                return True
                
            except Exception as e:
                print(f"{Fore.RED}❌ Ошибка сессии: {e}")
                return await self.setup_client(force_new=True)
        
        # Новый вход
        print(f"{Fore.YELLOW}=== НОВЫЙ ПОЛЬЗОВАТЕЛЬ ===")
        print(f"{Fore.CYAN}Каждый пользователь вводит СВОИ данные!")
        
        api_id = input(f"{Fore.GREEN}1. API ID (с my.telegram.org): {Fore.WHITE}")
        api_hash = input(f"{Fore.GREEN}2. API Hash: {Fore.WHITE}")
        phone = input(f"{Fore.GREEN}3. Номер телефона (+79991234567): {Fore.WHITE}")
        
        if not api_id or not api_hash or not phone:
            print(f"{Fore.RED}❌ Все поля обязательны!")
            return False
        
        try:
            self.client = TelegramClient("session", int(api_id), api_hash)
            await self.client.connect()
            
            if not await self.client.is_user_authorized():
                print(f"{Fore.YELLOW}📲 Отправка кода на {phone}...")
                await self.client.send_code_request(phone)
                code = input(f"{Fore.GREEN}Введите код из Telegram: {Fore.WHITE}")
                await self.client.sign_in(phone, code)
            
            self.me = await self.client.get_me()
            print(f"{Fore.GREEN}✅ Успешный вход: {self.me.first_name}")
            
            # Сохраняем настройки
            self.config = {
                "api_id": api_id,
                "api_hash": api_hash,
                "phone": phone,
                "user_id": self.me.id,
                "username": self.me.username,
                "first_name": self.me.first_name,
                "setup_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            self.save_json(CONFIG_FILE, self.config)
            
            # Добавляем в статистику пользователей
            user_exists = False
            for user in self.stats.get("users", []):
                if user.get("user_id") == self.me.id:
                    user_exists = True
                    break
            
            if not user_exists:
                self.stats["users"].append({
                    "user_id": self.me.id,
                    "username": self.me.username,
                    "first_name": self.me.first_name,
                    "first_login": datetime.now().strftime("%Y-%m-%d")
                })
                self.save_json(STATS_FILE, self.stats)
            
            return True
            
        except Exception as e:
            print(f"{Fore.RED}❌ Ошибка входа: {e}")
            return False
    
    async def load_all_chats(self):
        """Загружает ВСЕ чаты пользователя"""
        if not self.client:
            print(f"{Fore.RED}❌ Нет подключения")
            return
        
        print(f"{Fore.YELLOW}⏳ Загрузка ВСЕХ чатов...")
        
        try:
            offset = 0
            limit = 200
            all_chats = []
            
            while True:
                result = await self.client(GetDialogsRequest(
                    offset_date=None,
                    offset_id=offset,
                    offset_peer=InputPeerEmpty(),
                    limit=limit,
                    hash=0
                ))
                
                if not result.chats:
                    break
                
                for chat in result.chats:
                    chat_type = "личный" if hasattr(chat, 'user') else "группа" if hasattr(chat, 'megagroup') else "канал"
                    
                    chat_info = {
                        "id": chat.id,
                        "title": getattr(chat, 'title', ''),
                        "username": getattr(chat, 'username', ''),
                        "type": chat_type,
                        "participants_count": getattr(chat, 'participants_count', 0)
                    }
                    all_chats.append(chat_info)
                
                print(f"{Fore.CYAN}Загружено: {len(all_chats)} чатов")
                
                if len(result.chats) < limit:
                    break
                
                offset = result.chats[-1].id
                await asyncio.sleep(1)  # Чтобы не спамить запросами
            
            self.all_chats = all_chats
            print(f"{Fore.GREEN}✅ Всего загружено: {len(self.all_chats)} чатов")
            
            # Сохраняем список чатов в файл
            self.save_json("all_chats.json", self.all_chats)
            
            return True
            
        except Exception as e:
            print(f"{Fore.RED}❌ Ошибка загрузки: {e}")
            return False
    
    def show_all_chats_paginated(self):
        """Показывает ВСЕ чаты с постраничным выводом"""
        if not self.all_chats:
            print(f"{Fore.YELLOW}⚠️ Чаты не загружены")
            return
        
        page_size = 30
        total_pages = (len(self.all_chats) + page_size - 1) // page_size
        current_page = 1
        
        while True:
            self.print_header()
            print(f"{Fore.CYAN}=== ВСЕ ЧАТЫ ({len(self.all_chats)}) ===")
            print(f"{Fore.YELLOW}Страница {current_page}/{total_pages}")
            print()
            
            start_idx = (current_page - 1) * page_size
            end_idx = min(start_idx + page_size, len(self.all_chats))
            
            for i in range(start_idx, end_idx):
                chat = self.all_chats[i]
                chat_num = i + 1
                
                # Формируем имя
                if chat["title"]:
                    name = chat["title"]
                elif chat["username"]:
                    name = f"@{chat['username']}"
                else:
                    name = f"Чат {chat['id']}"
                
                # Информация о чате
                type_icon = "👤" if chat["type"] == "личный" else "👥" if chat["type"] == "группа" else "📢"
                participants = f" ({chat['participants_count']} чел.)" if chat["participants_count"] > 0 else ""
                
                print(f"{Fore.CYAN}[{chat_num:4}] {type_icon} {Fore.WHITE}{name[:45]:45} {Fore.GREEN}{chat['type']}{participants}")
            
            print(f"\n{Fore.YELLOW}Навигация:")
            print(f"[n] Следующая страница  [p] Предыдущая")
            print(f"[число] Выбрать чат      [s] Поиск")
            print(f"[m] В меню")
            
            action = input(f"\n{Fore.CYAN}Выберите: {Fore.WHITE}").lower()
            
            if action == 'n' and current_page < total_pages:
                current_page += 1
            elif action == 'p' and current_page > 1:
                current_page -= 1
            elif action == 'm':
                break
            elif action == 's':
                self.search_chats()
            elif action.isdigit():
                num = int(action)
                if 1 <= num <= len(self.all_chats):
                    self.select_chat_for_action(num)
                else:
                    print(f"{Fore.RED}❌ Неверный номер")
                    time.sleep(1)
    
    def search_chats(self):
        """Поиск чатов по названию"""
        if not self.all_chats:
            print(f"{Fore.YELLOW}⚠️ Чаты не загружены")
            return
        
        self.print_header()
        print(f"{Fore.CYAN}=== ПОИСК ЧАТОВ ===")
        
        search_term = input(f"{Fore.GREEN}Введите текст для поиска: {Fore.WHITE}").lower()
        
        if not search_term:
            return
        
        found_chats = []
        for i, chat in enumerate(self.all_chats):
            search_text = (chat["title"] or "").lower() + " " + (chat["username"] or "").lower()
            if search_term in search_text:
                found_chats.append((i, chat))
        
        print(f"\n{Fore.GREEN}Найдено: {len(found_chats)} чатов\n")
        
        for idx, (original_idx, chat) in enumerate(found_chats[:50]):
            name = chat["title"] or chat["username"] or f"Чат {chat['id']}"
            print(f"{Fore.CYAN}[{original_idx + 1:4}] {Fore.WHITE}{name[:50]}")
        
        if found_chats:
            print(f"\n{Fore.YELLOW}[номер] - Выбрать чат")
            print(f"[m] - Назад")
            
            choice = input(f"{Fore.CYAN}Выбор: {Fore.WHITE}")
            if choice.isdigit():
                num = int(choice)
                if 1 <= num <= len(self.all_chats):
                    self.select_chat_for_action(num)
        
        input(f"\n{Fore.YELLOW}Нажмите Enter...")
    
    def select_chat_for_action(self, chat_num):
        """Выбор действия для конкретного чата"""
        chat_idx = chat_num - 1
        if chat_idx < 0 or chat_idx >= len(self.all_chats):
            return
        
        chat = self.all_chats[chat_idx]
        name = chat["title"] or chat["username"] or f"Чат {chat['id']}"
        
        self.print_header()
        print(f"{Fore.CYAN}=== ЧАТ: {name} ===")
        print(f"{Fore.YELLOW}ID: {chat['id']}")
        print(f"{Fore.YELLOW}Тип: {chat['type']}")
        if chat['username']:
            print(f"{Fore.YELLOW}Username: @{chat['username']}")
        
        print(f"\n{Fore.GREEN}Действия:")
        print(f"[1] Отправить сообщение")
        print(f"[2] Добавить в рассылку")
        print(f"[3] Скопировать ссылку")
        print(f"[m] Назад")
        
        choice = input(f"\n{Fore.CYAN}Выбор: {Fore.WHITE}").lower()
        
        if choice == '1':
            self.send_to_specific_chat(chat)
        elif choice == '2':
            self.add_to_mailing_list(chat)
        elif choice == '3':
            if chat['username']:
                link = f"https://t.me/{chat['username']}"
                print(f"{Fore.GREEN}📋 Ссылка: {link}")
                # В Termux можно скопировать вручную
            else:
                print(f"{Fore.YELLOW}⚠️ У этого чата нет username")
            input(f"\n{Fore.YELLOW}Нажмите Enter...")
    
    def send_to_specific_chat(self, chat):
        """Отправка сообщения в конкретный чат"""
        name = chat["title"] or chat["username"] or f"Чат {chat['id']}"
        
        print(f"\n{Fore.CYAN}Отправка в: {name}")
        
        # Выбор текста
        print(f"{Fore.YELLOW}[1] Ввести текст")
        print(f"{Fore.YELLOW}[2] Использовать шаблон")
        
        text_choice = input(f"{Fore.CYAN}Выбор: {Fore.WHITE}")
        message = ""
        
        if text_choice == '1':
            print(f"{Fore.GREEN}Введите текст (две пустые строки для завершения):")
            lines = []
            empty_lines = 0
            while empty_lines < 2:
                line = input()
                if line.strip() == "":
                    empty_lines += 1
                else:
                    empty_lines = 0
                lines.append(line)
            message = "\n".join(lines[:-2])  # Убираем две последние пустые строки
        
        elif text_choice == '2' and self.templates:
            print(f"\n{Fore.CYAN}Шаблоны:")
            for i, template in enumerate(self.templates[:10], 1):
                print(f"{Fore.GREEN}[{i}] {template[:60]}...")
            
            try:
                t_num = int(input(f"{Fore.CYAN}Выберите шаблон: {Fore.WHITE}"))
                if 1 <= t_num <= len(self.templates):
                    message = self.templates[t_num-1]
            except:
                pass
        
        if not message:
            print(f"{Fore.RED}❌ Текст не введен")
            return
                  # Подтверждение
        print(f"\n{Fore.RED}=== ПОДТВЕРЖДЕНИЕ ===")
        print(f"{Fore.YELLOW}Чат: {name}")
        print(f"{Fore.YELLOW}Текст: {message[:50]}...")
        
        confirm = input(f"\n{Fore.RED}Отправить? (y/n): {Fore.WHITE}").lower()
        
        if confirm == 'y':
            asyncio.run(self.send_message_async(chat["id"], message))
            print(f"{Fore.GREEN}✅ Сообщение отправлено!")
            
            # Обновляем статистику
            self.stats["total_sent"] += 1
            self.save_json(STATS_FILE, self.stats)
        
        input(f"\n{Fore.YELLOW}Нажмите Enter...")
    
    async def send_message_async(self, chat_id, message):
        """Асинхронная отправка сообщения"""
        try:
            await self.client.send_message(chat_id, message)
            return True
        except Exception as e:
            print(f"{Fore.RED}❌ Ошибка: {e}")
            self.stats["total_errors"] += 1
            self.save_json(STATS_FILE, self.stats)
            return False
    
    def add_to_mailing_list(self, chat):
        """Добавление чата в список для рассылки"""
        # Для простоты сохраняем в временный файл
        mailing_list = self.load_json("mailing_list.json", [])
        
        if chat["id"] not in [c["id"] for c in mailing_list]:
            mailing_list.append(chat)
            self.save_json("mailing_list.json", mailing_list)
            print(f"{Fore.GREEN}✅ Чат добавлен в список рассылки!")
        else:
            print(f"{Fore.YELLOW}⚠️ Чат уже в списке")
        
        time.sleep(1)
    
    def start_mailing(self, infinite=False):
        """Запуск рассылки с выбором чатов"""
        if self.mailing_active:
            print(f"{Fore.RED}❌ Рассылка уже запущена!")
            return
        
        self.print_header()
        print(f"{Fore.CYAN}=== НАСТРОЙКА РАССЫЛКИ ===")
        
        # Выбор чатов
        print(f"\n{Fore.YELLOW}Выберите чаты:")
        print(f"[1] Выбрать вручную")
        print(f"[2] Из списка рассылки")
        print(f"[3] Все чаты (ОСТОРОЖНО!)")
        
        choice = input(f"{Fore.CYAN}Выбор: {Fore.WHITE}")
        
        target_chats = []
        
        if choice == '1':
            self.show_all_chats_paginated()
            nums = input(f"\n{Fore.GREEN}Введите номера чатов через запятую: {Fore.WHITE}")
            try:
                for n in nums.split(','):
                    num = int(n.strip())
                    if 1 <= num <= len(self.all_chats):
                        target_chats.append(self.all_chats[num-1])
            except:
                print(f"{Fore.RED}❌ Ошибка ввода")
                return
        
        elif choice == '2':
            mailing_list = self.load_json("mailing_list.json", [])
            if not mailing_list:
                print(f"{Fore.RED}❌ Список рассылки пуст")
                return
            target_chats = mailing_list
        
        elif choice == '3':
            confirm = input(f"{Fore.RED}ВНИМАНИЕ! Отправить во ВСЕ {len(self.all_chats)} чатов? (y/n): {Fore.WHITE}").lower()
            if confirm == 'y':
                target_chats = self.all_chats
            else:
                return
        
        if not target_chats:
            print(f"{Fore.RED}❌ Не выбрано чатов")
            return
        
        # Настройки рассылки
        print(f"\n{Fore.CYAN}=== НАСТРОЙКИ ===")
        
        message = input(f"{Fore.GREEN}Текст сообщения: {Fore.WHITE}")
        if not message:
            print(f"{Fore.RED}❌ Текст обязателен")
            return
        
        delay = input(f"{Fore.GREEN}Задержка между сообщениями (сек) [2]: {Fore.WHITE}")
        delay = float(delay) if delay else 2.0
        
        if infinite:
            cycles = 0
        else:
            cycles_input = input(f"{Fore.GREEN}Количество циклов [1]: {Fore.WHITE}")
            cycles = int(cycles_input) if cycles_input else 1
        
        # Подтверждение
        print(f"\n{Fore.RED}=== ПОДТВЕРЖДЕНИЕ ===")
        print(f"{Fore.YELLOW}Чатов: {len(target_chats)}")
        print(f"{Fore.YELLOW}Задержка: {delay} сек")
        print(f"{Fore.YELLOW}Циклов: {'∞' if cycles == 0 else cycles}")
        print(f"{Fore.YELLOW}Примерное время: {len(target_chats) * delay / 60:.1f} мин")
        
        confirm = input(f"\n{Fore.RED}Начать рассылку? (y/n): {Fore.WHITE}").lower()
        
        if confirm != 'y':
            print(f"{Fore.YELLOW}❌ Отменено")
            return
        
        # Запуск
        self.mailing_active = True
        self.stop_mailing = False
        self.current_stats = {
            "started": time.time(),
            "sent": 0,
            "errors": 0,
            "current_chat": None,
            "cycle": 0,
            "total_cycles": cycles
        }
        
        thread = threading.Thread(
            target=self.mailing_worker,
            args=(target_chats, message, delay, cycles)
        )
        thread.daemon = True
        thread.start()
        
        print(f"\n{Fore.GREEN}✅ Рассылка запущена!")
        print(f"{Fore.YELLOW}Для остановки выберите пункт 6 в меню")
        time.sleep(2)
    
    def mailing_worker(self, chats, text, delay, cycles):
        """Рабочий поток для рассылки"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        current_cycle = 0
        
        try:
            while (cycles == 0 or current_cycle < cycles) and not self.stop_mailing:
                current_cycle += 1
                self.current_stats["cycle"] = current_cycle
                
                print(f"{Fore.CYAN}[Цикл {current_cycle}] Начало...")
                
                for chat in chats:
                    if self.stop_mailing:
                        break
                    
                    name = chat["title"] or chat["username"] or f"Чат {chat['id']}"
                    self.current_stats["current_chat"] = name
                    
                    try:
                        loop.run_until_complete(
                            self.client.send_message(chat["id"], text)
                        )
                        
                        self.current_stats["sent"] += 1
                        print(f"{Fore.GREEN}[✓] {name[:30]}")
                        
                    except Exception as e:
                        self.current_stats["errors"] += 1
                        print(f"{Fore.RED}[✗] {name[:30]}: {str(e)[:50]}")
                    
                    time.sleep(delay)
                
                # Пауза между циклами
                if not self.stop_mailing and (cycles == 0 or current_cycle < cycles):
                    print(f"{Fore.YELLOW}[⏸️] Пауза 5 сек...")
                    time.sleep(5)
            
            # Сохраняем статистику
            self.stats["total_sent"] += self.current_stats["sent"]
            self.stats["total_errors"] += self.current_stats["errors"]
            self.save_json(STATS_FILE, self.stats)
            
        except Exception as e:
            print(f"{Fore.RED}❌ Ошибка: {e}")
        
        finally:
            self.mailing_active = False
            print(f"{Fore.YELLOW}✅ Рассылка завершена")
    
    async def reload_chats(self):
        """Перезагрузка списка чатов"""
        print(f"{Fore.YELLOW}🔄 Перезагрузка чатов...")
        if await self.load_all_chats():
            print(f"{Fore.GREEN}✅ Чаты перезагружены: {len(self.all_chats)}")
        else:
            print(f"{Fore.RED}❌ Ошибка перезагрузки")
        time.sleep(2)
    
    async def change_account(self):
        """Смена аккаунта"""
        confirm = input(f"{Fore.RED}Сменить аккаунт? (y/n): {Fore.WHITE}").lower()
        if confirm == 'y':
            # Удаляем старую сессию
            if os.path.exists("session.session"):
                os.remove("session.session")
            if os.path.exists(CONFIG_FILE):
                os.remove(CONFIG_FILE)
            
            print(f"{Fore.YELLOW}🔄 Настройка нового аккаунта...")
            return await self.setup_client(force_new=True)
        return False
    
    async def main_loop(self):
        """Основной цикл программы"""
        try:
            # Первоначальная настройка
            if not await self.setup_client():
                print(f"{Fore.RED}❌ Не удалось подключиться")
                return
            
            # Загрузка чатов
            await self.load_all_chats()
            
            # Главное меню
            while self.running:
                self.print_header()
                self.print_menu()
                
                choice = input(f"\n{Fore.GREEN}Выберите действие: {Fore.WHITE}").lower()
                
                if choice == '1':
                    self.show_all_chats_paginated()
                elif choice == '2':
                    self.search_chats()
                elif choice == '3':
                    self.show_all_chats_paginated()
                elif choice == '4':
                    self.start_mailing(infinite=False)
                elif choice == '5':
                    self.start_mailing(infinite=True)
                elif choice == '6':
                    if self.mailing_active:
                        confirm = input(f"{Fore.RED}Остановить рассылку? (y/n): {Fore.WHITE}").lower()
                        if confirm == 'y':
                            self.stop_mailing = True
                            print(f"{Fore.GREEN}✅ Остановка...")
                            time.sleep(1)
                    else:
                        print(f"{Fore.YELLOW}⚠️ Рассылка не активна")
                        time.sleep(1)
                elif choice == '7':
                    self.manage_templates()
                elif choice == '8':
                    self.show_stats()
                elif choice == '9':
                    await self.reload_chats()
                elif choice == '10':
                    await self.change_account()
                elif choice == '0':
                    print(f"\n{Fore.YELLOW}Настройки в разработке...")
                    time.sleep(1)
                elif choice == 'x':
                    if self.mailing_active:
                        confirm = input(f"{Fore.RED}Рассылка активна! Выйти? (y/n): {Fore.WHITE}").lower()
                        if confirm != 'y':
                            continue
                    break
                
                # Пауза между действиями
                if choice not in ['x', '']:
                    input(f"\n{Fore.YELLOW}Нажмите Enter...")
        
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}⚠️ Программа прервана")
        except Exception as e:
            print(f"{Fore.RED}❌ Ошибка: {e}")
        finally:
            if self.client:
                await self.client.disconnect()
            print(f"\n{Fore.GREEN}👋 До свидания!")
    
    def manage_templates(self):
        """Управление шаблонами"""
        self.print_header()
        print(f"{Fore.CYAN}=== ШАБЛОНЫ ТЕКСТОВ ===\n")
        
        if not self.templates:
            print(f"{Fore.YELLOW}Нет сохраненных шаблонов")
        else:
            for i, template in enumerate(self.templates, 1):
                print(f"{Fore.GREEN}[{i}] {template[:70]}...")
        
        print(f"\n{Fore.YELLOW}Действия:")
        print(f"[a] Добавить шаблон")
        print(f"[d] Удалить шаблон")
        print(f"[c] Очистить все")
        print(f"[m] Назад")
        
        choice = input(f"\n{Fore.CYAN}Выбор: {Fore.WHITE}").lower()
        
        if choice == 'a':
            print(f"{Fore.GREEN}Введите текст шаблона:")
            lines = []
            while True:
                line = input()
                if line.strip() == "" and len(lines) > 0:
                    if input(f"{Fore.YELLOW}Закончить ввод? (y/n): {Fore.WHITE}").lower() == 'y':
                        break
                lines.append(line)
            
            template = "\n".join(lines)
            if template.strip():
                self.templates.append(template)
                self.save_json(TEMPLATES_FILE, self.templates)
                print(f"{Fore.GREEN}✅ Шаблон сохранен!")
        
        elif choice == 'd' and self.templates:
            try:
                num = int(input(f"{Fore.CYAN}Номер шаблона для удаления: {Fore.WHITE}"))
                if 1 <= num <= len(self.templates):
                    del self.templates[num-1]
                    self.save_json(TEMPLATES_FILE, self.templates)
                    print(f"{Fore.GREEN}✅ Шаблон удален!")
            except:
                print(f"{Fore.RED}❌ Ошибка")
        
        elif choice == 'c':
            confirm = input(f"{Fore.RED}Удалить ВСЕ шаблоны? (y/n): {Fore.WHITE}").lower()
            if confirm == 'y':
                self.templates = []
                self.save_json(TEMPLATES_FILE, self.templates)
                print(f"{Fore.GREEN}✅ Все шаблоны удалены!")
        
        time.sleep(1)
    
    def show_stats(self):
        """Показать статистику"""
        self.print_header()
        print(f"{Fore.CYAN}=== СТАТИСТИКА ===\n")
        
        print(f"{Fore.GREEN}📊 ОБЩАЯ СТАТИСТИКА:")
        print(f"{Fore.WHITE}Всего отправлено: {Fore.GREEN}{self.stats['total_sent']}")
        print(f"{Fore.WHITE}Ошибок отправки: {Fore.RED}{self.stats['total_errors']}")
        print(f"{Fore.WHITE}Загружено чатов: {Fore.CYAN}{len(self.all_chats)}")
        print(f"{Fore.WHITE}Сохранено шаблонов: {Fore.YELLOW}{len(self.templates)}")
        
        if self.stats.get("users"):
            print(f"\n{Fore.CYAN}👥 ПОЛЬЗОВАТЕЛИ:")
            for user in self.stats["users"][:5]:  # Показываем первых 5
                name = user.get("first_name", "Unknown")
                username = f"(@{user['username']})" if user.get("username") else ""
                print(f"{Fore.WHITE}• {name} {username}")
        
        if self.mailing_active:
            print(f"\n{Fore.RED}🔥 ТЕКУЩАЯ РАССЫЛКА:")
            elapsed = time.time() - self.current_stats["started"]
            print(f"{Fore.YELLOW}Отправлено: {self.current_stats['sent']}")
            print(f"{Fore.YELLOW}Ошибок: {self.current_stats['errors']}")
            print(f"{Fore.YELLOW}Время работы: {time.strftime('%H:%M:%S', time.gmtime(elapsed))}")
        
        input(f"\n{Fore.YELLOW}Нажмите Enter...")

async def main():
    bot = TelegramMailer()
    await bot.main_loop()

if __name__ == "__main__":
    asyncio.run(main())
