import os
import logging
import sqlite3
import threading
import time
import random
import requests
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import telebot
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHANNEL_ID = os.getenv('CHANNEL_ID')
ADMIN_ID = os.getenv('ADMIN_ID')

bot = telebot.TeleBot(BOT_TOKEN)

# SQLite настройки
def adapt_datetime(dt):
    return dt.isoformat()

def convert_datetime(text):
    return datetime.fromisoformat(text.decode())

sqlite3.register_adapter(datetime, adapt_datetime)
sqlite3.register_converter("DATETIME", convert_datetime)

class DatabaseManager:
    def __init__(self):
        self.init_db()
    
    def init_db(self):
        """Инициализация базы данных"""
        conn = sqlite3.connect('posts.db', detect_types=sqlite3.PARSE_DECLTYPES)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scheduled_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_text TEXT,
                scheduled_time DATETIME,
                is_published BOOLEAN DEFAULT FALSE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")

    def save_scheduled_post(self, message_text, scheduled_time):
        """Сохраняет пост в базу данных"""
        conn = sqlite3.connect('posts.db', detect_types=sqlite3.PARSE_DECLTYPES)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO scheduled_posts (message_text, scheduled_time)
            VALUES (?, ?)
        ''', (message_text, scheduled_time))
        conn.commit()
        post_id = cursor.lastrowid
        conn.close()
        return post_id
    
    def get_pending_posts(self):
        """Получает неопубликованные посты"""
        try:
            conn = sqlite3.connect('posts.db', detect_types=sqlite3.PARSE_DECLTYPES)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, message_text, scheduled_time 
                FROM scheduled_posts 
                WHERE is_published = FALSE
                ORDER BY scheduled_time
            ''')
            posts = cursor.fetchall()
            conn.close()
        
            # ВОТ КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: не фильтруем по времени здесь
            # Фильтрацию делаем в publish_scheduled_posts
            return posts
        
        except Exception as e:
            logger.error(f"❌ Ошибка получения постов: {e}")
            return []
        
        except Exception as e:
            logger.error(f"❌ Ошибка получения постов: {e}")
            return []

    @bot.message_handler(commands=['debug_posts'])
    def debug_posts_command(message):
        """Отладочная информация о постах"""
        if str(message.from_user.id) != ADMIN_ID:
            bot.reply_to(message, "⛔ Нет прав!")
            return

        try:
            conn = sqlite3.connect('posts.db', detect_types=sqlite3.PARSE_DECLTYPES)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, message_text, scheduled_time, is_published, created_at
                FROM scheduled_posts 
                ORDER BY scheduled_time
            ''')
            all_posts = cursor.fetchall()
            conn.close()
        
            now = datetime.now()
            response = f"🐛 ОТЛАДКА ПОСТОВ (всего: {len(all_posts)})\n"
            response += f"⏰ Текущее время: {now.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
            for post in all_posts:
                post_id, text, post_time, is_published, created_at = post
                time_str = post_time.strftime('%Y-%m-%d %H:%M:%S')
                time_left = (post_time - now).total_seconds()
            
                status = "✅ ОПУБЛИКОВАН" if is_published else f"⏳ Ожидает ({int(time_left)} сек)"
                response += f"🆔 {post_id} | {status}\n"
                response += f"📅 {time_str}\n"
                response += f"📝 {text[:30]}...\n"
                response += "─" * 40 + "\n"
        
        # Принудительно запускаем проверку
            publish_scheduled_posts()
        
            bot.reply_to(message, response)
        
        except Exception as e:
            bot.reply_to(message, f"❌ Ошибка отладки: {e}")
    
    def mark_as_published(self, post_id):
        """Отмечает пост как опубликованный"""
        conn = sqlite3.connect('posts.db', detect_types=sqlite3.PARSE_DECLTYPES)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE scheduled_posts 
            SET is_published = TRUE 
            WHERE id = ?
        ''', (post_id,))
        conn.commit()
        conn.close()

# Инициализация БД
db = DatabaseManager()

def publish_scheduled_posts():
    """Публикует запланированные посты"""
    try:
        posts = db.get_pending_posts()
        now = datetime.now()
        
        logger.info(f"🔍 Проверка постов... Найдено: {len(posts)}")
        
        published_count = 0
        for post in posts:
            post_id, message_text, scheduled_time = post
            
            time_left = (scheduled_time - now).total_seconds()
            logger.info(f"📋 Пост {post_id}: запланирован на {scheduled_time}, осталось {time_left:.0f} сек")
            
            # Публикуем если время наступило ИЛИ прошло
            if time_left <= 0:
                try:
                    logger.info(f"🚀 Публикую пост {post_id}: {message_text[:50]}...")
                    bot.send_message(CHANNEL_ID, message_text)
                    db.mark_as_published(post_id)
                    published_count += 1
                    logger.info(f"✅ Успешно опубликован пост ID: {post_id}")
                    
                    # Пауза между публикациями
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка публикации поста {post_id}: {e}")
        
        if published_count > 0:
            logger.info(f"📤 Опубликовано {published_count} постов")
        else:
            logger.info("⏳ Нет постов для публикации")
                
    except Exception as e:
        logger.error(f"❌ Ошибка в publish_scheduled_posts: {e}")

def post_scheduler():
    """Планировщик постов"""
    logger.info("🕒 Запущен планировщик постов...")
    
    while True:
        try:
            publish_scheduled_posts()
            time.sleep(30)  # Проверяем каждые 30 секунд
            
        except Exception as e:
            logger.error(f"💥 Ошибка в планировщике: {e}")
            time.sleep(30)

@bot.message_handler(commands=['start'])
def start_command(message):
    """Команда start"""
    if str(message.from_user.id) != ADMIN_ID:
        bot.reply_to(message, "⛔ Нет прав!")
        return
    
    bot.reply_to(message,
        "🤖 Бот для управления каналом запущен!\n\n"
        "Команды:\n"
        "/post_now текст - опубликовать сейчас\n"
        "/schedule \"текст\" 2024-01-15 15:00 - запланировать\n"
        "/list_posts - список постов\n"
        "/help - справка\n\n"
        "Примеры:\n"
        "/post_now Привет мир!\n"
        '/schedule "Важное сообщение" 2024-01-15 15:30'
    )

@bot.message_handler(commands=['post_now'])
def post_now_command(message):
    """Немедленная публикация поста"""
    if str(message.from_user.id) != ADMIN_ID:
        bot.reply_to(message, "⛔ Нет прав!")
        return

    text = message.text.replace('/post_now', '').strip()
    
    if not text:
        bot.reply_to(message, 'Использование: /post_now Текст поста')
        return

    try:
        bot.send_message(CHANNEL_ID, text)
        bot.reply_to(message, "✅ Пост опубликован в канал!")
        logger.info(f"Опубликован пост: {text[:50]}...")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")
        logger.error(f"Ошибка в post_now: {e}")

@bot.message_handler(commands=['schedule'])
def schedule_command(message):
    """Планирование поста"""
    if str(message.from_user.id) != ADMIN_ID:
        bot.reply_to(message, "⛔ Нет прав!")
        return

    full_text = message.text.strip()
    logger.info(f"📨 Получена команда: {full_text}")
    
    if len(full_text) <= len('/schedule'):
        bot.reply_to(message, 
            'Использование: /schedule "Текст поста" ГГГГ-ММ-ДД ЧЧ:ММ\n\n'
            'Примеры:\n'
            '/schedule "Привет мир" 2024-01-15 15:30\n'
            '/schedule "Важное объявление" 2024-01-15 16:00'
        )
        return

    try:
        command_rest = full_text[len('/schedule'):].strip()
        
        if command_rest.startswith('"'):
            parts = command_rest.split('"', 2)
            if len(parts) < 3:
                bot.reply_to(message, "❌ Используйте кавычки для текста: /schedule \"Текст\" дата время")
                return
                
            message_text = parts[1].strip()
            datetime_part = parts[2].strip()
        else:
            parts = command_rest.split()
            if len(parts) < 3:
                bot.reply_to(message, "❌ Недостаточно аргументов. Нужен текст, дата и время")
                return
                
            message_text = ' '.join(parts[:-2])
            datetime_part = ' '.join(parts[-2:])

        if not message_text:
            bot.reply_to(message, "❌ Текст поста не может быть пустым!")
            return

        datetime_parts = datetime_part.split()
        if len(datetime_parts) < 2:
            bot.reply_to(message, "❌ Укажите дату И время: ГГГГ-ММ-ДД ЧЧ:ММ")
            return

        date_str = datetime_parts[0]
        time_str = datetime_parts[1]

        scheduled_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        now = datetime.now()
        
        time_diff = (scheduled_time - now).total_seconds()
        logger.info(f"⏰ Запланировано на: {scheduled_time}, через {time_diff:.0f} сек")
        
        if time_diff <= 0:
            bot.reply_to(message, "❌ Укажите будущее время!")
            return

        post_id = db.save_scheduled_post(message_text, scheduled_time)
        
        bot.reply_to(message, 
            f"✅ Пост запланирован!\n"
            f"🆔 ID: {post_id}\n"
            f"📅 Когда: {scheduled_time.strftime('%d.%m.%Y в %H:%M')}\n"
            f"📝 Текст: {message_text[:80]}...\n\n"
            f"Используйте /debug_posts для отладки"
        )
        logger.info(f"📅 Запланирован пост ID: {post_id} на {scheduled_time}")
        
    except ValueError as e:
        error_msg = f"❌ Неверный формат даты или времени!\nИспользуйте: ГГГГ-ММ-ДД ЧЧ:ММ\nПример: 2024-01-15 15:30"
        bot.reply_to(message, error_msg)
        logger.error(f"Ошибка формата даты: {e}")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")
        logger.error(f"Ошибка в schedule_command: {e}")

@bot.message_handler(commands=['list_posts'])
def list_posts_command(message):
    """Список запланированных постов"""
    if str(message.from_user.id) != ADMIN_ID:
        bot.reply_to(message, "⛔ Нет прав!")
        return

    posts = db.get_pending_posts()
    
    if not posts:
        bot.reply_to(message, "📭 Нет запланированных постов")
        return

    response = "📅 Запланированные посты:\n\n"
    for post in posts:
        post_id, text, post_time = post
        time_str = post_time.strftime('%d.%m.%Y %H:%M')
        time_left = (post_time - datetime.now()).total_seconds()
        
        status = "✅ ГОТОВ" if time_left <= 0 else f"⏳ {int(time_left/60)} мин"
        response += f"🆔 {post_id} | {status}\n"
        response += f"📅 {time_str}\n"
        response += f"📝 {text[:60]}...\n"
        response += "─" * 40 + "\n"

    bot.reply_to(message, response)

@bot.message_handler(commands=['help'])
def help_command(message):
    """Команда помощи"""
    bot.reply_to(message,
        "📖 Доступные команды:\n\n"
        "/start - начать работу\n"
        "/post_now [текст] - опубликовать пост сейчас\n"
        "/schedule [текст] [дата] [время] - запланировать пост\n"
        "/list_posts - показать запланированные посты\n"
        "/help - эта справка\n\n"
        "📅 Формат даты: ГГГГ-ММ-ДД ЧЧ:ММ\n"
        "Пример: /schedule \"Важное сообщение\" 2024-01-15 17:00"
    )

def main():
    """Запуск бота"""
    logger.info("🚀 Запуск бота...")
    
    # Проверяем переменные окружения
    if not all([BOT_TOKEN, CHANNEL_ID, ADMIN_ID]):
        logger.error("❌ Не все переменные окружения установлены!")
        logger.error(f"BOT_TOKEN: {'✅' if BOT_TOKEN else '❌'}")
        logger.error(f"CHANNEL_ID: {'✅' if CHANNEL_ID else '❌'}")
        logger.error(f"ADMIN_ID: {'✅' if ADMIN_ID else '❌'}")
        return
    
    # Запускаем планировщик
    scheduler_thread = threading.Thread(target=post_scheduler, daemon=True)
    scheduler_thread.start()
    
    # Запускаем бота
    logger.info("Бот готов к работе! Используйте /start в Telegram")
    try:
        bot.polling(none_stop=True, interval=1)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")

if __name__ == '__main__':
    main()


