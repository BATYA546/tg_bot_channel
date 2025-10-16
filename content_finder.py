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
            "🏆 Первый в истории {subject}\n• Год: {year}\n• Место: {place}\n• {achievement}\n• {fun_fact}\n\n#первый #{subject}",
            
            "💡 Исторический прорыв: {subject}\n• Когда: {year}\n• Кто: {who}\n• {what}\n• {significance}\n\n#прорыв #{subject}",
            
            "🚀 Рекордный результат: {subject}\n• Дата: {year}\n• Рекорд: {record}\n• {previous}\n• {impact}\n\n#рекорд #{subject}"
        ]
        
        subjects = [
            "телефон", "компьютер", "самолет", "автомобиль", "телевидение", "радио",
            "интернет", "электричество", "фотография", "космический_полет", "метро"
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
            fun_fact=random.choice([
                "Интересно: изобретатель потратил 10 лет",
                "Факт: технологию не оценили сразу",
                "Знаете ли вы: первый прототип был огромным",
                "Интересно: изначально для военных целей"
            ]),
            who=random.choice([
                "группа ученых",
                "инженер-самоучка",
                "исследовательский институт",
                "студент университета"
            ]),
            what=random.choice([
                "Разработана новая технология",
                "Создан революционный прототип",
                "Доказана неизвестная теория",
                "Установлен абсолютный рекорд"
            ]),
            significance=random.choice([
                "Значение: изменило жизнь миллионов",
                "Важность: основа для новых открытий",
                "Роль: рекорд не побит до сих пор"
            ]),
            record=random.choice([
                "максимальная скорость",
                "наибольшая точность", 
                "рекордная эффективность",
                "самая компактная конструкция"
            ]),
            previous=random.choice([
                "Предыдущий: 50% от текущего",
                "До этого: в 10 раз хуже",
                "Раньше: значительно больше размер",
                "Прежний: намного дольше по времени"
            ]),
            impact=random.choice([
                "Изменило повседневную жизнь",
                "Открыло новые возможности",
                "Стало основой для открытий",
                "Кардинально изменило коммуникации"
            ])
        )

        return {
            'title': f"Пост о {subject}",
            'summary': full_post_text,
            'category': 'history',
            'url': '',
            'found_date': datetime.now()
        }

    def format_for_preview(self, content):
        """Форматирует контент для предпросмотра"""
        current_time = datetime.now()
        return f"📰 ПРЕДПРОСМОТР ПОСТА\n\n{content['summary']}\n\n⏰ Сгенерировано: {current_time.strftime('%H:%M %d.%m.%Y')}"

def setup_content_finder():
    """Инициализация системы поиска контента"""
    return ContentFinder()
