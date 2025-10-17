# content_finder.py
import logging
import requests
from datetime import datetime
import random
import hashlib
from bs4 import BeautifulSoup
import re
import json

logger = logging.getLogger(__name__)

class ContentFinder:
    def __init__(self, db_manager=None):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        self.db_manager = db_manager
        self.post_hashes = set()
        self.load_existing_hashes()
        
        self.sources = [
            self.parse_science_news,
            self.parse_tech_news,
            self.parse_historical_facts,
            self.generate_ai_content
        ]

    def load_existing_hashes(self):
        """Загружает существующие хеши из БД при инициализации"""
        if self.db_manager:
            try:
                conn = self.db_manager.get_connection()
                cursor = conn.cursor()
                cursor.execute('SELECT title, content FROM found_content')
                existing_posts = cursor.fetchall()
                
                for title, content in existing_posts:
                    text = title + content
                    content_hash = hashlib.md5(text.encode()).hexdigest()
                    self.post_hashes.add(content_hash)
                    
                logger.info(f"✅ Загружено {len(self.post_hashes)} существующих хешей из БД")
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки хешей из БД: {e}")

    def search_content(self, max_posts=3):
        """Основной метод поиска контента"""
        logger.info("🔍 Начинаю поиск уникального контента...")
        
        found_content = []
        attempts = 0
        max_attempts = 15  # Увеличим количество попыток
        
        while len(found_content) < max_posts and attempts < max_attempts:
            attempts += 1
            logger.info(f"🔍 Попытка {attempts}/{max_attempts}")
            
            for source in self.sources:
                try:
                    content_list = source()
                    if content_list:
                        for content in content_list:
                            if self.is_truly_unique_content(content) and len(found_content) < max_posts:
                                found_content.append(content)
                                content_hash = self.get_content_hash(content)
                                self.post_hashes.add(content_hash)
                                logger.info(f"✅ Найден уникальный пост: {content['title'][:50]}...")
                            
                            if len(found_content) >= max_posts:
                                break
                
                except Exception as e:
                    logger.error(f"❌ Ошибка источника {source.__name__}: {e}")
                    continue
                
                if len(found_content) >= max_posts:
                    break
        
        logger.info(f"🎯 Найдено уникальных материалов: {len(found_content)}")
        return found_content

    def is_truly_unique_content(self, content):
        """Проверяет уникальность контента через хеши и БД"""
        content_hash = self.get_content_hash(content)
        
        # Проверка в памяти
        if content_hash in self.post_hashes:
            logger.info(f"🚫 Пост уже в памяти: {content['title'][:30]}...")
            return False
        
        # Проверка в БД
        if self.db_manager and self.is_content_in_db(content):
            logger.info(f"🚫 Пост уже в БД: {content['title'][:30]}...")
            return False
            
        return True

    def is_content_in_db(self, content):
        """Проверяет наличие контента в базе данных"""
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            # Ищем похожие посты по заголовку
            cursor.execute('''
                SELECT id FROM found_content 
                WHERE title = %s OR content LIKE %s
            ''', (content['title'], f"%{content['title'][:50]}%"))
            
            result = cursor.fetchone()
            return result is not None
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки БД: {e}")
            return False

    def get_content_hash(self, content):
        """Создает более надежный хеш контента"""
        # Используем заголовок и начало контента для лучшей уникальности
        text = content['title'] + content['summary'][:200]
        return hashlib.md5(text.encode()).hexdigest()

    # Остальные методы остаются без изменений...
    def parse_science_news(self):
        """Парсинг научных новостей с улучшенной уникальностью"""
        try:
            # Naked Science
            url = "https://naked-science.ru"
            response = self.session.get(url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            articles = []
            news_items = soup.find_all('article', class_='news')[:5]
            
            for item in news_items:
                try:
                    title_elem = item.find('h2') or item.find('a')
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text().strip()
                    
                    # Пропускаем нерелевантные посты
                    if not self.is_relevant_content(title):
                        continue
                    
                    # Ищем описание
                    description_elem = item.find('p') or item.find('div', class_='description')
                    description = description_elem.get_text().strip() if description_elem else ""
                    
                    full_text = self.get_article_content(item)
                    formatted_post = self.format_science_post(title, full_text or description)
                    
                    articles.append({
                        'title': title,
                        'summary': formatted_post,
                        'category': 'science',
                        'url': url,
                        'image_url': self.get_science_image(),
                        'found_date': datetime.now()
                    })
                    
                except Exception as e:
                    continue
                    
            return articles
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга научных новостей: {e}")
            return []

    def is_relevant_content(self, text):
        """Улучшенная проверка релевантности контента"""
        keywords = [
            'первый', 'первое', 'изобретение', 'открытие', 'революция',
            'прорыв', 'рекорд', 'история', 'создан', 'разработан',
            'запущен', 'обнаружен', 'научный', 'технология', 'инновац',
            'исторический', 'впервые', 'новая технология', 'прорыв',
            'новая эра', 'переломный момент', 'знаковое', 'эпохальное'
        ]
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in keywords)

# Остальные методы класса остаются без изменений...

def setup_content_finder(db_manager=None):
    """Инициализация системы поиска контента с передачей db_manager"""
    return ContentFinder(db_manager)
