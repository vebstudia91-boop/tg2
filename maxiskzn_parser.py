#!/usr/bin/env python3
"""
Скрипт для парсинга постов из Telegram канала @MaxisKzn
Сохраняет посты в JSON и скачивает картинки.
Проверяет дубликаты по ID поста.

Требования:
    pip install telethon aiohttp

Настройка:
    Замените API_ID и API_HASH на ваши значения от https://my.telegram.org/
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

from telethon import TelegramClient
from telethon.tl.types import Message, Channel

# ==================== НАСТРОЙКИ ====================
API_ID = 12345678  # Замените на ваш API_ID
API_HASH = "your_api_hash_here"  # Замените на ваш API_HASH
CHANNEL_USERNAME = "@MaxisKzn"  # Канал для парсинга

# Папки для сохранения (в той же директории, где физически лежит скрипт)
SCRIPT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = SCRIPT_DIR / "maxiskzn_data"
POSTS_JSON = DATA_DIR / "posts.json"
IMAGES_DIR = DATA_DIR / "images"

# Создаем сессию клиента
SESSION_NAME = "maxiskzn_session"


async def load_existing_posts() -> dict:
    """Загружает существующие посты из JSON файла."""
    if POSTS_JSON.exists():
        with open(POSTS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_posts(posts: dict):
    """Сохраняет посты в JSON файл."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(POSTS_JSON, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)


async def download_image(client: TelegramClient, message: Message, post_id: str) -> str | None:
    """Скачивает изображение из сообщения."""
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    
    media = message.media
    if not media:
        return None
    
    # Проверяем наличие фото или документа с изображением
    file_path = None
    
    if hasattr(media, 'photo') and media.photo:
        filename = f"{post_id}.jpg"
        file_path = IMAGES_DIR / filename
        await client.download_media(media.photo, file_path)
        return filename
    elif hasattr(media, 'document') and media.document:
        # Проверяем, является ли документ изображением
        if media.document.mime_type and media.document.mime_type.startswith('image/'):
            ext = media.document.mime_type.split('/')[-1]
            if ext == 'jpeg':
                ext = 'jpg'
            filename = f"{post_id}.{ext}"
            file_path = IMAGES_DIR / filename
            await client.download_media(media.document, file_path)
            return filename
    
    return None


async def main():
    """Основная функция парсинга."""
    print(f"Подключение к Telegram...")
    
    # Создаем клиент
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    
    await client.start()
    print("Клиент запущен!")
    
    # Получаем информацию о канале
    try:
        channel = await client.get_entity(CHANNEL_USERNAME)
        print(f"Канал найден: {channel.title}")
    except Exception as e:
        print(f"Ошибка получения канала: {e}")
        await client.disconnect()
        return
    
    # Загружаем существующие посты
    existing_posts = await load_existing_posts()
    print(f"Загружено {len(existing_posts)} существующих постов")
    
    # Счетчики
    new_posts_count = 0
    downloaded_images_count = 0
    MAX_NEW_POSTS = 10  # Лимит на количество новых постов за один запуск
    
    # Получаем последние посты (последние 100)
    print("Получение постов...")
    
    async for message in client.iter_messages(channel, limit=100):
        # Останавливаемся если достигли лимита новых постов
        if new_posts_count >= MAX_NEW_POSTS:
            print(f"Достигнут лимит новых постов ({MAX_NEW_POSTS})")
            break
            
        post_id = str(message.id)
        
        # Пропускаем если пост уже есть (проверка на дубликаты)
        if post_id in existing_posts:
            print(f"Пост #{post_id} уже загружен, пропускаем...")
            continue
        
        # Извлекаем данные поста
        post_data = {
            "id": post_id,
            "date": message.date.isoformat() if message.date else None,
            "text": message.text or "",
            "views": message.views if hasattr(message, 'views') else None,
            "forwards": message.forwards if hasattr(message, 'forwards') else None,
            "image": None,
            "downloaded_at": datetime.now().isoformat()
        }
        
        # Скачиваем изображение если есть
        if message.media:
            image_filename = await download_image(client, message, post_id)
            if image_filename:
                post_data["image"] = image_filename
                downloaded_images_count += 1
                print(f"Скачано изображение: {image_filename}")
        
        # Сохраняем пост
        existing_posts[post_id] = post_data
        new_posts_count += 1
        print(f"Добавлен пост #{post_id} от {post_data['date']}")
        
        # Сохраняем после каждого нового поста (для надежности)
        save_posts(existing_posts)
    
    print("\n" + "="*50)
    print(f"Готово!")
    print(f"Новых постов: {new_posts_count}")
    print(f"Скачано изображений: {downloaded_images_count}")
    print(f"Всего постов в базе: {len(existing_posts)}")
    print(f"JSON файл: {POSTS_JSON.absolute()}")
    print(f"Папка с изображениями: {IMAGES_DIR.absolute()}")
    print("="*50)
    
    await client.disconnect()


if __name__ == "__main__":
    # Проверяем настройки
    if API_ID == 12345678 or API_HASH == "your_api_hash_here":
        print("ОШИБКА: Необходимо настроить API_ID и API_HASH!")
        print("Получите их на https://my.telegram.org/")
        print("Откройте скрипт и замените значения в разделе НАСТРОЙКИ")
        exit(1)
    
    asyncio.run(main())
