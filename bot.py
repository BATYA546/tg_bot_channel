import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, ChatMemberHandler
from telegram.constants import ParseMode
from datetime import datetime
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация из переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))
ADMIN_ID = int(os.getenv('ADMIN_ID'))
DATABASE_URL = os.getenv('DATABASE_URL')

# Проверка обязательных переменных
if not all([BOT_TOKEN, CHANNEL_ID, ADMIN_ID]):
    raise ValueError("Missing required environment variables!")

class DatabaseManager:
    def __init__(self):
        self.conn = None
        self.init_db()
    
    def get_connection(self):
        """Создает соединение с PostgreSQL"""
        if self.conn is None or self.conn.closed:
            if DATABASE_URL:
                # Для Railway PostgreSQL
                self.conn = psycopg2.connect(DATABASE_URL, sslmode='require')
            else:
                # Для локальной разработки
                self.conn = psycopg2.connect(
                    host='localhost',
                    database='telegram_bot',
                    user='postgres',
                    password='password'
                )
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
                    image_url TEXT,
                    scheduled_time TIMESTAMP,
                    is_published BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise

    def save_scheduled_post(self, message_text, image_url, scheduled_time):
        """Сохраняет пост в базу данных"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO scheduled_posts (message_text, image_url, scheduled_time)
                VALUES (%s, %s, %s)
                RETURNING id
            ''', (message_text, image_url, scheduled_time))
            conn.commit()
            post_id = cursor.fetchone()[0]
            return post_id
        except Exception as e:
            logger.error(f"Error saving post: {e}")
            raise
    
    def get_pending_posts(self):
        """Получает неопубликованные посты"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute('''
                SELECT id, message_text, image_url, scheduled_time 
                FROM scheduled_posts 
                WHERE is_published = FALSE AND scheduled_time > %s
                ORDER BY scheduled_time
            ''', (datetime.now(),))
            posts = cursor.fetchall()
            return posts
        except Exception as e:
            logger.error(f"Error getting pending posts: {e}")
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
            logger.error(f"Error marking post as published: {e}")

# Инициализация менеджера БД
db = DatabaseManager()

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветствует новых участников в канале."""
    try:
        if update.chat_member is None:
            return

        new_status = update.chat_member.new_chat_member.status
        old_status = update.chat_member.old_chat_member.status

        # Проверяем, что пользователь только что присоединился
        if (old_status == 'left' and new_status in ['member', 'administrator', 'creator']):
            user = update.chat_member.new_chat_member.user
            chat_id = update.chat_member.chat.id

            # Проверяем, что это наш канал
            if chat_id == CHANNEL_ID:
                welcome_text = f"""
🎉 Добро пожаловать в наш канал, [{user.first_name}](tg://user?id={user.id})!

Рады видеть тебя здесь! Ознакомься с закреплённым постом, чтобы узнать правила и полезные ссылки.

Не стесняйся задавать вопросы! 🤖
                """
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=welcome_text,
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=True
                )
                logger.info(f"Приветствовал нового пользователя: {user.first_name}")
    except Exception as e:
        logger.error(f"Error in welcome_new_member: {e}")

async def publish_scheduled_post(context: ContextTypes.DEFAULT_TYPE):
    """Публикует запланированный пост."""
    try:
        job = context.job
        post_data = job.data
        post_id = post_data['post_id']

        if post_data.get('image_url') and post_data['image_url'] != 'None':
            await context.bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=post_data['image_url'],
                caption=post_data['message_text'],
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await context.bot.send_message(
                chat_id=CHANNEL_ID,
                text=post_data['message_text'],
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True
            )
        
        # Отмечаем как опубликованный
        db.mark_as_published(post_id)
        logger.info(f"Опубликован запланированный пост ID: {post_id}")
        
    except Exception as e:
        logger.error(f"Ошибка при публикации поста: {e}")

schedule_post

async def post_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Немедленная публикация поста."""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ У вас нет прав для выполнения этой команды.")
        return

    # Получаем полный текст сообщения
    full_text = update.message.text
    logger.info(f"Received command: {full_text}")

    # Проверяем есть ли аргументы после команды
    if not full_text or len(full_text.strip()) <= len('/post_now'):
        await update.message.reply_text(
            "Использование: /post_now \"Текст поста\"\n\n"
            "Пример:\n"
            '/post_now "Привет, это тестовый пост!"'
        )
        return

    # Извлекаем текст поста (все что после /post_now)
    command_parts = full_text.split(' ', 1)
    if len(command_parts) < 2:
        await update.message.reply_text("❌ Не указан текст поста!")
        return

    message_text = command_parts[1].strip()
    
    # Убираем кавычки если они есть
    if message_text.startswith('"') and message_text.endswith('"'):
        message_text = message_text[1:-1]
    elif message_text.startswith('"') and message_text.endswith('"'):
        message_text = message_text[1:-1]

    if not message_text:
        await update.message.reply_text("❌ Текст поста не может быть пустым!")
        return

    logger.info(f"Publishing post: {message_text}")

    try:
        # Публикуем простой текстовый пост
        await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=message_text,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )
        
        await update.message.reply_text("✅ Пост успешно опубликован в канал!")
        logger.info(f"Пост опубликован: {message_text[:50]}...")

    except Exception as e:
        error_msg = f"❌ Ошибка при публикации: {str(e)}"
        await update.message.reply_text(error_msg)
        logger.error(f"Error in post_now: {e}")

async def list_posts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает запланированные посты."""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ У вас нет прав для выполнения этой команды.")
        return

    posts = db.get_pending_posts()
    
    if not posts:
        await update.message.reply_text("📭 Нет запланированных постов.")
        return

    message = "📅 Запланированные посты:\n\n"
    for post in posts:
        message += f"🆔 {post['id']}\n"
        message += f"📅 {post['scheduled_time'].strftime('%d.%m.%Y %H:%M')}\n"
        message += f"📝 {post['message_text'][:50]}...\n"
        message += f"🖼️ {'Да' if post['image_url'] else 'Нет'}\n"
        message += "─" * 30 + "\n"

    await update.message.reply_text(message)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда start"""
    await update.message.reply_text(
        "🤖 Бот для управления каналом запущен!\n\n"
        "Доступные команды:\n"
        "/schedule - запланировать пост\n"
        "/post_now - опубликовать сейчас\n"
        "/list_posts - список запланированных постов\n\n"
        "Примеры:\n"
        '/schedule "Привет мир" none 2024-01-15 14:30\n'
        '/post_now "Срочная новость"'
    )

async def load_scheduled_posts(application: Application):
    """Загружает неопубликованные посты при старте бота."""
    try:
        posts = db.get_pending_posts()
        loaded_count = 0
        
        for post in posts:
            scheduled_time = post['scheduled_time']
            time_delta = scheduled_time - datetime.now()
            seconds_until_post = time_delta.total_seconds()

            if seconds_until_post > 0:
                application.job_queue.run_once(
                    publish_scheduled_post,
                    seconds_until_post,
                    data={
                        'message_text': post['message_text'], 
                        'image_url': post['image_url'],
                        'post_id': post['id']
                    },
                    name=str(post['id'])
                )
                loaded_count += 1
                logger.info(f"Загружен запланированный пост ID: {post['id']}")
            else:
                # Если время уже прошло, отмечаем как опубликованный
                db.mark_as_published(post['id'])
                logger.info(f"Пропущен просроченный пост ID: {post['id']}")
                
        logger.info(f"Загружено {loaded_count} запланированных постов")
    except Exception as e:
        logger.error(f"Error loading scheduled posts: {e}")

def main():
    """Основная функция"""
    try:
        # Создаем приложение
        application = Application.builder().token(BOT_TOKEN).build()

        # Добавляем обработчики
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("schedule", schedule_post))
        application.add_handler(CommandHandler("post_now", post_now))
        application.add_handler(CommandHandler("list_posts", list_posts))
        application.add_handler(ChatMemberHandler(welcome_new_member, ChatMemberHandler.CHAT_MEMBER))

        # Загружаем запланированные посты при старте
        application.job_queue.run_once(
            lambda ctx: load_scheduled_posts(application), 
            3
        )

        # Запускаем бота
        logger.info("Бот запускается...")
        application.run_polling()
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise

if __name__ == '__main__':
    main()

