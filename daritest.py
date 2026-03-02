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

# НАСТРОЙКА CORS: Позволяет вашему сайту отправлять запросы на этот локальный сервер
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Разрешает запросы с любых доменов
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    """Проверка и скачивание обновлений из GitHub"""
    UPDATE_URL = "https://raw.githubusercontent.com/diasa-sys/kassa_updates/refs/heads/main/daritest.py"
    VERSION_URL = "https://raw.githubusercontent.com/diasa-sys/kassa_updates/refs/heads/main/version.txt"
    
    try:
        logging.info(f"--- Проверка обновлений (Версия {CURRENT_VERSION}) ---")
        response = requests.get(VERSION_URL, timeout=5)
        latest_version = response.text.strip()
        
        if latest_version > CURRENT_VERSION:
            logging.info(f"Найдена новая версия {latest_version}! Обновляюсь...")
            create_backup()
            r = requests.get(UPDATE_URL, timeout=10)
            if r.status_code == 200:
                with open(__file__, "w", encoding="utf-8") as f:
                    f.write(r.text)
                logging.info("ОБНОВЛЕНИЕ ЗАВЕРШЕНО. ПЕРЕЗАПУСТИТЕ СКРИПТ.")
                os._exit(0) 
            else:
                logging.error(f"Не удалось скачать код, ошибка: {r.status_code}")
        else:
            logging.info("У вас последняя версия программы.")
    except Exception as e:
        logging.error(f"Ошибка при связи с GitHub: {e}")

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
    """Поиск окна кассы в системе"""
    try:
        for w in Desktop(backend="uia").windows():
            if TARGET_WINDOW.lower() in (w.window_text() or "").lower(): return w
    except: return None

@app.post("/scan")
async def scan(req: Dict[Any, Any]):
    """Основной обработчик запросов на печать"""
    try:
        # Если данные пришли в POST-запросе от сайта, используем их
        if req:
            payload = json.dumps(req, ensure_ascii=False)
            logging.info("Получены актуальные данные от фронтенда")
        else:
            # Резервный тестовый payload
            payload = (
                "{\"doc_id\":\"228698\",\"items\":["
                "{\"ware_id\":\"27DBB2EE-C6E7-4D22-9F3C-7C6B03378CFA\",\"price\":1651,\"quantity\":1},"
                "{\"ware_id\":\"11475AE2-83AD-4253-80C5-44F9C1E0416E\",\"price\":3512,\"quantity\":1},"
                "{\"ware_id\":\"25077273-0DB4-4D41-8B9B-AA79EFAAFDC5\",\"price\":2337,\"quantity\":1}"
                "]}"
            )
            logging.info("Данные в запросе отсутствуют, использован тестовый payload")

        win = find_target_window()
        if not win: 
            logging.error("Окно кассы не найдено")
            return {"status": "error", "message": "Окно не найдено"}
        
        win.set_focus()
        hard_type(payload)
        return {"status": "ok"}
    except Exception as e:
        logging.exception("Ошибка в функции scan")
        return {"status": "error", "details": str(e)}

# 4. ЗАПУСК
if __name__ == "__main__":
    check_for_updates() 
    # Запуск сервера uvicorn без стандартных конфигов логов для корректной работы в фоне
    uvicorn.run(app, host="127.0.0.1", port=8000, log_config=None)
