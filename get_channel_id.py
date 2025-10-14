import os
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

BOT_TOKEN = "YOUR_BOT_TOKEN"

async def get_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"Chat ID: {update.message.chat.id}")

app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.ALL, get_chat_id))
app.run_polling()