# content_finder.py
import logging
from datetime import datetime
import random

logger = logging.getLogger(__name__)

class ContentFinder:
    def __init__(self):
        pass

    def search_content(self, max_posts=3):
        """Основной метод поиска контента"""
        logger.info("🔍 Начинаю поиск контента...")
        
        found_content = []
        
        for _ in range(max_posts):
            content = self.generate_vk_style_post()
            if content:
                found_content.append(content)
        
        logger.info(f"🎯 Сгенерировано материалов: {len(found_content)}")
        return found_content

    def generate_vk_style_post(self):
        """Генерирует короткий пост в стиле вашей группы ВК"""
        
        # Создаем очень короткие и простые посты
        templates = [
            "🏆 Первый в истории {subject}\n• Год: {year}\n• Место: {place}\n• {achievement}\n\n#первый #{subject}",
            
            "💡 Исторический прорыв: {subject}\n• Когда: {year}\n• Кто: {who}\n• {what}\n\n#прорыв #{subject}",
            
            "🚀 Рекордный результат: {subject}\n• Дата: {year}\n• Рекорд: {record}\n• {impact}\n\n#рекорд #{subject}"
        ]
        
        subjects = [
            "телефон", "компьютер", "самолет", "автомобиль", "телевидение", "радио",
            "интернет", "электричество", "фотография", "космический полет", "метро"
        ]
        
        places = ["США", "Россия", "Германия", "Франция", "Великобритания", "Япония"]
        years = ["1876", "1903", "1927", "1957", "1969", "1983", "1991", "1998"]
        
        template = random.choice(templates)
        subject = random.choice(subjects)
        
        # Заполняем шаблон
        full_post_text = template.format(
            subject=subject,
            year=random.choice(years),
            place=random.choice(places),
            achievement=random.choice([
                "Создано первое работающее устройство",
                "Проведен успешный эксперимент", 
                "Установлен мировой рекорд",
                "Получен патент на изобретение"
            ]),
            who=random.choice([
                "группа ученых",
                "инженер-самоучка",
                "исследовательский институт"
            ]),
            what=random.choice([
                "Разработана новая технология",
                "Создан революционный прототип",
                "Доказана неизвестная теория"
            ]),
            record=random.choice([
                "максимальная скорость",
                "наибольшая точность", 
                "рекордная эффективность"
            ]),
            impact=random.choice([
                "Изменило повседневную жизнь",
                "Открыло новые возможности",
                "Стало основой для открытий"
            ])
        )

        return {
            'title': f"Пост о {subject}",
            'summary': full_post_text,  # КОРОТКИЙ полный текст
            'category': 'history',
            'url': '',
            'found_date': datetime.now()
        }

    def format_for_preview(self, content):
        """Форматирует контент для предпросмотра"""
        return f"📰 ПРЕДПРОСМОТР ПОСТА\n\n{content['summary']}\n\n⏰ Сгенерировано: {content['found_date'].strftime('%H:%M %d.%m.%Y')}"

def setup_content_finder():
    """Инициализация системы поиска контента"""
    return ContentFinder()
