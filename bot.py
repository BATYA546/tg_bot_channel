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

# Импорт content_finder
try:
    from content_finder import setup_content_finder
    CONTENT_FINDER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"❌ ContentFinder не доступен: {e}")
    CONTENT_FINDER_AVAILABLE = False

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
            
            # Таблица для запланированных постов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scheduled_posts (
                    id SERIAL PRIMARY KEY,
                    message_text TEXT,
                    scheduled_time TIMESTAMP,
                    is_published BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица для найденного контента
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS found_content (
                    id SERIAL PRIMARY KEY,
                    title TEXT,
                    content TEXT,
                    category VARCHAR(50),
                    url TEXT,
                    image_url TEXT,
                    is_approved BOOLEAN DEFAULT FALSE,
                    is_published BOOLEAN DEFAULT FALSE,
                    found_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

    def add_found_content(self, content_data):
        """Сохраняет найденный контент в базу"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO found_content (title, content, category, url)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            ''', (
                content_data['title'], 
                content_data['summary'], 
                content_data['category'], 
                content_data.get('url', '')
            ))
            
            conn.commit()
            content_id = cursor.fetchone()[0]
            logger.info(f"✅ Сохранен найденный контент ID: {content_id}")
            return content_id
            
        except Exception as e:
            logger.error(f"❌ Error saving found content: {e}")
            raise

    def get_found_content(self, content_id):
        """Получает найденный контент по ID"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, title, content, category, is_approved, is_published
                FROM found_content 
                WHERE id = %s
            ''', (content_id,))
            result = cursor.fetchone()
            return result
        except Exception as e:
            logger.error(f"❌ Error getting found content: {e}")
            return None

# Инициализация БД
db = DatabaseManager()

# Словарь для хранения редактируемых постов
editing_posts = {}

def send_formatted_message(chat_id, text):
    """Умная отправка сообщений с форматированием"""
    try:
        # Сначала пробуем отправить как есть (без форматирования)
        bot.send_message(chat_id, text, parse_mode=None)
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка отправки сообщения: {e}")
        try:
            # Если не получается, разбиваем на части
            if len(text) > 4000:
                parts = []
                lines = text.split('\n')
                current_part = ""
                
                for line in lines:
                    if len(current_part + line) < 4000:
                        current_part += line + "\n"
                    else:
                        parts.append(current_part)
                        current_part = line + "\n"
                
                if current_part:
                    parts.append(current_part)
                
                for part in parts:
                    bot.send_message(chat_id, part, parse_mode=None)
                    time.sleep(0.5)
            else:
                bot.send_message(chat_id, text, parse_mode=None)
            
            return True
        except Exception as e2:
            logger.error(f"❌ Критическая ошибка отправки: {e2}")
            return False
        
    except Exception as e:
        logger.error(f"❌ Ошибка публикации поста {content_id}: {e}")
        return False

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

def auto_content_scheduler():
    """Автоматический поиск и публикация контента"""
    logger.info("⏰ Запущен автоматический планировщик контента")
    
    def job():
        try:
            if CONTENT_FINDER_AVAILABLE:
                logger.info("🔄 Автоматический поиск контента...")
                finder = setup_content_finder()
                found_content = finder.search_content(max_posts=1)  # 1 пост за раз
                
                if found_content:
                    content = found_content[0]
                    content_id = db.add_found_content(content)
                    
                    # Сразу публикуем в канал
                    success = publish_approved_post(content_id)
                    
                    if success:
                        logger.info(f"✅ Автопост {content_id} опубликован")
                    else:
                        logger.error(f"❌ Ошибка автопубликации {content_id}")
                        
        except Exception as e:
            logger.error(f"❌ Ошибка автоматического планировщика: {e}")
    
    # Временное решение: запускать каждые 10 минут для теста
    while True:
        job()  # Запускаем сразу
        time.sleep(600)  # Ждем 10 минут

def start_scheduler():
    """Запускает все планировщики"""
    # Запускаем планировщик постов
    post_scheduler_thread = threading.Thread(target=post_scheduler, daemon=True)
    post_scheduler_thread.start()
    
    # Запускаем автопланировщик контента
    auto_scheduler_thread = threading.Thread(target=auto_content_scheduler, daemon=True)
    auto_scheduler_thread.start()
    
    logger.info("✅ Все планировщики запущены")

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
🤖 <b>Бот управления каналом</b>

⏰ Время: {current_time.strftime('%H:%M %d.%m.%Y')}

⚙️ <b>Команды:</b>
/post_now - опубликовать пост
/schedule - запланировать пост  
/list_posts - список постов
/stats - статистика
/find_content - найти контент
/view_found - просмотреть найденные посты

📝 <b>Пример:</b>
/schedule "<b>Важно</b> сообщение" 2024-01-15 15:30
"""
        bot.reply_to(message, response, parse_mode='HTML')
    else:
        response = """
👋 <b>Привет!</b>

Я бот канала <b>"Самое Первое"</b> 🏆

📌 <b>Мы публикуем:</b>
• Первые открытия и изобретения
• Мировые рекорды
• Революционные технологии

💡 <b>Будьте в курсе самого важного!</b>
"""
        bot.reply_to(message, response, parse_mode='HTML')

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
        
        cursor.execute('SELECT COUNT(*) FROM found_content WHERE is_published = TRUE')
        auto_published_count = cursor.fetchone()[0]
        
        stats_text = f"""
📊 *Статистика бота:*

🗃️ *База данных:* ✅ PostgreSQL
📊 *Публикации:*
✅ Опубликовано вручную: {published_count}
🤖 Опубликовано авто: {auto_published_count}
⏳ В ожидании: {pending_count}

⏰ *Время:* {current_time.strftime('%H:%M %d.%m.%Y')}

*Бот работает исправно!* 🚀
"""
        bot.reply_to(message, stats_text, parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка статистики: {e}")

@bot.message_handler(commands=['find_content'])
def find_content_command(message):
    """Ручной поиск контента"""
    if str(message.from_user.id) != ADMIN_ID:
        bot.reply_to(message, "⛔ Нет прав!")
        return

    if not CONTENT_FINDER_AVAILABLE:
        bot.reply_to(message, "❌ Модуль поиска контента не доступен")
        return

    try:
        bot.reply_to(message, "🔍 Начинаю поиск контента...")
        
        finder = setup_content_finder()
        found_content = finder.search_content(max_posts=3)
        
        if found_content:
            for content in found_content:
                content_id = db.add_found_content(content)
                
                # Форматируем превью БЕЗ Markdown
                preview = finder.format_for_preview(content)
                
                # Создаем клавиатуру
                markup = telebot.types.InlineKeyboardMarkup()
                markup.row(
                    telebot.types.InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{content_id}"),
                    telebot.types.InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_{content_id}"),
                    telebot.types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{content_id}")
                )
                
                # Отправляем сообщение с кнопками БЕЗ Markdown
                bot.send_message(
                    message.chat.id, 
                    preview, 
                    parse_mode=None,  # ВАЖНО: отключаем Markdown
                    reply_markup=markup
                )
                time.sleep(1)
            
            bot.reply_to(message, f"✅ Найдено {len(found_content)} материалов. Проверьте предложения выше!")
        else:
            bot.reply_to(message, "❌ Не найдено подходящего контента.")
            
    except Exception as e:
        logger.error(f"❌ Ошибка поиска контента: {e}")
        bot.reply_to(message, f"❌ Ошибка поиска: {e}")

@bot.message_handler(commands=['view_found'])
def view_found_command(message):
    """Показывает все найденные посты"""
    if str(message.from_user.id) != ADMIN_ID:
        bot.reply_to(message, "⛔ Нет прав!")
        return

    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, title, content, category, is_approved, is_published
            FROM found_content 
            ORDER BY found_at DESC 
            LIMIT 10
        ''')
        posts = cursor.fetchall()
        
        if not posts:
            bot.reply_to(message, "📭 Нет найденных постов")
            return
        
        response = "📋 *Последние найденные посты:*\n\n"
        for post in posts:
            post_id, title, content, category, approved, published = post
            
            status = "✅ Одобрен" if approved else "⏳ На модерации"
            status += " 📤 Опубликован" if published else ""
            
            response += f"🆔 {post_id} | {status}\n"
            response += f"📁 {category}\n"
            response += f"📝 {title[:50]}...\n"
            response += "─" * 30 + "\n"
        
        bot.reply_to(message, response, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"❌ Ошибка просмотра постов: {e}")
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    """Обработчик нажатий на инлайн-кнопки"""
    try:
        if call.data.startswith('approve_'):
            content_id = int(call.data.split('_')[1])
            bot.answer_callback_query(call.id, "✅ Контент одобрен!")
            
            # Получаем полный текст из базы
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT content FROM found_content WHERE id = %s', (content_id,))
            result = cursor.fetchone()
            
            if result:
                full_post_text = result[0]
                
                # Сразу публикуем в канал
                success = publish_approved_post(content_id)
                
                if success:
                    # Вместо полного текста показываем короткое подтверждение
                    final_text = "✅ *ПОСТ УСПЕШНО ОПУБЛИКОВАН В КАНАЛЕ!* 📢"
                else:
                    final_text = "❌ Ошибка публикации поста"
                
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=final_text,
                    parse_mode='Markdown'
                )
            
        elif call.data.startswith('reject_'):
            content_id = int(call.data.split('_')[1])
            bot.answer_callback_query(call.id, "❌ Контент отклонен")
            
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="❌ *Контент отклонен*",
                parse_mode='Markdown'
            )
            
        elif call.data.startswith('edit_'):
            content_id = int(call.data.split('_')[1])
            bot.answer_callback_query(call.id, "✏️ Загружаем полный текст...")
            
            # Получаем полный текст из базы
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT content FROM found_content WHERE id = %s', (content_id,))
            result = cursor.fetchone()
            
            if result:
                full_post_text = result[0]
                
                # Сохраняем в памяти для редактирования
                editing_posts[call.message.chat.id] = content_id
                
                # Показываем полный текст для редактирования БЕЗ Markdown
                edit_message = f"""✏️ РЕДАКТИРОВАНИЕ ПОСТА #{content_id}

Текущий текст:
{full_post_text}

📝 Отправьте исправленный текст:"""
                
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="✏️ Режим редактирования",
                    parse_mode=None
                )
                
                bot.send_message(
                    call.message.chat.id,
                    edit_message,
                    parse_mode=None
                )
            
    except Exception as e:
        logger.error(f"❌ Ошибка обработки callback: {e}")
        bot.answer_callback_query(call.id, "❌ Ошибка обработки")

@bot.message_handler(func=lambda message: message.chat.id in editing_posts)
def handle_edit_text(message):
    """Обрабатывает редактирование текста поста"""
    try:
        content_id = editing_posts.pop(message.chat.id, None)
        if not content_id:
            return
            
        new_content = message.text.strip()
        
        # Обновляем в базе - сохраняем весь текст как есть
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE found_content 
            SET content = %s 
            WHERE id = %s
        ''', (new_content, content_id))
        conn.commit()
        
        # Показываем обновленную версию
        updated_preview = f"""
✏️ *ТЕКСТ ОБНОВЛЕН*

{new_content}

✅ Изменения сохранены. Теперь можете одобрить пост.
        """
        
        # Создаем новую клавиатуру для обновленного поста
        markup = telebot.types.InlineKeyboardMarkup()
        markup.row(
            telebot.types.InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{content_id}"),
            telebot.types.InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_{content_id}"),
            telebot.types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{content_id}")
        )
        
        bot.send_message(
            message.chat.id,
            updated_preview,
            parse_mode='Markdown',
            reply_markup=markup
        )
        
        logger.info(f"✏️ Контент {content_id} отредактирован")
        
    except Exception as e:
        logger.error(f"❌ Ошибка редактирования: {e}")
        bot.reply_to(message, f"❌ Ошибка при сохранении: {e}")

def main():
    """Запуск бота"""
    logger.info("🚀 Запуск бота...")
    
    if not all([BOT_TOKEN, CHANNEL_ID, ADMIN_ID]):
        logger.error("❌ Не все переменные окружения установлены!")
        return
    
    # Запускаем все планировщики
    start_scheduler()
    
    # Запускаем бота
    logger.info("✅ Бот готов к работе!")
    safe_polling()

if __name__ == '__main__':
    main()


