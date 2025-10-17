import os
import logging
import threading
import time
import re
import requests
import io
import urllib.parse
from datetime import datetime, timedelta, timezone
from PIL import Image
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

# Флаг для остановки бота
bot_running = True

# Импорт content_finder
try:
    from content_finder import setup_content_finder
    CONTENT_FINDER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"❌ ContentFinder не доступен: {e}")
    CONTENT_FINDER_AVAILABLE = False

def get_current_time():
    """Возвращает текущее время с правильным часовым поясом"""
    return datetime.now(timezone.utc) + timedelta(hours=TIMEZONE_OFFSET)

def download_image(image_url):
    """Скачивает изображение по URL"""
    try:
        if not image_url:
            return None
            
        logger.info(f"📥 Загружаю изображение: {image_url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8'
        }
        
        response = requests.get(image_url, headers=headers, timeout=10)
        if response.status_code == 200:
            # Проверяем что это изображение по content-type
            content_type = response.headers.get('content-type', '')
            if 'image' in content_type:
                logger.info(f"✅ Изображение загружено: {len(response.content)} байт")
                return response.content
            else:
                logger.error(f"❌ Не изображение: {content_type}")
                return None
        else:
            logger.error(f"❌ Ошибка HTTP {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки изображения: {e}")
        return None

def send_post_with_image(chat_id, text, image_data=None):
    """Отправляет пост с изображением"""
    try:
        if image_data:
            # Отправляем фото с подписью
            bot.send_photo(chat_id, image_data, caption=text)
            logger.info(f"✅ Пост с изображением отправлен в {chat_id}")
        else:
            # Отправляем просто текст
            bot.send_message(chat_id, text)
            logger.info(f"✅ Текстовый пост отправлен в {chat_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка отправки поста с изображением: {e}")
        # Пробуем отправить без изображения
        try:
            bot.send_message(chat_id, text)
            logger.info(f"✅ Пост отправлен без изображения в {chat_id}")
            return True
        except Exception as e2:
            logger.error(f"❌ Критическая ошибка отправки: {e2}")
            return False

def send_formatted_message(chat_id, text):
    """Простая отправка сообщений без форматирования"""
    try:
        # Просто отправляем как обычный текст
        bot.send_message(chat_id, text)
        logger.info(f"✅ Сообщение отправлено в {chat_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка отправки сообщения: {e}")
        return False

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
            
            # Добавляем индексы для ускорения поиска дубликатов
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_found_content_title ON found_content(title)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_found_content_found_at ON found_content(found_at)')
            
            conn.commit()
            logger.info("✅ PostgreSQL database initialized with indexes")
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
                INSERT INTO found_content (title, content, category, url, image_url)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            ''', (
                content_data['title'], 
                content_data['summary'], 
                content_data['category'], 
                content_data.get('url', ''),
                content_data.get('image_url', '')
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
                SELECT id, title, content, category, is_approved, is_published, image_url
                FROM found_content 
                WHERE id = %s
            ''', (content_id,))
            result = cursor.fetchone()
            return result
        except Exception as e:
            logger.error(f"❌ Error getting found content: {e}")
            return None

    def is_content_exists(self, title, content):
        """Проверяет, существует ли уже такой контент в базе"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Ищем похожие посты по заголовку и содержанию
            cursor.execute('''
                SELECT id FROM found_content 
                WHERE title = %s OR content LIKE %s
            ''', (title, f"%{title[:50]}%"))
            
            result = cursor.fetchone()
            return result is not None
            
        except Exception as e:
            logger.error(f"❌ Error checking content existence: {e}")
            return False

    def get_all_content_hashes(self):
        """Возвращает все существующие хеши контента из БД"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT title, content FROM found_content')
            existing_posts = cursor.fetchall()
            
            hashes = set()
            for title, content in existing_posts:
                text = title + content
                content_hash = hashlib.md5(text.encode()).hexdigest()
                hashes.add(content_hash)
                
            logger.info(f"✅ Загружено {len(hashes)} существующих хешей из БД")
            return hashes
            
        except Exception as e:
            logger.error(f"❌ Error loading content hashes: {e}")
            return set()

# Инициализация БД
db = DatabaseManager()

# Словарь для хранения редактируемых постов
editing_posts = {}

# Словарь для хранения состояний пользователей
user_states = {}

def publish_approved_post(content_id):
    """Публикует одобренный пост в канал"""
    try:
        # Получаем контент из базы
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT content, image_url FROM found_content WHERE id = %s', (content_id,))
        result = cursor.fetchone()
        
        if result:
            full_post_text, image_url = result
            logger.info(f"📤 Публикую пост {content_id}")
            logger.info(f"🖼️ URL изображения: {image_url}")
            
            # Скачиваем изображение если есть
            image_data = None
            if image_url and image_url.startswith('http'):
                image_data = download_image(image_url)
                if image_data:
                    logger.info(f"✅ Изображение загружено для поста {content_id}")
                else:
                    logger.warning(f"⚠️ Не удалось загрузить изображение для поста {content_id}")
            else:
                logger.warning(f"⚠️ Некорректный URL изображения: {image_url}")
            
            # Публикуем в канал
            success = send_post_with_image(CHANNEL_ID, full_post_text, image_data)
            
            if success:
                # Отмечаем как опубликованный
                cursor.execute('UPDATE found_content SET is_published = TRUE WHERE id = %s', (content_id,))
                conn.commit()
                logger.info(f"✅ Пост {content_id} опубликован в канале")
                return True
            else:
                logger.error(f"❌ Не удалось опубликовать пост {content_id}")
        
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
    while bot_running:
        try:
            publish_scheduled_posts()
            time.sleep(30)
        except Exception as e:
            logger.error(f"💥 Ошибка планировщика: {e}")
            time.sleep(30)

def auto_content_scheduler():
    """Автоматический поиск контента (без авто-публикации)"""
    logger.info("⏰ Запущен автоматический поиск контента")
    
    def job():
        try:
            if CONTENT_FINDER_AVAILABLE and bot_running:
                logger.info("🔄 Автоматический поиск контента...")
                
                # Создаем ContentFinder с передачей db_manager
                finder = setup_content_finder(db)
                found_content = finder.search_content(max_posts=3)
                
                if found_content:
                    new_posts_count = 0
                    for content in found_content:
                        # Дополнительная проверка перед сохранением
                        if not db.is_content_exists(content['title'], content['summary']):
                            content_id = db.add_found_content(content)
                            new_posts_count += 1
                            
                            # Форматируем превью
                            preview = finder.format_for_preview(content)
                            
                            # Создаем клавиатуру для модерации
                            markup = telebot.types.InlineKeyboardMarkup()
                            markup.row(
                                telebot.types.InlineKeyboardButton("✅ Опубликовать", callback_data=f"approve_{content_id}"),
                                telebot.types.InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_{content_id}"),
                                telebot.types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{content_id}")
                            )
                            
                            # Отправляем админу на одобрение
                            bot.send_message(
                                ADMIN_ID,
                                preview,
                                reply_markup=markup
                            )
                            time.sleep(2)
                        else:
                            logger.info(f"🚫 Пропускаем дубликат: {content['title'][:30]}...")
                    
                    if new_posts_count > 0:
                        logger.info(f"✅ Отправлено {new_posts_count} новых постов на модерацию")
                    else:
                        logger.info("ℹ️ Новых постов не найдено")
                        
        except Exception as e:
            logger.error(f"❌ Ошибка автоматического поиска: {e}")
    
    # Запускаем 2 раза в день (утром и вечером)
    while bot_running:
        job()
        time.sleep(43200)  # 12 часов

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
    global bot_running
    while bot_running:
        try:
            logger.info("🔄 Запуск бота...")
            bot.polling(none_stop=True, interval=1, timeout=60)
        except Exception as e:
            if not bot_running:
                break
            if "409" in str(e):
                logger.warning("⚠️ Конфликт - жду 10 секунд")
                time.sleep(10)
            else:
                logger.error(f"❌ Ошибка: {e}")
                time.sleep(30)

def show_admin_menu(chat_id):
    """Показывает меню админа с кнопками"""
    current_time = get_current_time()
    
    menu_text = f"""
🤖 Бот управления каналом

⏰ Время: {current_time.strftime('%H:%M %d.%m.%Y')}

⚙️ Выберите действие:
"""
    
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    # Первый ряд кнопок
    markup.row(
        telebot.types.KeyboardButton('📝 Опубликовать пост'),
        telebot.types.KeyboardButton('⏰ Запланировать пост')
    )
    
    # Второй ряд кнопок
    markup.row(
        telebot.types.KeyboardButton('📋 Список постов'),
        telebot.types.KeyboardButton('📊 Статистика')
    )
    
    # Третий ряд кнопок
    markup.row(
        telebot.types.KeyboardButton('🔍 Найти контент'),
        telebot.types.KeyboardButton('📰 Просмотреть посты')
    )
    
    # Четвертый ряд кнопок
    markup.row(
        telebot.types.KeyboardButton('🕒 Проверить время'),
        telebot.types.KeyboardButton('🛑 Остановить бота')
    )
    
    # Кнопка скрытия клавиатуры
    markup.row(telebot.types.KeyboardButton('📱 Скрыть меню'))
    
    bot.send_message(chat_id, menu_text, reply_markup=markup)

def hide_menu(chat_id):
    """Скрывает меню"""
    remove_markup = telebot.types.ReplyKeyboardRemove()
    bot.send_message(chat_id, "📱 Меню скрыто. Используйте /start для показа меню.", reply_markup=remove_markup)

# ВСЕ ОБРАБОТЧИКИ ДОЛЖНЫ БЫТЬ ПОСЛЕ ОПРЕДЕЛЕНИЯ ВСЕХ ФУНКЦИЙ:

@bot.message_handler(commands=['start'])
def start_command(message):
    """Команда start"""
    if str(message.from_user.id) == ADMIN_ID:
        show_admin_menu(message.chat.id)
    else:
        response = """
👋 Привет!

Я бот канала "Самое Первое" 🏆

📌 Мы публикуем:
• Первые открытия и изобретения
• Мировые рекорды
• Революционные технологии

💡 Будьте в курсе самого важного!
"""
        bot.reply_to(message, response)

@bot.message_handler(func=lambda message: message.text == '📱 Скрыть меню')
def hide_menu_command(message):
    """Скрытие меню"""
    if str(message.from_user.id) == ADMIN_ID:
        hide_menu(message.chat.id)

@bot.message_handler(func=lambda message: message.text == '📝 Опубликовать пост')
def post_now_button(message):
    """Кнопка публикации поста"""
    if str(message.from_user.id) != ADMIN_ID:
        bot.reply_to(message, "⛔ Нет прав!")
        return
    
    user_states[message.chat.id] = 'waiting_post_text'
    bot.send_message(message.chat.id, "📝 Введите текст поста для немедленной публикации:")

@bot.message_handler(func=lambda message: message.text == '⏰ Запланировать пост')
def schedule_button(message):
    """Кнопка планирования поста"""
    if str(message.from_user.id) != ADMIN_ID:
        bot.reply_to(message, "⛔ Нет прав!")
        return
    
    user_states[message.chat.id] = 'waiting_schedule_text'
    bot.send_message(message.chat.id, "📅 Введите текст поста для планирования (в следующем сообщении укажите дату и время):")

@bot.message_handler(func=lambda message: message.text == '📋 Список постов')
def list_posts_button(message):
    """Кнопка списка постов"""
    if str(message.from_user.id) != ADMIN_ID:
        bot.reply_to(message, "⛔ Нет прав!")
        return
    
    list_posts_command(message)

@bot.message_handler(func=lambda message: message.text == '📊 Статистика')
def stats_button(message):
    """Кнопка статистики"""
    if str(message.from_user.id) != ADMIN_ID:
        bot.reply_to(message, "⛔ Нет прав!")
        return
    
    stats_command(message)

@bot.message_handler(func=lambda message: message.text == '🔍 Найти контент')
def find_content_button(message):
    """Кнопка поиска контента"""
    if str(message.from_user.id) != ADMIN_ID:
        bot.reply_to(message, "⛔ Нет прав!")
        return
    
    find_content_command(message)

@bot.message_handler(func=lambda message: message.text == '📰 Просмотреть посты')
def view_found_button(message):
    """Кнопка просмотра постов"""
    if str(message.from_user.id) != ADMIN_ID:
        bot.reply_to(message, "⛔ Нет прав!")
        return
    
    view_found_command(message)

@bot.message_handler(func=lambda message: message.text == '🕒 Проверить время')
def time_button(message):
    """Кнопка проверки времени"""
    if str(message.from_user.id) != ADMIN_ID:
        bot.reply_to(message, "⛔ Нет прав!")
        return
    
    time_command(message)

@bot.message_handler(func=lambda message: message.text == '🛑 Остановить бота')
def stop_button(message):
    """Кнопка остановки бота"""
    if str(message.from_user.id) != ADMIN_ID:
        bot.reply_to(message, "⛔ Нет прав!")
        return
    
    stop_command(message)

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'waiting_post_text')
def handle_post_text(message):
    """Обработка текста для немедленной публикации"""
    try:
        text = message.text.strip()
        if not text:
            bot.reply_to(message, "❌ Текст поста не может быть пустым!")
            return
        
        success = send_formatted_message(CHANNEL_ID, text)
        if success:
            bot.reply_to(message, "✅ Пост опубликован!")
        else:
            bot.reply_to(message, "❌ Не удалось опубликовать пост")
        
        # Сбрасываем состояние
        user_states.pop(message.chat.id, None)
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")
        user_states.pop(message.chat.id, None)

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'waiting_schedule_text')
def handle_schedule_text(message):
    """Обработка текста для планирования"""
    try:
        text = message.text.strip()
        if not text:
            bot.reply_to(message, "❌ Текст поста не может быть пустым!")
            return
        
        # Сохраняем текст и запрашиваем дату
        user_states[message.chat.id] = {'state': 'waiting_schedule_time', 'text': text}
        bot.reply_to(message, "⏰ Теперь введите дату и время в формате: ГГГГ-ММ-ДД ЧЧ:ММ\nНапример: 2024-01-15 15:30")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")
        user_states.pop(message.chat.id, None)

@bot.message_handler(func=lambda message: 
                    user_states.get(message.chat.id) and 
                    user_states[message.chat.id].get('state') == 'waiting_schedule_time')
def handle_schedule_time(message):
    """Обработка времени для планирования"""
    try:
        user_data = user_states[message.chat.id]
        message_text = user_data['text']
        datetime_str = message.text.strip()
        
        scheduled_time = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
        
        if scheduled_time <= get_current_time():
            bot.reply_to(message, "❌ Укажите будущее время!")
            return
        
        post_id = db.save_scheduled_post(message_text, scheduled_time)
        
        bot.reply_to(message, f"✅ Пост #{post_id} запланирован на {scheduled_time.strftime('%H:%M %d.%m.%Y')}")
        
        # Сбрасываем состояние
        user_states.pop(message.chat.id, None)
        
    except ValueError:
        bot.reply_to(message, "❌ Неверный формат даты. Используйте: ГГГГ-ММ-ДД ЧЧ:ММ")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")
        user_states.pop(message.chat.id, None)

@bot.message_handler(commands=['stop'])
def stop_command(message):
    """Остановка бота"""
    global bot_running
    
    if str(message.from_user.id) != ADMIN_ID:
        bot.reply_to(message, "⛔ Нет прав!")
        return
    
    bot_running = False
    logger.info("🛑 Получена команда остановки бота")
    bot.reply_to(message, "🛑 Бот останавливается...")
    
    # Даем время на отправку ответа
    time.sleep(2)
    
    # Завершаем работу
    logger.info("✅ Бот остановлен")
    exit(0)

@bot.message_handler(commands=['time'])
def time_command(message):
    """Показывает текущее время бота"""
    current_time = get_current_time()
    bot.reply_to(message, f"🕒 Текущее время бота: {current_time.strftime('%H:%M:%S %d.%m.%Y')}")

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

    response = "📅 Запланированные посты:\n\n"
    for post in posts:
        post_id, text, post_time = post
        time_str = post_time.strftime('%d.%m %H:%M')
        time_left = (post_time - now).total_seconds()
        
        status = "✅ ГОТОВ" if time_left <= 0 else f"⏳ {int(time_left/60)} мин"
        response += f"🆔 {post_id} | {status}\n"
        response += f"📅 {time_str}\n"
        response += f"📝 {text[:50]}...\n"
        response += "─" * 30 + "\n"

    bot.reply_to(message, response)

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
        
        cursor.execute('SELECT COUNT(*) FROM found_content')
        total_found_count = cursor.fetchone()[0]
        
        stats_text = f"""
📊 Статистика бота:

🗃️ База данных: ✅ PostgreSQL
📊 Публикации:
✅ Опубликовано вручную: {published_count}
🤖 Опубликовано авто: {auto_published_count}
⏳ В ожидании: {pending_count}

📋 Найденный контент:
📥 Всего найдено: {total_found_count}
✅ Опубликовано: {auto_published_count}

⏰ Время: {current_time.strftime('%H:%M %d.%m.%Y')}

Бот работает исправно! 🚀
"""
        bot.reply_to(message, stats_text)
        
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
        
        # Передаем db_manager в content_finder для проверки дубликатов
        finder = setup_content_finder(db)
        found_content = finder.search_content(max_posts=2)
        
        if found_content:
            new_posts_count = 0
            for content in found_content:
                # Дополнительная проверка перед сохранением
                if not db.is_content_exists(content['title'], content['summary']):
                    content_id = db.add_found_content(content)
                    new_posts_count += 1
                    
                    # Форматируем превью
                    preview = finder.format_for_preview(content)
                    
                    # Создаем клавиатуру
                    markup = telebot.types.InlineKeyboardMarkup()
                    markup.row(
                        telebot.types.InlineKeyboardButton("✅ Опубликовать", callback_data=f"approve_{content_id}"),
                        telebot.types.InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_{content_id}"),
                        telebot.types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{content_id}")
                    )
                    
                    # Отправляем сообщение с кнопками
                    bot.send_message(
                        message.chat.id, 
                        preview, 
                        reply_markup=markup
                    )
                    time.sleep(1)
                else:
                    logger.info(f"🚫 Пропускаем дубликат: {content['title'][:30]}...")
            
            if new_posts_count > 0:
                bot.reply_to(message, f"✅ Найдено {new_posts_count} новых материалов. Проверьте предложения выше!")
            else:
                bot.reply_to(message, "❌ Новых материалов не найдено, все уже есть в базе.")
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
        
        response = "📋 Последние найденные посты:\n\n"
        for post in posts:
            post_id, title, content, category, approved, published = post
            
            status = "✅ Одобрен" if approved else "⏳ На модерации"
            status += " 📤 Опубликован" if published else ""
            
            response += f"🆔 {post_id} | {status}\n"
            response += f"📁 {category}\n"
            response += f"📝 {title[:50]}...\n"
            response += "─" * 30 + "\n"
        
        bot.reply_to(message, response)
        
    except Exception as e:
        logger.error(f"❌ Ошибка просмотра постов: {e}")
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    """Обработчик нажатий на инлайн-кнопки"""
    try:
        if call.data.startswith('approve_'):
            content_id = int(call.data.split('_')[1])
            bot.answer_callback_query(call.id, "📤 Публикую пост...")
            
            # Получаем контент из базы
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT content, image_url FROM found_content WHERE id = %s', (content_id,))
            result = cursor.fetchone()
            
            if result:
                full_post_text, image_url = result
                
                # Публикуем в канал
                success = publish_approved_post(content_id)
                
                if success:
                    final_text = "✅ ПОСТ ОПУБЛИКОВАН В КАНАЛЕ! 📢"
                    # Отмечаем как одобренный
                    cursor.execute('UPDATE found_content SET is_approved = TRUE WHERE id = %s', (content_id,))
                    conn.commit()
                else:
                    final_text = "❌ Ошибка публикации поста"
                
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=final_text
                )
            
        elif call.data.startswith('reject_'):
            content_id = int(call.data.split('_')[1])
            bot.answer_callback_query(call.id, "❌ Пост отклонен")
            
            # Просто отмечаем как отклоненный
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM found_content WHERE id = %s', (content_id,))
            conn.commit()
            
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="❌ Пост отклонен и удален"
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
                
                # Показываем полный текст для редактирования
                edit_message = f"""✏️ РЕДАКТИРОВАНИЕ ПОСТА #{content_id}

Текущий текст:
{full_post_text}

📝 Отправьте исправленный текст:"""
                
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="✏️ Режим редактирования"
                )
                
                bot.send_message(
                    call.message.chat.id,
                    edit_message
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
        updated_preview = f"""✏️ ТЕКСТ ОБНОВЛЕН

{new_content}

✅ Изменения сохранены. Теперь можете одобрить пост."""
        
        # Создаем новую клавиатуру для обновленного поста
        markup = telebot.types.InlineKeyboardMarkup()
        markup.row(
            telebot.types.InlineKeyboardButton("✅ Опубликовать", callback_data=f"approve_{content_id}"),
            telebot.types.InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_{content_id}"),
            telebot.types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{content_id}")
        )
        
        bot.send_message(
            message.chat.id,
            updated_preview,
            reply_markup=markup
        )
        
        logger.info(f"✏️ Контент {content_id} отредактирован")
        
    except Exception as e:
        logger.error(f"❌ Ошибка редактирования: {e}")
        bot.reply_to(message, f"❌ Ошибка при сохранении: {e}")

def main():
    """Запуск бота"""
    global bot_running
    
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
