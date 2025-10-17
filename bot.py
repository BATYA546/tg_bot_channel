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

# ... (все функции остаются здесь: get_current_time, download_image, send_post_with_image, etc.)
# ... (DatabaseManager класс и все остальные функции)

# Словарь для хранения редактируемых постов
editing_posts = {}

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

# ВСЕ ОБРАБОТЧИКИ ДОЛЖНЫ БЫТЬ ПОСЛЕ ОПРЕДЕЛЕНИЯ ВСЕХ ФУНКЦИЙ:

@bot.message_handler(commands=['start'])
def start_command(message):
    """Команда start"""
    if str(message.from_user.id) == ADMIN_ID:
        current_time = get_current_time()
        response = f"""
🤖 Бот управления каналом

⏰ Время: {current_time.strftime('%H:%M %d.%m.%Y')}

⚙️ Команды:
/post_now - опубликовать пост
/schedule - запланировать пост  
/list_posts - список постов
/stats - статистика
/find_content - найти контент
/view_found - просмотреть найденные посты
/time - проверить время
/stop - остановить бота

📝 Пример:
/schedule "Важно сообщение" 2024-01-15 15:30
"""
        bot.reply_to(message, response)
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
        
        stats_text = f"""
📊 Статистика бота:

🗃️ База данных: ✅ PostgreSQL
📊 Публикации:
✅ Опубликовано вручную: {published_count}
🤖 Опубликовано авто: {auto_published_count}
⏳ В ожидании: {pending_count}

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
        
        finder = setup_content_finder()
        found_content = finder.search_content(max_posts=2)
        
        if found_content:
            for content in found_content:
                content_id = db.add_found_content(content)
                
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

if __name__ == '__main__':
    main()
