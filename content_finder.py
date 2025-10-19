# content_finder.py
import logging
import requests
from datetime import datetime
import random
import hashlib
from bs4 import BeautifulSoup
import re
import time
import urllib.parse
import feedparser

logger = logging.getLogger(__name__)

class ContentFinder:
    def __init__(self, db_manager=None):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
        self.db_manager = db_manager
        self.post_hashes = set()
        if db_manager:
            self.load_existing_hashes()
        
        self.sources = [
            self.parse_science_news,
            self.parse_tech_news,
            self.parse_historical_facts
        ]

    def load_existing_hashes(self):
        """Загружает существующие хеши из БД"""
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT title, content FROM found_content')
            existing_posts = cursor.fetchall()
            
            for title, content in existing_posts:
                text = title + content[:200]
                content_hash = hashlib.md5(text.encode()).hexdigest()
                self.post_hashes.add(content_hash)
                
            logger.info(f"✅ Загружено {len(self.post_hashes)} хешей из БД")
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки хешей: {e}")

    def search_content(self, max_posts=3):
        """Основной метод поиска контента"""
        logger.info("🔍 Начинаю поиск контента...")
        
        found_content = []
        
        for source in self.sources:
            try:
                if len(found_content) >= max_posts:
                    break
                    
                content_list = source()
                if content_list:
                    for content in content_list:
                        if self.is_unique_content(content) and len(found_content) < max_posts:
                            found_content.append(content)
                            content_hash = self.get_content_hash(content)
                            self.post_hashes.add(content_hash)
                            logger.info(f"✅ Найден пост: {content['title'][:50]}...")
            except Exception as e:
                logger.error(f"❌ Ошибка источника: {e}")
                continue
        
        logger.info(f"🎯 Найдено материалов: {len(found_content)}")
        return found_content

    def is_unique_content(self, content):
        """Проверяет уникальность контента"""
        content_hash = self.get_content_hash(content)
        
        if content_hash in self.post_hashes:
            return False
        
        if self.db_manager and self.is_content_in_db(content):
            return False
            
        return True

    def is_content_in_db(self, content):
        """Проверяет наличие контента в базе данных"""
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM found_content WHERE title LIKE %s', (f"%{content['title'][:30]}%",))
            result = cursor.fetchone()
            return result is not None
        except Exception as e:
            logger.error(f"❌ Ошибка проверки БД: {e}")
            return False

    def get_content_hash(self, content):
        """Создает хеш контента"""
        text = content['title'] + content['summary'][:100]
        return hashlib.md5(text.encode()).hexdigest()

    def parse_science_news(self):
        """Парсинг научных новостей"""
        try:
            articles = []
            url = "https://naked-science.ru/rss.xml"
            
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                feed = feedparser.parse(response.content)
                
                for entry in feed.entries[:5]:
                    title = entry.title
                    summary = entry.get('summary', '') or entry.get('description', '')
                    
                    if self.is_relevant_content(title + summary):
                        image_url = self.get_science_image()
                        formatted_post = self.format_science_post(title, summary)
                        
                        articles.append({
                            'title': title,
                            'summary': formatted_post,
                            'category': 'science',
                            'url': entry.link,
                            'image_url': image_url,
                            'found_date': datetime.now()
                        })
            
            return articles
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга научных новостей: {e}")
            return []

    def parse_tech_news(self):
        """Парсинг технологических новостей"""
        try:
            articles = []
            url = "https://3dnews.ru/news/rss/"
            
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                feed = feedparser.parse(response.content)
                
                for entry in feed.entries[:5]:
                    title = entry.title
                    summary = entry.get('summary', '') or entry.get('description', '')
                    
                    if self.is_relevant_content(title + summary):
                        image_url = self.get_tech_image()
                        formatted_post = self.format_tech_post(title, summary)
                        
                        articles.append({
                            'title': title,
                            'summary': formatted_post,
                            'category': 'technology',
                            'url': entry.link,
                            'image_url': image_url,
                            'found_date': datetime.now()
                        })
            
            return articles
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга техновостей: {e}")
            return []

    def parse_historical_facts(self):
        """Парсинг исторических фактов"""
        try:
            articles = []
            
            # Используем Wikipedia API
            url = "https://ru.wikipedia.org/w/api.php"
            params = {
                'action': 'query',
                'list': 'search',
                'srsearch': 'первый изобретение открытие',
                'format': 'json',
                'srlimit': 5
            }
            
            response = self.session.get(url, params=params, timeout=10)
            data = response.json()
            
            for item in data.get('query', {}).get('search', [])[:3]:
                title = item.get('title', '')
                
                if self.is_relevant_content(title):
                    full_content = self.get_wikipedia_content(title)
                    if full_content:
                        image_url = self.get_historical_image()
                        formatted_post = self.format_historical_post(title, full_content)
                        
                        articles.append({
                            'title': title,
                            'summary': formatted_post,
                            'category': 'history',
                            'url': f"https://ru.wikipedia.org/wiki/{title.replace(' ', '_')}",
                            'image_url': image_url,
                            'found_date': datetime.now()
                        })
            
            return articles
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга исторических фактов: {e}")
            return []

    def get_wikipedia_content(self, title):
        """Получает контент из Wikipedia"""
        try:
            url = "https://ru.wikipedia.org/w/api.php"
            params = {
                'action': 'query',
                'prop': 'extracts',
                'titles': title,
                'exintro': True,
                'explaintext': True,
                'format': 'json'
            }
            
            response = self.session.get(url, params=params, timeout=10)
            data = response.json()
            
            pages = data.get('query', {}).get('pages', {})
            for page_id, page_data in pages.items():
                extract = page_data.get('extract', '')
                if extract:
                    first_para = extract.split('\n')[0]
                    return first_para[:400] + '...'
            
            return ""
            
        except Exception as e:
            return ""

    def format_science_post(self, title, content):
        """Форматирует научный пост"""
        templates = [
            "🔬 НАУЧНОЕ ОТКРЫТИЕ\n\n{title}\n\n{content}\n\n💫 Это открытие меняет наши представления о мире\n\n#наука #открытие #исследование",
            "🌌 ПРОРЫВ В НАУКЕ\n\n{title}\n\n{content}\n\n🚀 Ученые совершили важный шаг\n\n#наука #прорыв #исследование"
        ]
        template = random.choice(templates)
        return template.format(title=title.upper(), content=content)

    def format_tech_post(self, title, content):
        """Форматирует технологический пост"""
        templates = [
            "⚡ ТЕХНОЛОГИЧЕСКАЯ РЕВОЛЮЦИЯ\n\n{title}\n\n{content}\n\n💡 Это изобретение меняет подход\n\n#технологии #инновации #будущее",
            "🤖 ИННОВАЦИОННАЯ РАЗРАБОТКА\n\n{title}\n\n{content}\n\n🚀 Прогресс не стоит на месте\n\n#технологии #разработка #инновации"
        ]
        template = random.choice(templates)
        return template.format(title=title.upper(), content=content)

    def format_historical_post(self, title, content):
        """Форматирует исторический пост"""
        templates = [
            "🏆 ИСТОРИЧЕСКОЕ СОБЫТИЕ\n\n{title}\n\n{content}\n\n📚 Это событие стало поворотным моментом\n\n#история #событие #память",
            "💡 ВЕЛИКОЕ ОТКРЫТИЕ\n\n{title}\n\n{content}\n\n🎯 Это достижение изменило ход истории\n\n#история #открытие #достижение"
        ]
        template = random.choice(templates)
        return template.format(title=title.upper(), content=content)

    def get_science_image(self):
        """Возвращает изображение для научных постов"""
        science_images = [
            'https://images.unsplash.com/photo-1532094349884-543bc11b234d?w=500&fit=crop',
            'https://images.unsplash.com/photo-1563089145-599997674d42?w=500&fit=crop',
        ]
        return random.choice(science_images)

    def get_tech_image(self):
        """Возвращает изображение для технологических постов"""
        tech_images = [
            'https://images.unsplash.com/photo-1518709268805-4e9042af2176?w=500&fit=crop',
            'https://images.unsplash.com/photo-1517077304055-6e89abbf09b0?w=500&fit=crop',
        ]
        return random.choice(tech_images)

    def get_historical_image(self):
        """Возвращает изображение для исторических постов"""
        historical_images = [
            'https://images.unsplash.com/photo-1481627834876-b7833e8f5570?w=500&fit=crop',
            'https://images.unsplash.com/photo-1589652717521-10c0d092dea9?w=500&fit=crop',
        ]
        return random.choice(historical_images)

    def is_relevant_content(self, text):
        """Проверяет релевантность контента"""
        keywords = [
            'первый', 'первое', 'изобретение', 'открытие', 'революция',
            'прорыв', 'рекорд', 'история', 'создан', 'разработан',
            'запущен', 'обнаружен', 'научный', 'технология'
        ]
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in keywords)

    def format_for_preview(self, content):
        """Форматирует контент для предпросмотра"""
        current_time = datetime.now()
        preview_text = f"📰 НОВЫЙ ПОСТ ДЛЯ ПУБЛИКАЦИИ\n\n{content['summary']}\n\n"
        
        if content.get('image_url'):
            preview_text += f"🖼️ Приложено изображение\n\n"
        
        preview_text += f"⏰ Найдено: {current_time.strftime('%H:%M %d.%m.%Y')}"
        
        return preview_text

def setup_content_finder(db_manager=None):
    """Инициализация системы поиска контента"""
    return ContentFinder(db_manager)
