import os
import json
import sys
import shutil
import logging
import requests
import time
import uvicorn
import asyncio
import ctypes
import subprocess
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pywinauto import Desktop
from typing import Dict, Any

# 1. НАСТРОЙКИ И ЛОГИРОВАНИЕ
CURRENT_VERSION = "1.1.0"  # Финальная версия для теста
BACKUP_DIR = "backups"
TARGET_WINDOW = "Касса v2."
TYPE_SUFFIX = "\r"
TYPE_DELAY = 0.0008

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("daritest.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

app = FastAPI()

# Глобальный замок для предотвращения одновременной печати
scan_lock = asyncio.Lock()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. ФУНКЦИИ ОБНОВЛЕНИЯ И БЭКАПА
def check_for_updates():
    """Проверяет версию, делает бэкап и обновляет EXE"""
    EXE_UPDATE_URL = "https://github.com/diasa-sys/kassa_updates/raw/main/daritest.exe"
    VERSION_URL = "https://raw.githubusercontent.com/diasa-sys/kassa_updates/refs/heads/main/version.txt"
    
    try:
        logging.info(f"--- Проверка обновлений (Версия {CURRENT_VERSION}) ---")
        response = requests.get(VERSION_URL, timeout=5)
        latest_version = response.text.strip()
        
        if latest_version > CURRENT_VERSION:
            logging.info(f"Найдена новая версия {latest_version}! Подготовка...")
            
            current_exe = sys.executable
            new_exe = os.path.join(os.path.dirname(current_exe), "daritest_new.exe")

            # СОЗДАНИЕ БЭКАПА ПЕРЕД ОБНОВЛЕНИЕМ
            if not os.path.exists(BACKUP_DIR):
                os.makedirs(BACKUP_DIR)
            backup_path = os.path.join(BACKUP_DIR, f"daritest_v{CURRENT_VERSION}.exe")
            shutil.copy2(current_exe, backup_path)
            logging.info(f"Бэкап создан: {backup_path}")
            
            # СКАЧИВАНИЕ
            r = requests.get(EXE_UPDATE_URL, timeout=30, stream=True)
            if r.status_code == 200:
                with open(new_exe, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                logging.info("Создаю скрипт обновления update.bat...")
                
                # Создаем вспомогательный файл для замены EXE
                with open("update.bat", "w", encoding="cp866") as f:
                    f.write(f"@echo off\n")
                    f.write(f"timeout /t 5 /nobreak\n")
                    f.write(f"taskkill /f /im daritest.exe /t >nul 2>&1\n")
                    f.write(f"del /f /q \"{current_exe}\"\n")
                    f.write(f"move /y \"{new_exe}\" \"{current_exe}\"\n")
                    f.write(f"start \"\" \"{current_exe}\"\n")
                    f.write(f"del \"%~f0\"\n")

                logging.info("Запускаю скрипт и выхожу...")
                os.startfile("update.bat")
                os._exit(0)
            else:
                logging.error(f"Ошибка загрузки: {r.status_code}")
        else:
            logging.info("У вас актуальная версия.")
    except Exception as e:
        logging.error(f"Ошибка при обновлении: {e}")

# 3. ЭМУЛЯЦИЯ КЛАВИАТУРЫ
user32 = ctypes.WinDLL("user32", use_last_error=True)

def _press_vk(vk):
    scan = user32.MapVirtualKeyW(vk, 0) & 0xFF
    user32.keybd_event(vk, scan, 0, 0)
    user32.keybd_event(vk, scan, 2, 0)

def _send_char(ch):
    v = user32.VkKeyScanW(ord(ch))
    if v == -1: return
    vk = v & 0xFF
    if (v >> 8) & 0x01: user32.keybd_event(0x10, 0, 0, 0)
    _press_vk(vk)
    if (v >> 8) & 0x01: user32.keybd_event(0x10, 0, 2, 0)

def hard_type(text, suffix=TYPE_SUFFIX, delay=TYPE_DELAY):
    for ch in text:
        _send_char(ch)
        if delay: time.sleep(delay)
    if suffix == "\r": _press_vk(0x0D)

def find_target_window():
    try:
        for w in Desktop(backend="uia").windows():
            if TARGET_WINDOW.lower() in (w.window_text() or "").lower(): return w
    except: return None

# 4. API
# 4. API (Модернизирован под структуру Go)
from pydantic import BaseModel
from typing import List, Optional

# Описание структуры товара (Product из Go)
class Product(BaseModel):
    ware_id: str
    name: str
    quantity: int
    price: float

# Основная структура запроса (confirmOrderRequestSoft из Go)
class OrderRequest(BaseModel):
    phone: str
    confirm_code: Optional[str] = None
    bonus_used: bool
    doc_id: str
    source_code: str
    items: List[Product]
    client_bonus_debit: float
    client_bonus_credit: float
    pharmacist_bonus_credit: float

@app.post("/scan")
async def scan(req: OrderRequest): # Теперь Swagger будет знать точную структуру
    async with scan_lock: 
        try:
            # Превращаем модель обратно в словарь и затем в JSON для кассы
            req_dict = req.dict()
            payload = json.dumps(req_dict, ensure_ascii=False)
            
            win = find_target_window()
            if not win:
                return {"status": "error", "message": "Касса не активна"}

            win.set_focus()
            
            # Печатаем JSON с твоими 3 товарами и бонусами
            hard_type(payload)
            
            log_msg = f"Чек {req.doc_id} отправлен. Бонусы: {req.bonus_used}"
            logging.info(log_msg)
            
            return {"status": "ok", "doc_id": req.doc_id}

        except Exception as e:
            logging.exception("Ошибка при вводе данных в кассу")
            return {"status": "error", "details": str(e)}

if __name__ == "__main__":
    check_for_updates() 
    uvicorn.run(app, host="127.0.0.1", port=8000, log_config=None)
