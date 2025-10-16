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
            "космический полет", "подводная лодка", "метро", "поезд", "велосипед",
            "мобильный телефон", "электронная почта", "социальная сеть", "поисковая система",
            "операционная система", "компьютерная игра", "веб-сайт", "онлайн-трансляция"
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
                    "получен патент на изобретение",
                    "запущено первое массовое производство"
                ]
                facts.append(fact_template.format(achievement=random.choice(achievements)))
            elif "Интересный факт" in fact_template:
                fun_facts = [
                    "изобретатель потратил на разработку более 10 лет",
                    "первоначально изобретение не оценили современники",
                    "технология изначально создавалась для военных целей",
                    "первый прототип стоил целое состояние",
                    "изобретатель был вдохновлен природными явлениями",
                    "проект финансировался за счет личных сбережений изобретателя",
                    "первая версия имела множество недостатков, но положила начало новой эре"
                ]
                facts.append(fact_template.format(fun_fact=random.choice(fun_facts)))
            elif "Кто" in fact_template:
                inventors = [
                    "группа ученых из международной лаборатории",
                    "один талантливый инженер-самоучка",
                    "научно-исследовательский институт",
                    "студент университета",
                    "частная компания-стартап"
                ]
                facts.append(fact_template.format(who=random.choice(inventors)))
            elif "Что сделано" in fact_template:
                whats = [
                    "разработана принципиально новая технология",
                    "создан прототип, превосходящий аналоги",
                    "доказана ранее неизвестная теория",
                    "установлен абсолютный рекорд",
                    "открыто новое направление в науке"
                ]
                facts.append(fact_template.format(what=random.choice(whats)))
            elif "Значение" in fact_template:
                significances = [
                    "это изобретение изменило повседневную жизнь миллионов людей",
                    "технология стала основой для последующих открытий",
                    "рекорд не побит до сих пор",
                    "это достижение открыло новые возможности для человечества"
                ]
                facts.append(fact_template.format(significance=random.choice(significances)))
            elif "Рекорд" in fact_template:
                records = [
                    "установлена максимальная скорость",
                    "достигнута наибольшая точность",
                    "создан самый компактный устройство",
                    "достигнута рекордная эффективность"
                ]
                facts.append(fact_template.format(record=random.choice(records)))
            elif "Предыдущий результат" in fact_template:
                previouses = [
                    "предыдущий рекорд составлял 50% от текущего",
                    "технология была в 10 раз менее эффективной",
                    "устройства были значительно больше по размеру",
                    "процесс занимал в несколько раз больше времени"
                ]
                facts.append(fact_template.format(previous=random.choice(previouses)))
            elif "Что это изменило" in fact_template:
                impacts = [
                    "это позволило ускорить развитие целой отрасли",
                    "технология сделала ранее недоступное доступным для всех",
                    "изобретение кардинально изменило коммуникации между людьми",
                    "это открыло новые горизонты для научных исследований"
                ]
                facts.append(fact_template.format(impact=random.choice(impacts)))
        
        # Формируем ПОЛНЫЙ текст поста в стиле ВК
        full_post_text = f"{emoji} {title}\n\n"
        for fact in facts:
            full_post_text += f"• {fact}\n"
        
        # Добавляем хештеги
        hashtags = ["#первый", "#история", "#рекорд", f"#{subject}"]
        random.shuffle(hashtags)
        full_post_text += f"\n{' '.join(hashtags[:3])}"

        # ВОЗВРАЩАЕМ ПОЛНЫЙ ТЕКСТ И В title И В summary
        return {
            'title': title,
            'summary': full_post_text,  # ЗДЕСЬ ПОЛНЫЙ ТЕКСТ
            'category': 'history',
            'url': '',
            'found_date': datetime.now()
        }

    def format_for_preview(self, content):
        """Форматирует контент для предпросмотра - показываем ПОЛНЫЙ текст"""
        return f"""
📰 *ПРЕДПРОСМОТР ПОСТА*

{content['summary']}

⏰ Сгенерировано: {content['found_date'].strftime('%H:%M %d.%m.%Y')}
        """

def setup_content_finder():
    """Инициализация системы поиска контента"""
    return ContentFinder()
