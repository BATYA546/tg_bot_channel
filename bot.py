import os
import logging
import threading
import time
import re
from datetime import datetime, timedelta
import telebot
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

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
DATABASE_URL = os.getenv('DATABASE_URL')

bot = telebot.TeleBot(BOT_TOKEN)

# Исправление часового пояса (UTC+3 для Москвы)
TIMEZONE_OFFSET = 3

def get_current_time():
    """Возвращает текущее время с поправкой на часовой пояс"""
    return datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)

class DatabaseManager:
    def __init__(self):
        self.conn = None
        self.init_db()
    
    def get_connection(self):
        """Создает соединение с PostgreSQL"""
        if self.conn is None or self.conn.closed:
            if DATABASE_URL:
                self.conn = psycopg2.connect(DATABASE_URL, sslmode='require')
            else:
                logger.error("DATABASE_URL not found")
                raise Exception("Database connection failed")
        return self.conn
    
    def init_db(self):
        """Инициализация базы данных"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scheduled_posts (
                    id SERIAL PRIMARY KEY,
                    message_text TEXT,
                    scheduled_time TIMESTAMP,
                    is_published BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            logger.info("✅ PostgreSQL database initialized")
        except Exception as e:
            logger.error(f"❌ Database init error: {e}")

    def save_scheduled_post(self, message_text, scheduled_time):
        """Сохраняет пост в базу данных"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO scheduled_posts (message_text, scheduled_time)
                VALUES (%s, %s)
                RETURNING id
            ''', (message_text, scheduled_time))
            conn.commit()
            post_id = cursor.fetchone()[0]
            return post_id
        except Exception as e:
            logger.error(f"❌ Error saving post: {e}")
            raise
    
    def get_pending_posts(self):
        """Получает неопубликованные посты"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, message_text, scheduled_time 
                FROM scheduled_posts 
                WHERE is_published = FALSE
                ORDER BY scheduled_time
            ''')
            posts = cursor.fetchall()
            return posts
        except Exception as e:
            logger.error(f"❌ Error getting posts: {e}")
            return []
    
    def mark_as_published(self, post_id):
        """Отмечает пост как опубликованный"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE scheduled_posts 
                SET is_published = TRUE 
                WHERE id = %s
            ''', (post_id,))
            conn.commit()
        except Exception as e:
            logger.error(f"❌ Error marking post: {e}")

# Инициализация БД
db = DatabaseManager()

def send_formatted_message(chat_id, text):
    """Умная отправка сообщений с форматированием"""
    # Заменяем \n на настоящие переносы строк
    text = text.replace('\\n', '\n')
    
    try:
        # Пробуем Markdown
        bot.send_message(chat_id, text, parse_mode='Markdown')
        return True
    except:
        try:
            # Пробуем HTML
            html_text = text
            html_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', html_text)
            html_text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', html_text)
            html_text = re.sub(r'__(.*?)__', r'<u>\1</u>', html_text)
            bot.send_message(chat_id, html_text, parse_mode='HTML')
            return True
        except:
            # Отправляем как простой текст
            bot.send_message(chat_id, text, parse_mode=None)
            return True

def publish_scheduled_posts():
    """Публикует запланированные посты"""
    try:
        posts = db.get_pending_posts()
        now = get_current_time()
        
        published_count = 0
        for post in posts:
            post_id, message_text, scheduled_time = post
            time_left = (scheduled_time - now).total_seconds()
            
            if time_left <= 0:
                try:
                    success = send_formatted_message(CHANNEL_ID, message_text)
                    if success:
                        db.mark_as_published(post_id)
                        published_count += 1
                        logger.info(f"✅ Опубликован пост ID: {post_id}")
                    time.sleep(1)
                except Exception as e:
                    logger.error(f"❌ Ошибка публикации: {e}")
        
        if published_count > 0:
            logger.info(f"📤 Опубликовано постов: {published_count}")
                
    except Exception as e:
        logger.error(f"❌ Ошибка в планировщике: {e}")

def post_scheduler():
    """Планировщик постов"""
    logger.info("🕒 Запущен планировщик постов")
    while True:
        try:
            publish_scheduled_posts()
            time.sleep(30)
        except Exception as e:
            logger.error(f"💥 Ошибка планировщика: {e}")
            time.sleep(30)

def safe_polling():
    """Безопасный запуск бота"""
    while True:
        try:
            logger.info("🔄 Запуск бота...")
            bot.polling(none_stop=True, interval=1, timeout=60)
        except Exception as e:
            if "409" in str(e):
                logger.warning("⚠️ Конфликт - жду 10 секунд")
                time.sleep(10)
            else:
                logger.error(f"❌ Ошибка: {e}")
                time.sleep(30)

@bot.message_handler(commands=['start'])
def start_command(message):
    """Команда start"""
    if str(message.from_user.id) == ADMIN_ID:
        current_time = get_current_time()
        response = f"""
🤖 *Бот управления каналом*

⏰ Время: {current_time.strftime('%H:%M %d.%m.%Y')}

⚙️ *Команды:*
/post_now - опубликовать пост
/schedule - запланировать пост  
/list_posts - список постов
/stats - статистика

📝 *Пример:*
/schedule "**Важно** сообщение" 2024-01-15 15:30
"""
    else:
        response = """
👋 *Привет!*

Я бот канала *"Обо всём самом первом"* 🏆

📌 Мы публикуем:
• Первые открытия и изобретения
• Мировые рекорды
• Революционные технологии

💡 *Будьте в курсе самого важного!*
"""
    
    bot.reply_to(message, response, parse_mode='Markdown')

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
        success = send_formatted_message(CHANNEL_ID, text)
        if success:
            bot.reply_to(message, "✅ Пост опубликован!")
        else:
            bot.reply_to(message, "❌ Не удалось опубликовать")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['schedule'])
def schedule_command(message):
    """Планирование поста"""
    if str(message.from_user.id) != ADMIN_ID:
        bot.reply_to(message, "⛔ Нет прав!")
        return

    try:
        parts = message.text.split('"')
        if len(parts) < 3:
            bot.reply_to(message, 'Использование: /schedule "Текст" 2024-01-15 15:00')
            return

        message_text = parts[1]
        datetime_part = parts[2].strip().split()
        
        if len(datetime_part) < 2:
            bot.reply_to(message, "Укажите дату и время: ГГГГ-ММ-ДД ЧЧ:ММ")
            return

        date_str, time_str = datetime_part[0], datetime_part[1]
        scheduled_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        
        if scheduled_time <= get_current_time():
            bot.reply_to(message, "Укажите будущее время!")
            return

        post_id = db.save_scheduled_post(message_text, scheduled_time)
        bot.reply_to(message, f"✅ Пост #{post_id} запланирован на {scheduled_time.strftime('%H:%M %d.%m.%Y')}")
        
    except ValueError:
        bot.reply_to(message, "❌ Неверный формат даты. Используйте: ГГГГ-ММ-ДД ЧЧ:ММ")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['list_posts'])
def list_posts_command(message):
    """Список запланированных постов"""
    if str(message.from_user.id) != ADMIN_ID:
        bot.reply_to(message, "⛔ Нет прав!")
        return

    posts = db.get_pending_posts()
    now = get_current_time()
    
    if not posts:
        bot.reply_to(message, "📭 Нет запланированных постов")
        return

    response = "📅 *Запланированные посты:*\n\n"
    for post in posts:
        post_id, text, post_time = post
        time_str = post_time.strftime('%d.%m %H:%M')
        time_left = (post_time - now).total_seconds()
        
        status = "✅ ГОТОВ" if time_left <= 0 else f"⏳ {int(time_left/60)} мин"
        response += f"🆔 {post_id} | {status}\n"
        response += f"📅 {time_str}\n"
        response += f"📝 {text[:50]}...\n"
        response += "─" * 30 + "\n"

    bot.reply_to(message, response, parse_mode='Markdown')

@bot.message_handler(commands=['stats'])
def stats_command(message):
    """Статистика бота"""
    if str(message.from_user.id) != ADMIN_ID:
        bot.reply_to(message, "⛔ Нет прав!")
        return

    try:
        current_time = get_current_time()
        
        posts = db.get_pending_posts()
        pending_count = len(posts)
        
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM scheduled_posts WHERE is_published = TRUE')
        published_count = cursor.fetchone()[0]
        
        stats_text = f"""
📊 *Статистика бота:*

🗃️ *База данных:* ✅ PostgreSQL
📊 *Публикации:*
✅ Опубликовано: {published_count}
⏳ В ожидании: {pending_count}

⏰ *Время:* {current_time.strftime('%H:%M %d.%m.%Y')}

*Бот работает исправно!* 🚀
"""
        bot.reply_to(message, stats_text, parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка статистики: {e}")

def main():
    """Запуск бота"""
    logger.info("🚀 Запуск бота...")
    
    if not all([BOT_TOKEN, CHANNEL_ID, ADMIN_ID]):
        logger.error("❌ Не все переменные окружения установлены!")
        return
    
    # Запускаем планировщик
    scheduler_thread = threading.Thread(target=post_scheduler, daemon=True)
    scheduler_thread.start()
    
    # Запускаем бота
    logger.info("✅ Бот готов к работе!")
    safe_polling()

if __name__ == '__main__':
    main()
