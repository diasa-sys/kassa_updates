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
CURRENT_VERSION = "1.0.2"
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

# 2. ФУНКЦИИ ОБНОВЛЕНИЯ И БЭКАПА
def create_backup():
    """Создает резервную копию текущего файла"""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_name = f"{BACKUP_DIR}/daritest_v{CURRENT_VERSION}_{timestamp}.py"
    shutil.copy(__file__, backup_name)
    logging.info(f"Бэкап успешно создан: {backup_name}")

def check_for_updates():
    """Проверяет обновления (пока в тестовом режиме)"""
    UPDATE_URL = "http://placeholder-url.com/daritest.py"
    VERSION_URL = "http://placeholder-url.com/version.txt"
    try:
        logging.info(f"--- Проверка обновлений (Версия {CURRENT_VERSION}) ---")
        # Пока мы просто имитируем, что обновлений нет (latest == current)
        latest_version = CURRENT_VERSION
        if latest_version > CURRENT_VERSION:
            logging.info(f"Найдена новая версия {latest_version}!")
            create_backup()
            # Тут будет код скачивания, когда появится ссылка
        else:
            logging.info("У вас последняя версия программы.")
    except Exception as e:
        logging.error(f"Не удалось проверить обновления: {e}")

# 3. ТВОИ РАБОЧИЕ ФУНКЦИИ ДЛЯ КАССЫ
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
        # Тот самый фрагмент, который ты правил вручную
        payload = (
            "{\"doc_id\":\"228694\",\"items\":["
            "{\"ware_id\":\"6FC6A660-AA17-4A5B-B732-112A7E580C32\",\"price\":98,\"quantity\":15},"
            "{\"ware_id\":\"37D2B27D-D2AC-4359-B760-CF250C776D7A\",\"price\":597,\"quantity\":10},"
            "{\"ware_id\":\"37D2B27D-D2AC-4359-B760-CF250C776D7A\",\"price\":545,\"quantity\":4}"
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
    check_for_updates() # Проверяем обновы ПЕРЕД запуском сервера

    uvicorn.run(app, host="127.0.0.1", port=8000)
