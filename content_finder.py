# content_finder.py
import requests
import logging
from datetime import datetime
import time
from bs4 import BeautifulSoup
import random

logger = logging.getLogger(__name__)

class ContentFinder:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Темы для постов в стиле вашей группы ВК
        self.topics = [
            "исторические события", "научные открытия", "технологические прорывы",
            "спортивные рекорды", "культурные достижения", "медицинские открытия"
        ]

    def search_content(self, max_posts=3):
        """Основной метод поиска контента"""
        logger.info("🔍 Начинаю поиск контента...")
        
        found_content = []
        
        # Генерируем посты в стиле ВК группы
        for _ in range(max_posts):
            content = self.generate_vk_style_post()
            if content:
                found_content.append(content)
        
        logger.info(f"🎯 Сгенерировано материалов: {len(found_content)}")
        return found_content

    def generate_vk_style_post(self):
        """Генерирует пост в стиле вашей группы ВК"""
        # Шаблоны заголовков как в ВК
        templates = [
            {
                "title": "Первый в истории: {subject}",
                "emoji": "🏆",
                "facts": [
                    "Год: {year}",
                    "Место: {place}",
                    "Достижение: {achievement}",
                    "Интересный факт: {fun_fact}"
                ]
            },
            {
                "title": "Исторический прорыв: {subject}",
                "emoji": "💡", 
                "facts": [
                    "Когда: {year}",
                    "Кто: {who}",
                    "Что сделано: {what}",
                    "Значение: {significance}"
                ]
            },
            {
                "title": "Рекордный результат: {subject}",
                "emoji": "🚀",
                "facts": [
                    "Дата: {year}",
                    "Рекорд: {record}",
                    "Предыдущий результат: {previous}",
                    "Что это изменило: {impact}"
                ]
            }
        ]
        
        # Данные для заполнения шаблонов
        subjects = [
            "телефон", "компьютер", "самолет", "автомобиль", "телевидение", "радио",
            "кинематограф", "интернет", "электричество", "фотография", "музыкальная запись",
            "космический полет", "подводная лодка", "метро", "поезд", "велосипед"
        ]
        
        places = ["США", "Россия", "Германия", "Франция", "Великобритания", "Италия", "Япония", "Китай"]
        years = ["1876", "1903", "1927", "1941", "1957", "1969", "1983", "1991", "1998", "2007"]
        
        template = random.choice(templates)
        subject = random.choice(subjects)
        
        # Заполняем шаблон
        title = template["title"].format(subject=subject)
        emoji = template["emoji"]
        
        # Генерируем факты
        facts = []
        for fact_template in template["facts"]:
            if "Год" in fact_template or "Когда" in fact_template or "Дата" in fact_template:
                facts.append(fact_template.format(year=random.choice(years)))
            elif "Место" in fact_template:
                facts.append(fact_template.format(place=random.choice(places)))
            elif "Достижение" in fact_template:
                achievements = [
                    "создано первое работающее устройство",
                    "проведен первый успешный эксперимент", 
                    "установлен мировой рекорд",
                    "получен патент на изобретение"
                ]
                facts.append(fact_template.format(achievement=random.choice(achievements)))
            elif "Интересный факт" in fact_template:
                fun_facts = [
                    "изобретатель потратил на разработку более 10 лет",
                    "первоначально изобретение не оценили современники",
                    "технология изначально создавалась для военных целей",
                    "первый прототип стоил целое состояние",
                    "изобретатель был вдохновлен природными явлениями"
                ]
                facts.append(fact_template.format(fun_fact=random.choice(fun_facts)))
            elif "Кто" in fact_template:
                inventors = [
                    "группа ученых из международной лаборатории",
                    "один талантливый инженер-самоучка",
                    "научно-исследовательский институт",
                    "студент университета"
                ]
                facts.append(fact_template.format(who=random.choice(inventors)))
            elif "Что сделано" in fact_template:
                whats = [
                    "разработана принципиально новая технология",
                    "создан прототип, превосходящий аналоги",
                    "доказана ранее неизвестная теория",
                    "установлен абсолютный рекорд"
                ]
                facts.append(fact_template.format(what=random.choice(whats)))
        
        # Формируем текст поста в стиле ВК
        post_text = f"{emoji} {title}\n\n"
        for fact in facts:
            post_text += f"• {fact}\n"
        
        post_text += f"\n#первый #история #рекорд #{subject}"
        
        return {
            'title': title,
            'summary': post_text,
            'category': 'history',
            'url': '',
            'found_date': datetime.now()
        }

    def format_for_preview(self, content):
        """Форматирует контент для предпросмотра"""
        return f"""
📰 *ПРЕДПРОСМОТР ПОСТА*

{content['summary']}

⏰ Сгенерировано: {content['found_date'].strftime('%H:%M %d.%m.%Y')}
        """

def setup_content_finder():
    """Инициализация системы поиска контента"""
    return ContentFinder()
