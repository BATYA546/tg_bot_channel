# content_finder.py
import requests
import logging
from datetime import datetime
import time
from bs4 import BeautifulSoup
import random
import re

logger = logging.getLogger(__name__)

class ContentFinder:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Расширяем ключевые слова
        self.keywords = [
            "перв", "революц", "рекорд", "прорыв", "инновац", "открытие",
            "изобрет", "технолог", "наук", "истори", "уникальн", "новый",
            "прогресс", "разработк", "создан", "запуск", "обнаружен"
        ]
        
        # Добавляем больше источников
        self.sources = [
            {
                'name': 'РИА Новости (наука)',
                'url': 'https://ria.ru/science/',
                'parser': self.parse_ria_science
            },
            {
                'name': 'ТАСС (наука)',
                'url': 'https://tass.ru/nauka',
                'parser': self.parse_tass_science
            },
            {
                'name': 'N+1 (архив)',
                'url': 'https://nplus1.ru/news/archive',
                'parser': self.parse_nplus1_archive
            }
        ]

    def search_content(self, max_posts=5):
        """Основной метод поиска контента"""
        logger.info("🔍 Начинаю поиск контента...")
        
        found_content = []
        
        for source in self.sources:
            try:
                logger.info(f"📰 Проверяю {source['name']}...")
                content = source['parser'](source['url'])
                if content:
                    found_content.extend(content)
                    logger.info(f"✅ Найдено: {len(content)} записей")
                
                if len(found_content) >= max_posts:
                    found_content = found_content[:max_posts]
                    break
                    
                time.sleep(3)  # Увеличиваем паузу
                
            except Exception as e:
                logger.error(f"❌ Ошибка парсинга {source['name']}: {e}")
                continue
        
        # Если ничего не нашли, используем fallback - создаем тестовый контент
        if not found_content:
            found_content = self.generate_fallback_content()
        
        logger.info(f"🎯 Всего найдено материалов: {len(found_content)}")
        return found_content

def parse_ria_science(self, url):
    """Парсер РИА Новости (наука)"""
    try:
        response = self.session.get(url, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        articles = []
        news_items = soup.find_all('div', class_=['list-item', 'cell'])
        
        for item in news_items[:15]:
            try:
                title_elem = item.find(['a', 'h2', 'span'])
                if not title_elem:
                    continue
                    
                title = title_elem.get_text().strip()
                if len(title) < 10:
                    continue
                
                if self.is_relevant_content(title):
                    article_data = {
                        'title': title,
                        'summary': self.generate_summary(title),
                        'category': self.categorize_content(title),
                        'url': '',  # Убрали source, оставили url пустым
                        'found_date': datetime.now()
                    }
                    articles.append(article_data)
                    
            except Exception as e:
                logger.debug(f"Ошибка обработки статьи РИА: {e}")
                continue
                
        return articles[:3]
        
    except Exception as e:
        logger.error(f"Ошибка парсинга РИА: {e}")
        return []

def parse_tass_science(self, url):
    """Парсер ТАСС (наука)"""
    try:
        response = self.session.get(url, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        articles = []
        news_items = soup.find_all(['article', 'div'], class_=True)
        
        for item in news_items[:20]:
            try:
                title_elem = (item.find('h2') or 
                             item.find('h3') or 
                             item.find('a') or 
                             item.find('span'))
                
                if not title_elem:
                    continue
                    
                title = title_elem.get_text().strip()
                if len(title) < 15:
                    continue
                
                if self.is_relevant_content(title):
                    article_data = {
                        'title': title,
                        'summary': self.generate_summary(title),
                        'category': self.categorize_content(title),
                        'url': '',
                        'found_date': datetime.now()
                    }
                    articles.append(article_data)
                    
            except Exception as e:
                continue
                
        return articles[:2]
        
    except Exception as e:
        logger.error(f"Ошибка парсинга ТАСС: {e}")
        return []

def parse_nplus1_archive(self, url):
    """Парсер архива N+1"""
    try:
        response = self.session.get(url, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        articles = []
        news_items = soup.find_all('article')[:10]
        
        for item in news_items:
            try:
                title_elem = item.find('h2') or item.find('a')
                if not title_elem:
                    continue
                    
                title = title_elem.get_text().strip()
                
                if self.is_relevant_content(title):
                    article_data = {
                        'title': title,
                        'summary': self.generate_summary(title),
                        'category': self.categorize_content(title),
                        'url': '',
                        'found_date': datetime.now()
                    }
                    articles.append(article_data)
                    
            except Exception:
                continue
                
        return articles[:2]
        
    except Exception as e:
        logger.error(f"Ошибка парсинга N+1: {e}")
        return []

def generate_fallback_content(self):
    """Генерирует тестовый контент если ничего не найдено"""
    logger.info("🔄 Генерирую тестовый контент...")
    
    fallback_titles = [
        "Ученые создали первый в мире квантовый компьютер с рекордной производительностью",
        "Революционная технология позволила впервые получить энергию из вакуума",
        "Историческое открытие: обнаружена новая частица, меняющая представления о физике",
        "Первый в мире искусственный интеллект прошел тест Тьюринга с рекордным результатом",
        "Инновационная разработка: созданы солнечные батареи с КПД более 50%"
    ]
    
    content_list = []
    for title in random.sample(fallback_titles, 3):
        content_list.append({
            'title': title,
            'summary': self.generate_summary(title),
            'category': self.categorize_content(title),
            'url': '',
            'found_date': datetime.now()
        })
    
    return content_list

# В методе format_for_preview меняем:
def format_for_preview(self, content):
    """Форматирует контент для предпросмотра"""
    # Создаем эмодзи для категорий
    category_emojis = {
        'technology': '🔧',
        'science': '🔬', 
        'records': '🏆',
        'discovery': '💡'
    }
    
    emoji = category_emojis.get(content['category'], '📰')
    
    return f"""
{emoji} *Новый материал для публикации*

*Заголовок:* {content['title']}
*Категория:* {content['category']}

*Полный текст:*
{content['summary']}

⏰ Найдено: {content['found_date'].strftime('%H:%M %d.%m.%Y')}
        """

def setup_content_finder():
    """Инициализация системы поиска контента"""
    return ContentFinder()
