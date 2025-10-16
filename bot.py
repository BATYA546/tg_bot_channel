import os
import logging
import sqlite3
import threading
import time
import random
import re
from datetime import datetime, timedelta
import telebot
from dotenv import load_dotenv

# Исправление часового пояса (UTC+3 для Москвы)
TIMEZONE_OFFSET = 3

def get_current_time():
    """Возвращает текущее время с поправкой на часовой пояс"""
    return datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)

def parse_schedule_time(date_str, time_str):
    """Парсит время планирования"""
    return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")

def format_time(dt):
    """Форматирует время для отображения"""
    return dt.strftime('%Y-%m-%d %H:%M:%S')

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

from telebot import types

@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_member(message):
    """Приветствует новых участников с интерактивной кнопкой"""
    try:
        for new_member in message.new_chat_members:
            if new_member.id == bot.get_me().id:
                continue
                
            if str(message.chat.id) == CHANNEL_ID:
                # Создаем клавиатуру с кнопкой
                markup = types.InlineKeyboardMarkup()
                channel_btn = types.InlineKeyboardButton(
                    "📱 Включить уведомления", 
                    url="https://t.me/e_f_world"  # Замените на username вашего канала
                )
                markup.add(channel_btn)
                
                welcome_text = f"""
🏆 *Добро пожаловать, {new_member.first_name}!*

Вы присоединились к каналу о *Обо всём самом первом*:

🚀 **Первые в мире** открытия
⭐ **Мировые рекорды** и достижения  
💡 **Революционные** технологии
📌 **Уникальные** события

*Чтобы не пропустить ничего важного:*
                """
                
                bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=welcome_text,
                    parse_mode='Markdown',
                    reply_markup=markup
                )
                
                logger.info(f"👋 Приветствовал: {new_member.first_name}")
                
    except Exception as e:
        logger.error(f"❌ Ошибка при приветствии: {e}")

@bot.message_handler(commands=['stats'])
def stats_command(message):
    """Показывает статистику канала"""
    if str(message.from_user.id) != ADMIN_ID:
        bot.reply_to(message, "⛔ Нет прав!")
        return

    try:
        current_time = get_current_time()
        
        # Получаем статистику из базы
        conn = sqlite3.connect('posts.db', detect_types=sqlite3.PARSE_DECLTYPES)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM scheduled_posts WHERE is_published = TRUE')
        published_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM scheduled_posts WHERE is_published = FALSE')
        pending_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM scheduled_posts')
        total_count = cursor.fetchone()[0]
        
        # Последний опубликованный пост
        cursor.execute('''
            SELECT scheduled_time FROM scheduled_posts 
            WHERE is_published = TRUE 
            ORDER BY scheduled_time DESC 
            LIMIT 1
        ''')
        last_post = cursor.fetchone()
        last_post_time = last_post[0].strftime('%d.%m.%Y %H:%M') if last_post else 'Нет'
        
        conn.close()
        
        stats_text = f"""
📊 *Статистика бота:*

📈 *Публикации:*
✅ Опубликовано: {published_count}
⏳ Ожидает: {pending_count}
📊 Всего: {total_count}

🕒 *Временные данные:*
⏰ Текущее время: {current_time.strftime('%H:%M')}
📅 Сегодня: {current_time.strftime('%d.%m.%Y')}
📮 Последний пост: {last_post_time}

💾 *База данных:*
🗃️ Таблицы: scheduled_posts
🔧 Статус: ✅ Активна
        """
        
        bot.reply_to(message, stats_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ошибка статистики: {e}")
        bot.reply_to(message, "❌ Ошибка получения статистики. Проверьте базу данных.")

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
            return posts
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения постов: {e}")
            return []
    
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

def send_formatted_message(chat_id, text):
    """
    Простая отправка с обработкой переносов строк
    """
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
        
        logger.info(f"🔍 Проверка постов... Найдено: {len(posts)}")
        logger.info(f"⏰ Текущее время сервера: {format_time(now)}")
        
        published_count = 0
        for post in posts:
            post_id, message_text, scheduled_time = post
            
            time_left = (scheduled_time - now).total_seconds()
            logger.info(f"📋 Пост {post_id}: запланирован на {format_time(scheduled_time)}, осталось {time_left:.0f} сек")
            
            # Публикуем если время наступило ИЛИ прошло
            if time_left <= 0:
                try:
                    logger.info(f"🚀 Публикую пост {post_id}: {message_text[:50]}...")
                    
                    # Используем умную отправку
                    success = send_formatted_message(CHANNEL_ID, message_text)
                    
                    if success:
                        db.mark_as_published(post_id)
                        published_count += 1
                        logger.info(f"✅ Успешно опубликован пост ID: {post_id}")
                    else:
                        logger.error(f"❌ Не удалось опубликовать пост ID: {post_id}")
                    
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

def safe_polling():
    """Безопасный запуск бота с обработкой конфликтов"""
    while True:
        try:
            logger.info("🔄 Запуск бота...")
            bot.polling(none_stop=True, interval=1, timeout=60)
            
        except Exception as e:
            if "409" in str(e):
                logger.warning("⚠️ Другой экземпляр бота уже запущен. Жду 10 секунд...")
                time.sleep(10)
            else:
                logger.error(f"❌ Ошибка: {e}")
                logger.info("🔄 Перезапуск бота через 30 секунд...")
                time.sleep(30)

@bot.message_handler(commands=['start'])
def start_command(message):
    """Универсальная команда start"""
    if str(message.from_user.id) == ADMIN_ID:
        # Админ
        current_time = get_current_time()
        response = (
            f"🤖 *Бот управления каналом*\n"
            f"⏰ Время: {current_time.strftime('%d.%m.%Y %H:%M')}\n\n"
            "⚙️ *Команды:*\n"
            "• /post_now текст - опубликовать\n"
            "• /schedule \"текст\" дата время - запланировать\n"  
            "• /list_posts - список запланированных\n"
            "• /debug_posts - отладка\n"
            "• /setup_welcome - приветствие\n"
            "• /stats - статистика\n\n"
            "📝 *Примеры:*\n"
            "/post_now Привет мир!\n"
            '/schedule "**Важно**" 2024-01-15 15:30'
        )
    else:
        # Обычный пользователь
        response = (
            "👋 *Добро пожаловать!*\n\n"
            "🏆 Я - бот канала *\"Обо всём самом первом\"*\n\n"
            "📌 Мы публикуем:\n"
            "• Первые открытия и изобретения\n"  
            "• Мировые рекорды\n"
            "• Революционные технологии\n"
            "• Уникальные события\n\n"
            "🔗 *Подпишитесь на канал:*\n"
            "Ищите `Обо всём самом первом` в Telegram\n\n"
            "*Будьте в курсе самого важного!* ✨"
        )

@bot.message_handler(commands=['setup_welcome'])
def setup_welcome_command(message):
    """Создает приветственное сообщение в канале"""
    if str(message.from_user.id) != ADMIN_ID:
        bot.reply_to(message, "⛔ Нет прав!")
        return

    try:
        welcome_text = """
🏆 *Добро пожаловать в "Обо всём самом первом"!* 

✨ *Что вас ждет:*
• Первые в мире открытия
• Мировые рекорды Гиннесса  
• Революционные технологии
• Исторические "впервые"

📱 *Совет:* Включите уведомления!

*Приятного просмотра!* 🚀
        """
        
        sent_message = bot.send_message(
            CHANNEL_ID,
            welcome_text,
            parse_mode='Markdown'
        )
        
        bot.reply_to(message, "✅ Приветственное сообщение создано в канале!")
            
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")



    
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
            bot.reply_to(message, "✅ Пост опубликован в канал!")
            logger.info(f"Опубликован пост: {text[:50]}...")
        else:
            bot.reply_to(message, "❌ Не удалось опубликовать пост")
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
            '/schedule "**Важное** объявление" 2024-01-15 16:00'
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

        scheduled_time = parse_schedule_time(date_str, time_str)
        now = get_current_time()
        
        time_diff = (scheduled_time - now).total_seconds()
        logger.info(f"⏰ Запланировано на: {format_time(scheduled_time)}, через {time_diff:.0f} сек")
        
        if time_diff <= 0:
            bot.reply_to(message, "❌ Укажите будущее время!")
            return

        post_id = db.save_scheduled_post(message_text, scheduled_time)
        
        bot.reply_to(message, 
            f"✅ Пост запланирован!\n"
            f"🆔 ID: {post_id}\n"
            f"📅 Когда: {scheduled_time.strftime('%d.%m.%Y в %H:%M')}\n"
            f"📝 Текст: {message_text[:80]}...\n\n"
            f"⏰ Текущее время: {now.strftime('%H:%M')}\n"
            f"Используйте /debug_posts для отладки"
        )
        logger.info(f"📅 Запланирован пост ID: {post_id} на {format_time(scheduled_time)}")
        
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
    now = get_current_time()
    
    if not posts:
        bot.reply_to(message, "📭 Нет запланированных постов")
        return

    response = f"📅 Запланированные посты (время: {now.strftime('%H:%M')}):\n\n"
    for post in posts:
        post_id, text, post_time = post
        time_str = post_time.strftime('%d.%m.%Y %H:%M')
        time_left = (post_time - now).total_seconds()
        
        status = "✅ ГОТОВ" if time_left <= 0 else f"⏳ {int(time_left/60)} мин"
        response += f"🆔 {post_id} | {status}\n"
        response += f"📅 {time_str}\n"
        response += f"📝 {text[:60]}...\n"
        response += "─" * 40 + "\n"

    bot.reply_to(message, response)

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
        
        now = get_current_time()
        response = f"🐛 ОТЛАДКА ПОСТОВ (всего: {len(all_posts)})\n"
        response += f"⏰ Текущее время: {format_time(now)}\n\n"
        
        for post in all_posts:
            post_id, text, post_time, is_published, created_at = post
            time_str = format_time(post_time)
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

@bot.message_handler(commands=['formatting'])
def formatting_command(message):
    """Справка по форматированию текста"""
    help_text = """
🎨 **Поддерживаемое форматирование:**

**Жирный текст** - двойные звездочки:
`**жирный текст**` → **жирный текст**

*Курсив* - одинарные звездочки:
`*курсив*` → *курсив*

__Подчеркнутый__ - двойное подчеркивание:
`__подчеркнутый__` → __подчеркнутый__

`Моноширинный` - обратные кавычки:
`` `код` `` → `код`

📝 **Переносы строк:**
Используйте `\\n` для переноса строки

**Пример правильного сообщения:**
/schedule "**ВАЖНОЕ ОБЪЯВЛЕНИЕ**\\n\\nСегодня *особенный* день!\\n__Не пропустите__ наше мероприятие." 2024-01-15 16:30

**Результат:**
**ВАЖНОЕ ОБЪЯВЛЕНИЕ**

Сегодня *особенный* день!
__Не пропустите__ наше мероприятие.
"""
    bot.reply_to(message, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['help'])
def help_command(message):
    """Команда помощи"""
    current_time = get_current_time()
    
    bot.reply_to(message,
        f"📖 Доступные команды (время: {current_time.strftime('%H:%M')}):\n\n"
        "/start - начать работу\n"
        "/post_now [текст] - опубликовать пост сейчас\n"
        "/schedule [текст] [дата] [время] - запланировать пост\n"
        "/list_posts - показать запланированные посты\n"
        "/debug_posts - отладка постов\n"
        "/formatting - справка по форматированию\n"
        "/help - эта справка\n\n"
        "📅 Формат даты: ГГГГ-ММ-ДД ЧЧ:ММ\n"
        "Пример: /schedule \"**Важное сообщение**\" 2024-01-15 17:00"
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
    
    # Запускаем бота с безопасным polling
    logger.info("Бот готов к работе! Используйте /start в Telegram")
    safe_polling()

if __name__ == '__main__':
    main()






