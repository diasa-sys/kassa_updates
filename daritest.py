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
CURRENT_VERSION = "1.0.4"  # Обновленная версия
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

# НАСТРОЙКА CORS для интеграции с фронтендом сайта
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. ФУНКЦИИ ОБНОВЛЕНИЯ (БЕЗОПАСНАЯ ЗАМЕНА EXE)
def check_for_updates():
    """Обновление самого .exe файла через механизм временной замены"""
    # Ссылка на прямой скачивание EXE из твоего репозитория
    EXE_UPDATE_URL = "https://github.com/diasa-sys/kassa_updates/raw/main/daritest.exe"
    VERSION_URL = "https://raw.githubusercontent.com/diasa-sys/kassa_updates/refs/heads/main/version.txt"
    
    try:
        logging.info(f"--- Проверка обновлений (Версия {CURRENT_VERSION}) ---")
        response = requests.get(VERSION_URL, timeout=5)
        latest_version = response.text.strip()
        
        if latest_version > CURRENT_VERSION:
            logging.info(f"Найдена новая версия {latest_version}! Подготовка к обновлению...")
            
            current_exe = sys.executable
            new_exe = current_exe + ".new"
            
            # Скачиваем новый бинарник
            r = requests.get(EXE_UPDATE_URL, timeout=30, stream=True)
            if r.status_code == 200:
                with open(new_exe, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                logging.info("Файл скачан. Перезапуск для замены...")
                
                # Скрипт для cmd: подождать 2 сек, удалить старый, переименовать новый, запустить
                cmd_command = (
                    f"timeout /t 5 /nobreak && "
                    f"taskkill /f /im \"{os.path.basename(current_exe)}\" /t && "
                    f"del /f /q \"{current_exe}\" && "
                    f"move \"{new_exe}\" \"{current_exe}\" && "
                    f"start \"\" \"{current_exe}\""
                )
                
                # Запускаем cmd отдельно от текущего процесса
                os.spawnl(os.P_NOWAIT, "C:\\Windows\\System32\\cmd.exe", "/c", cmd_command)
                
                # Немедленный выход, чтобы разблокировать .exe для удаления
                os._exit(0)
            else:
                logging.error(f"Ошибка загрузки: {r.status_code}")
        else:
            logging.info("У вас актуальная версия.")
    except Exception as e:
        logging.error(f"Обновление прервано: {e}")

# 3. РАБОЧИЕ ФУНКЦИИ ДЛЯ КАССЫ
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

@app.post("/scan")
async def scan(req: Dict[Any, Any]):
    try:
        # Приоритет данным от фронтенда
        if req:
            payload = json.dumps(req, ensure_ascii=False)
            logging.info("Печать данных из запроса")
        else:
            payload = "{\"doc_id\":\"тест\",\"items\":[]}"
            logging.warning("Пустой запрос, ничего не печатаю")

        win = find_target_window()
        if not win: return {"status": "error", "message": "Касса не открыта"}
        
        win.set_focus()
        hard_type(payload)
        return {"status": "ok"}
    except Exception as e:
        logging.exception("Ошибка в scan")
        return {"status": "error", "details": str(e)}

# 4. ЗАПУСК
if __name__ == "__main__":
    check_for_updates() 
    uvicorn.run(app, host="127.0.0.1", port=8000, log_config=None)
