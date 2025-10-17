# В функции auto_content_scheduler заменяем:
def auto_content_scheduler():
    """Автоматический поиск контента (без авто-публикации)"""
    logger.info("⏰ Запущен автоматический поиск контента")
    
    def job():
        try:
            if CONTENT_FINDER_AVAILABLE and bot_running:
                logger.info("🔄 Автоматический поиск контента...")
                finder = setup_content_finder()
                found_content = finder.search_content(max_posts=3)  # 3 поста в день
                
                if found_content:
                    for content in found_content:
                        content_id = db.add_found_content(content)
                        
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
                    
                    logger.info(f"✅ Отправлено {len(found_content)} постов на модерацию")
                        
        except Exception as e:
            logger.error(f"❌ Ошибка автоматического поиска: {e}")
    
    # Запускаем 2 раза в день (утром и вечером)
    while bot_running:
        job()
        time.sleep(43200)  # 12 часов

# В обработчике callback меняем только approve:
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
