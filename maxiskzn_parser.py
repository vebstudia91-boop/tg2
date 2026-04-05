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


async def download_images(client: TelegramClient, message: Message, post_id: str) -> list[str]:
    """Скачивает все изображения из сообщения (поддержка альбомов)."""
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    
    downloaded_files = []
    
    # Проверяем наличие медиа
    if not message.media:
        return downloaded_files
    
    # Обработка альбома фотографий (проверяем grouped_id)
    if message.grouped_id:
        # Получаем все сообщения из альбома по grouped_id
        album_messages = []
        async for msg in client.iter_messages(message.chat_id, limit=10):
            if msg.grouped_id == message.grouped_id and msg.media:
                album_messages.append(msg)
        
        # Сортируем по ID чтобы сохранить порядок
        album_messages.sort(key=lambda m: m.id)
        
        # Скачиваем все изображения из альбома
        for idx, grouped_message in enumerate(album_messages):
            filename = await _download_single_image(client, grouped_message, post_id, idx)
            if filename:
                downloaded_files.append(filename)
    else:
        # Обработка одиночного изображения
        filename = await _download_single_image(client, message, post_id, 0)
        if filename:
            downloaded_files.append(filename)
    
    return downloaded_files


async def _download_single_image(client: TelegramClient, message: Message, post_id: str, index: int) -> str | None:
    """Скачивает одно изображение из сообщения."""
    media = message.media
    if not media:
        return None
    
    file_path = None
    filename = None
    
    if hasattr(media, 'photo') and media.photo:
        ext = 'jpg'
        if index > 0:
            filename = f"{post_id}_{index}.{ext}"
        else:
            filename = f"{post_id}.{ext}"
        file_path = IMAGES_DIR / filename
        
        # Проверяем, существует ли уже файл
        if file_path.exists():
            print(f"Изображение {filename} уже существует, пропускаем скачивание")
            return filename
        
        await client.download_media(media.photo, file_path)
        return filename
    
    elif hasattr(media, 'document') and media.document:
        # Проверяем, является ли документ изображением
        if media.document.mime_type and media.document.mime_type.startswith('image/'):
            ext = media.document.mime_type.split('/')[-1]
            if ext == 'jpeg':
                ext = 'jpg'
            if index > 0:
                filename = f"{post_id}_{index}.{ext}"
            else:
                filename = f"{post_id}.{ext}"
            file_path = IMAGES_DIR / filename
            
            # Проверяем, существует ли уже файл
            if file_path.exists():
                print(f"Изображение {filename} уже существует, пропускаем скачивание")
                return filename
            
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
            "images": [],  # Теперь поддерживаем несколько изображений
            "downloaded_at": datetime.now().isoformat()
        }
        
        # Скачиваем все изображения если есть (поддержка альбомов)
        if message.media:
            image_filenames = await download_images(client, message, post_id)
            if image_filenames:
                post_data["images"] = image_filenames
                downloaded_images_count += len(image_filenames)
                print(f"Скачано изображений для поста #{post_id}: {len(image_filenames)}")
                for filename in image_filenames:
                    print(f"  - {filename}")
        
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
