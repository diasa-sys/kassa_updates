import os
import json
import sys
import shutil
import logging
import requests
import time
import uvicorn
import ctypes
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pywinauto import Desktop
from typing import Dict, Any

# 1. НАСТРОЙКИ И ЛОГИРОВАНИЕ
CURRENT_VERSION = "1.0.4" 
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

# НАСТРОЙКА CORS: Чтобы сайт мог слать запросы на localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. ФУНКЦИИ ОБНОВЛЕНИЯ (ЗАМЕНА EXE ЧЕРЕЗ CMD)
def check_for_updates():
    """Проверяет версию и скачивает новый EXE, если он появился"""
    EXE_UPDATE_URL = "https://github.com/diasa-sys/kassa_updates/raw/main/daritest.exe"
    VERSION_URL = "https://raw.githubusercontent.com/diasa-sys/kassa_updates/refs/heads/main/version.txt"
    
    try:
        logging.info(f"--- Проверка обновлений (Версия {CURRENT_VERSION}) ---")
        response = requests.get(VERSION_URL, timeout=5)
        latest_version = response.text.strip()
        
        if latest_version > CURRENT_VERSION:
            logging.info(f"Найдена новая версия {latest_version}! Скачиваю EXE...")
            
            current_exe = sys.executable
            new_exe = current_exe + ".new"
            
            r = requests.get(EXE_UPDATE_URL, timeout=30, stream=True)
            if r.status_code == 200:
                with open(new_exe, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                logging.info("Файл скачан. Запуск процесса самозамены...")
                
                # Команда для CMD: подождать, удалить старый, переименовать новый, запустить снова
                cmd_command = (
                    f"timeout /t 2 /nobreak && "
                    f"del /f /q \"{current_exe}\" && "
                    f"move \"{new_exe}\" \"{current_exe}\" && "
                    f"start \"\" \"{current_exe}\""
                )
                
                os.spawnl(os.P_NOWAIT, "C:\\Windows\\System32\\cmd.exe", "/c", cmd_command)
                os._exit(0)
            else:
                logging.error(f"Не удалось скачать обновление: {r.status_code}")
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

# 4. API ЭНДПОИНТЫ
@app.post("/scan")
async def scan(req: Dict[Any, Any]):
    try:
        if req:
            payload = json.dumps(req, ensure_ascii=False)
            logging.info("Получен JSON от фронтенда")
        else:
            # Заглушка, если пришел пустой запрос
            payload = "{\"doc_id\":\"TEST-000\",\"items\":[]}"
            logging.warning("Пустой запрос. Печатаю тестовый заголовок.")

        win = find_target_window()
        if not win: 
            return {"status": "error", "message": "Окно кассы не найдено. Откройте программу Касса v2."}
        
        win.set_focus()
        hard_type(payload)
        return {"status": "ok", "message": "Данные успешно отправлены в кассу"}
    except Exception as e:
        logging.exception("Критическая ошибка в методе scan")
        return {"status": "error", "details": str(e)}

# 5. ТОЧКА ВХОДА
if __name__ == "__main__":
    check_for_updates() 
    uvicorn.run(app, host="127.0.0.1", port=8000, log_config=None)
