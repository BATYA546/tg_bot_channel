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
        """Генерирует пост в стиле вашей группы ВК"""
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
        
        subjects = [
            "телефон", "компьютер", "самолет", "автомобиль", "телевидение", "радио",
            "кинематограф", "интернет", "электричество", "фотография", "музыкальная запись",
            "космический полет", "подводная лодка", "метро", "поезд", "велосипед"
        ]
        
        places = ["США", "Россия", "Германия", "Франция", "Великобритания", "Италия", "Япония", "Китай"]
        years = ["1876", "1903", "1927", "1941", "1957", "1969", "1983", "1991", "1998", "2007"]
        
        template = random.choice(templates)
        subject = random.choice(subjects)
        
        title = template["title"].format(subject=subject)
        emoji = template["emoji"]
        
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
                    "первый прототип стоил целое состояние"
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
            elif "Значение" in fact_template:
                significances = [
                    "это изобретение изменило повседневную жизнь миллионов людей",
                    "технология стала основой для последующих открытий",
                    "рекорд не побит до сих пор"
                ]
                facts.append(fact_template.format(significance=random.choice(significances)))
        
        # Формируем ПОЛНЫЙ текст поста - БЕЗ Markdown разметки
        full_post_text = f"{emoji} {title}\n\n"
        for fact in facts:
            full_post_text += f"• {fact}\n"
        
        # Добавляем хештеги
        hashtags = ["#первый", "#история", "#рекорд", f"#{subject}"]
        random.shuffle(hashtags)
        full_post_text += f"\n{' '.join(hashtags[:3])}"

        return {
            'title': title,
            'summary': full_post_text,  # ПОЛНЫЙ текст
            'category': 'history',
            'url': '',
            'found_date': datetime.now()
        }

    def format_for_preview(self, content):
        """Форматирует контент для предпросмотра - БЕЗ Markdown"""
        return f"""
📰 ПРЕДПРОСМОТР ПОСТА

{content['summary']}

⏰ Сгенерировано: {content['found_date'].strftime('%H:%M %d.%m.%Y')}
        """

def setup_content_finder():
    """Инициализация системы поиска контента"""
    return ContentFinder()
