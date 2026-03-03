import os
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
CURRENT_VERSION = "1.1.5"
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
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# 2. ФУНКЦИИ ОБНОВЛЕНИЯ И БЭКАПА (Скорректировано под EXE)
def create_backup():
    """Создает резервную копию текущего EXE перед заменой"""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    
    current_exe = sys.executable
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    # Если запущен как скрипт, бэкапим .py, если как EXE — бэкапим EXE
    ext = ".exe" if current_exe.endswith(".exe") else ".py"
    backup_path = os.path.join(BACKUP_DIR, f"daritest_v{CURRENT_VERSION}_{timestamp}{ext}")
    
    try:
        shutil.copy2(current_exe, backup_path)
        logging.info(f"Бэкап создан: {backup_path}")
    except Exception as e:
        logging.error(f"Не удалось создать бэкап: {e}")

def check_for_updates():
    """Проверка версии и обновление EXE через вспомогательный BAT-файл"""
    EXE_UPDATE_URL = "https://github.com/diasa-sys/kassa_updates/raw/main/daritest.exe"
    VERSION_URL = "https://raw.githubusercontent.com/diasa-sys/kassa_updates/refs/heads/main/version.txt"
    
    try:
        logging.info(f"--- Проверка обновлений (Версия {CURRENT_VERSION}) ---")
        response = requests.get(VERSION_URL, timeout=5)
        latest_version = response.text.strip()
        
        if latest_version > CURRENT_VERSION:
            logging.info(f"Найдена новая версия {latest_version}! Подготовка...")
            
            create_backup()
            
            current_exe = sys.executable
            new_exe = os.path.join(os.path.dirname(current_exe), "daritest_new.exe")
            
            # Скачиваем новый файл
            r = requests.get(EXE_UPDATE_URL, timeout=30, stream=True)
            if r.status_code == 200:
                with open(new_exe, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                # Создаем BAT-скрипт для безопасной замены работающего EXE
                with open("update.bat", "w", encoding="cp866") as f:
                    f.write(f"@echo off\n")
                    f.write(f"timeout /t 3 /nobreak\n")
                    f.write(f"taskkill /f /im daritest.exe /t >nul 2>&1\n")
                    f.write(f"del /f /q \"{current_exe}\"\n")
                    f.write(f"move /y \"{new_exe}\" \"{current_exe}\"\n")
                    f.write(f"start \"\" \"{current_exe}\"\n")
                    f.write(f"del \"%~f0\"\n")

                logging.info("Обновление загружено. Запускаю замену...")
                os.startfile("update.bat")
                os._exit(0)
        else:
            logging.info("У вас актуальная версия.")
    except Exception as e:
        logging.error(f"Ошибка при обновлении: {e}")

# 3. РАБОЧИЕ ФУНКЦИИ (Твой оригинал, не трогаем)
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
        # Твой рабочий Payload (строго без изменений)
        payload = (
            "{\"doc_id\":\"238979\",\"items\":["
            "{\"ware_id\":\"BD4C72F8-C507-4ABC-B98E-B8290AF5FE41\",\"price\":9349,\"quantity\":2},"
            "{\"ware_id\":\"3E815439-17FB-4D50-B7B1-AA555A56BC97\",\"price\":840,\"quantity\":6},"
            "{\"ware_id\":\"7117019E-5A5F-441B-B6F4-53F47FFD6551\",\"price\":170,\"quantity\":5}"
            "]}"
        )
        win = find_target_window()
        if not win: return {"status": "error", "message": "Окно не найдено"}
        win.set_focus()
        hard_type(payload)
        return {"status": "ok"}
    except Exception as e:
        logging.exception("Ошибка в scan")
        return {"status": "error", "details": str(e)}

# 4. ЗАПУСК
if __name__ == "__main__":
    check_for_updates() 
    # log_config=None важен для стабильности вывода в EXE
    uvicorn.run(app, host="127.0.0.1", port=8000, log_config=None)
