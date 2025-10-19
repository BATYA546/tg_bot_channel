# content_finder.py
import logging
import requests
from datetime import datetime
import random
import hashlib
from bs4 import BeautifulSoup
import re
import json
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
        self.load_existing_hashes()
        
        # Реальные источники для парсинга
        self.sources = [
            self.parse_google_news,
            self.parse_science_news,
            self.parse_tech_news,
            self.parse_historical_facts,
            self.parse_wikipedia_firsts
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
                    text = title + content[:200]
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
        max_attempts = 8
        
        while len(found_content) < max_posts and attempts < max_attempts:
            attempts += 1
            logger.info(f"🔍 Попытка {attempts}/{max_attempts}")
            
            random.shuffle(self.sources)
            
            for source in self.sources:
                try:
                    if len(found_content) >= max_posts:
                        break
                        
                    logger.info(f"📡 Проверяем источник: {source.__name__}")
                    content_list = source()
                    
                    if content_list:
                        for content in content_list:
                            if self.is_truly_unique_content(content) and len(found_content) < max_posts:
                                # Улучшаем изображение перед сохранением
                                if not content.get('image_url') or 'unsplash' in content.get('image_url', ''):
                                    content['image_url'] = self.get_relevant_image(content['title'], content['summary'])
                                
                                found_content.append(content)
                                content_hash = self.get_content_hash(content)
                                self.post_hashes.add(content_hash)
                                logger.info(f"✅ Найден уникальный пост: {content['title'][:50]}...")
                            
                            if len(found_content) >= max_posts:
                                break
                
                except Exception as e:
                    logger.error(f"❌ Ошибка источника {source.__name__}: {e}")
                    continue
                
            time.sleep(2)
        
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
            
            search_term = content['title'][:40]
            cursor.execute('''
                SELECT id FROM found_content 
                WHERE title LIKE %s OR content LIKE %s
            ''', (f"%{search_term}%", f"%{search_term}%"))
            
            result = cursor.fetchone()
            return result is not None
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки БД: {e}")
            return False

    def get_content_hash(self, content):
        """Создает хеш контента"""
        text = content['title'] + content['summary'][:150]
        return hashlib.md5(text.encode()).hexdigest()

    def parse_google_news(self):
        """Парсинг Google News по тематике первых событий"""
        try:
            articles = []
            
            keywords = [
                "первое изобретение", "первое открытие", "революционное открытие",
                "историческое открытие", "прорыв в науке", "первый в мире",
                "впервые в истории", "новая эра", "знаковое открытие"
            ]
            
            for keyword in random.sample(keywords, 3):
                try:
                    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(keyword)}&hl=ru&gl=RU&ceid=RU:ru"
                    
                    response = self.session.get(url, timeout=15)
                    if response.status_code == 200:
                        feed = feedparser.parse(response.content)
                        
                        for entry in feed.entries[:5]:
                            title = entry.title
                            summary = entry.get('summary', '') or entry.get('description', '')
                            link = entry.link
                            
                            if self.is_relevant_content(title + summary):
                                full_content = self.get_article_content(link)
                                image_url = self.extract_image_from_article(link) or self.get_relevant_image(title, summary)
                                
                                formatted_post = self.format_news_post(title, full_content or summary, keyword)
                                
                                articles.append({
                                    'title': title,
                                    'summary': formatted_post,
                                    'category': 'news',
                                    'url': link,
                                    'image_url': image_url,
                                    'found_date': datetime.now()
                                })
                                
                                if len(articles) >= 3:
                                    return articles
                    
                    time.sleep(2)
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка парсинга ключевого слова {keyword}: {e}")
                    continue
                    
            return articles
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга Google News: {e}")
            return []

    def parse_science_news(self):
        """Парсинг научных новостей"""
        try:
            articles = []
            
            science_feeds = [
                "https://naked-science.ru/rss.xml",
                "https://scientificrussia.ru/rss",
                "https://elementy.ru/rss",
                "https://www.popmech.ru/rss/"
            ]
            
            for feed_url in random.sample(science_feeds, 2):
                try:
                    response = self.session.get(feed_url, timeout=15)
                    if response.status_code == 200:
                        feed = feedparser.parse(response.content)
                        
                        for entry in feed.entries[:5]:
                            title = entry.title
                            summary = entry.get('summary', '') or entry.get('description', '')
                            link = entry.link
                            
                            if self.is_relevant_content(title + summary):
                                image_url = self.extract_image_from_article(link) or self.get_relevant_image(title, summary)
                                
                                formatted_post = self.format_science_post(title, summary)
                                
                                articles.append({
                                    'title': title,
                                    'summary': formatted_post,
                                    'category': 'science',
                                    'url': link,
                                    'image_url': image_url,
                                    'found_date': datetime.now()
                                })
                                
                                if len(articles) >= 3:
                                    return articles
                    
                    time.sleep(2)
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка парсинга ленты {feed_url}: {e}")
                    continue
                    
            return articles
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга научных новостей: {e}")
            return []

    def parse_tech_news(self):
        """Парсинг технологических новостей"""
        try:
            articles = []
            
            tech_feeds = [
                "https://3dnews.ru/news/rss/",
                "https://hi-news.ru/feed",
                "https://www.ixbt.com/export/news.rss",
                "https://habr.com/ru/rss/articles/"
            ]
            
            for feed_url in random.sample(tech_feeds, 2):
                try:
                    response = self.session.get(feed_url, timeout=15)
                    if response.status_code == 200:
                        feed = feedparser.parse(response.content)
                        
                        for entry in feed.entries[:5]:
                            title = entry.title
                            summary = entry.get('summary', '') or entry.get('description', '')
                            link = entry.link
                            
                            if self.is_relevant_content(title + summary):
                                image_url = self.extract_image_from_article(link) or self.get_relevant_image(title, summary)
                                
                                formatted_post = self.format_tech_post(title, summary)
                                
                                articles.append({
                                    'title': title,
                                    'summary': formatted_post,
                                    'category': 'technology',
                                    'url': link,
                                    'image_url': image_url,
                                    'found_date': datetime.now()
                                })
                                
                                if len(articles) >= 3:
                                    return articles
                    
                    time.sleep(2)
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка парсинга ленты {feed_url}: {e}")
                    continue
                    
            return articles
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга технологических новостей: {e}")
            return []

    def parse_historical_facts(self):
        """Парсинг исторических фактов"""
        try:
            articles = []
            
            historical_sources = [
                self.parse_historical_events_api,
                self.parse_wikipedia_today_in_history
            ]
            
            for source in historical_sources:
                try:
                    content = source()
                    if content:
                        articles.extend(content)
                        if len(articles) >= 2:
                            break
                except Exception as e:
                    logger.error(f"❌ Ошибка исторического источника: {e}")
                    continue
            
            return articles
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга исторических фактов: {e}")
            return []

    def parse_historical_events_api(self):
        """Парсинг исторических событий через API"""
        try:
            articles = []
            
            today = datetime.now()
            url = f"http://history.muffinlabs.com/date/{today.month}/{today.day}"
            
            response = self.session.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                
                events = data.get('data', {}).get('Events', [])
                for event in events[:5]:
                    year = event.get('year', '')
                    text = event.get('text', '')
                    
                    if self.is_relevant_content(text):
                        image_url = self.get_historical_image_for_event(text, year)
                        
                        formatted_post = self.format_historical_post(f"Событие {year} года", text, year)
                        
                        articles.append({
                            'title': f"Историческое событие {year} года",
                            'summary': formatted_post,
                            'category': 'history',
                            'url': data.get('url', ''),
                            'image_url': image_url,
                            'found_date': datetime.now()
                        })
                        
                        if len(articles) >= 2:
                            break
            
            return articles
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга исторических событий API: {e}")
            return []

    def parse_wikipedia_today_in_history(self):
        """Парсинг 'сегодня в истории' из Wikipedia"""
        try:
            articles = []
            
            today = datetime.now()
            url = "https://ru.wikipedia.org/w/api.php"
            params = {
                'action': 'query',
                'prop': 'extracts',
                'titles': f"{today.day} {self.get_month_name(today.month)}",
                'exintro': True,
                'explaintext': True,
                'format': 'json'
            }
            
            response = self.session.get(url, params=params, timeout=15)
            data = response.json()
            
            pages = data.get('query', {}).get('pages', {})
            for page_id, page_data in pages.items():
                extract = page_data.get('extract', '')
                if extract and self.is_relevant_content(extract):
                    title = f"События {today.day} {self.get_month_name(today.month)}"
                    image_url = self.get_wikipedia_image(title)
                    
                    formatted_post = self.format_historical_post(title, extract[:500] + "...", "")
                    
                    articles.append({
                        'title': title,
                        'summary': formatted_post,
                        'category': 'history',
                        'url': f"https://ru.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}",
                        'image_url': image_url,
                        'found_date': datetime.now()
                    })
            
            return articles
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга Wikipedia сегодня в истории: {e}")
            return []

    def parse_wikipedia_firsts(self):
        """Парсинг первых событий из Википедии"""
        try:
            articles = []
            
            search_queries = [
                "первый искусственный спутник", "первый полет в космос", 
                "первое изобретение", "революционное открытие", "первая фотография",
                "первый компьютер", "первый телефон", "первый автомобиль"
            ]
            
            for query in random.sample(search_queries, 3):
                try:
                    url = "https://ru.wikipedia.org/w/api.php"
                    params = {
                        'action': 'query',
                        'list': 'search',
                        'srsearch': query,
                        'format': 'json',
                        'srlimit': 3
                    }
                    
                    response = self.session.get(url, params=params, timeout=15)
                    data = response.json()
                    
                    for item in data.get('query', {}).get('search', []):
                        title = item.get('title', '')
                        
                        if self.is_relevant_content(title):
                            full_content = self.get_wikipedia_content(title)
                            if full_content:
                                image_url = self.get_wikipedia_image(title)
                                
                                formatted_post = self.format_wikipedia_post(title, full_content, query)
                                
                                articles.append({
                                    'title': title,
                                    'summary': formatted_post,
                                    'category': 'wikipedia',
                                    'url': f"https://ru.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}",
                                    'image_url': image_url,
                                    'found_date': datetime.now()
                                })
                                
                                if len(articles) >= 2:
                                    return articles
                    
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка парсинга запроса {query}: {e}")
                    continue
                    
            return articles
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга Wikipedia: {e}")
            return []

    def get_month_name(self, month):
        """Возвращает название месяца на русском"""
        months = {
            1: "января", 2: "февраля", 3: "марта", 4: "апреля",
            5: "мая", 6: "июня", 7: "июля", 8: "августа", 
            9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
        }
        return months.get(month, "")

    def get_article_content(self, url):
        """Получает контент статьи"""
        try:
            response = self.session.get(url, timeout=15)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            for element in soup(['script', 'style', 'nav', 'header', 'footer']):
                element.decompose()
            
            content_selectors = [
                'article', '.article-content', '.post-content', 
                '.entry-content', '.content', 'main'
            ]
            
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    text = content_elem.get_text(strip=True)
                    if len(text) > 200:
                        return text[:500] + '...'
            
            paragraphs = soup.find_all('p')
            text = ' '.join([p.get_text(strip=True) for p in paragraphs[:5]])
            return text[:500] + '...' if len(text) > 500 else text
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения контента статьи: {e}")
            return ""

    def extract_image_from_article(self, url):
        """Извлекает изображение из статьи"""
        try:
            response = self.session.get(url, timeout=15)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            image_selectors = [
                'meta[property="og:image"]',
                'meta[name="twitter:image"]',
                '.article-image img',
                '.post-image img',
                '.entry-content img',
                'article img'
            ]
            
            for selector in image_selectors:
                img_elem = soup.select_one(selector)
                if img_elem:
                    if img_elem.get('content'):
                        image_url = img_elem['content']
                    else:
                        image_url = img_elem.get('src', '')
                    
                    if image_url and image_url.startswith('http'):
                        if image_url.startswith('//'):
                            image_url = 'https:' + image_url
                        elif image_url.startswith('/'):
                            from urllib.parse import urljoin
                            image_url = urljoin(url, image_url)
                        
                        return image_url
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка извлечения изображения: {e}")
            return None

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
            
            response = self.session.get(url, params=params, timeout=15)
            data = response.json()
            
            pages = data.get('query', {}).get('pages', {})
            for page_id, page_data in pages.items():
                extract = page_data.get('extract', '')
                if extract:
                    paragraphs = [p for p in extract.split('\n') if p.strip()]
                    if paragraphs:
                        return paragraphs[0][:600] + '...' if len(paragraphs[0]) > 600 else paragraphs[0]
            
            return ""
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения контента Wikipedia: {e}")
            return ""

    def get_wikipedia_image(self, title):
        """Получает изображение из Wikipedia"""
        try:
            url = "https://ru.wikipedia.org/w/api.php"
            params = {
                'action': 'query',
                'prop': 'pageimages',
                'titles': title,
                'pithumbsize': 500,
                'format': 'json'
            }
            
            response = self.session.get(url, params=params, timeout=15)
            data = response.json()
            
            pages = data.get('query', {}).get('pages', {})
            for page_id, page_data in pages.items():
                thumbnail = page_data.get('thumbnail')
                if thumbnail:
                    return thumbnail.get('source', '')
            
            return self.get_relevant_image(title, "")
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения изображения Wikipedia: {e}")
            return self.get_default_image()

    def get_relevant_image(self, title, content):
        """Находит релевантное изображение по заголовку и содержанию"""
        try:
            text = (title + ' ' + content).lower()
            
            # Космос и астрономия
            if any(word in text for word in ['космос', 'спутник', 'ракета', 'гагарин', 'терешкова', 'космонавт', 'орбита', 'планета']):
                return self.get_space_image()
            
            # Наука и исследования
            elif any(word in text for word in ['наука', 'ученый', 'открытие', 'исследование', 'лаборатория', 'эксперимент']):
                return self.get_science_image()
            
            # Технологии
            elif any(word in text for word in ['технология', 'компьютер', 'смартфон', 'интернет', 'программирование', 'софт']):
                return self.get_tech_image()
            
            # История
            elif any(word in text for word in ['история', 'исторический', 'древний', 'археология', 'прошлое', 'событие']):
                return self.get_historical_image()
            
            # Медицина
            elif any(word in text for word in ['медицина', 'врач', 'лекарство', 'болезнь', 'здоровье', 'вирус']):
                return self.get_medical_image()
            
            # Изобретения
            elif any(word in text for word in ['изобретение', 'патент', 'инновация', 'разработка', 'создал']):
                return self.get_invention_image()
            
            else:
                return self.get_thematic_image(text)
                
        except Exception as e:
            logger.error(f"❌ Ошибка поиска релевантного изображения: {e}")
            return self.get_default_image()

    def get_space_image(self):
        """Изображения космоса"""
        space_images = [
            'https://images.unsplash.com/photo-1446776653964-20c1d3a81b06?w=800&fit=crop',
            'https://images.unsplash.com/photo-1462331940025-496dfbfc7564?w=800&fit=crop',
            'https://images.unsplash.com/photo-1502136969935-8d8eef54d77b?w=800&fit=crop',
            'https://images.unsplash.com/photo-1464802686167-b939a6910659?w=800&fit=crop',
        ]
        return random.choice(space_images)

    def get_science_image(self):
        """Научные изображения"""
        science_images = [
            'https://images.unsplash.com/photo-1532094349884-543bc11b234d?w=800&fit=crop',
            'https://images.unsplash.com/photo-1563089145-599997674d42?w=800&fit=crop',
            'https://images.unsplash.com/photo-1554475900-0a0350e3fc7b?w=800&fit=crop',
            'https://images.unsplash.com/photo-1507413245164-6160d8298b31?w=800&fit=crop',
        ]
        return random.choice(science_images)

    def get_tech_image(self):
        """Технологические изображения"""
        tech_images = [
            'https://images.unsplash.com/photo-1518709268805-4e9042af2176?w=800&fit=crop',
            'https://images.unsplash.com/photo-1517077304055-6e89abbf09b0?w=800&fit=crop',
            'https://images.unsplash.com/photo-1542831371-29b0f74f9713?w=800&fit=crop',
            'https://images.unsplash.com/photo-1550751827-4bd374c3f58b?w=800&fit=crop',
        ]
        return random.choice(tech_images)

    def get_historical_image(self):
        """Исторические изображения"""
        historical_images = [
            'https://images.unsplash.com/photo-1481627834876-b7833e8f5570?w=800&fit=crop',
            'https://images.unsplash.com/photo-1589652717521-10c0d092dea9?w=800&fit=crop',
            'https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&fit=crop',
            'https://images.unsplash.com/photo-1505664194779-8beaceb93744?w=800&fit=crop',
        ]
        return random.choice(historical_images)

    def get_medical_image(self):
        """Медицинские изображения"""
        medical_images = [
            'https://images.unsplash.com/photo-1559757148-5c350d0d3c56?w=800&fit=crop',
            'https://images.unsplash.com/photo-1576091160399-112ba8d25d1f?w=800&fit=crop',
            'https://images.unsplash.com/photo-1559757175-0eb30cd8c063?w=800&fit=crop',
        ]
        return random.choice(medical_images)

    def get_invention_image(self):
        """Изображения изобретений"""
        invention_images = [
            'https://images.unsplash.com/photo-1506744038136-46273834b3fb?w=800&fit=crop',
            'https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=800&fit=crop',
            'https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?w=800&fit=crop',
        ]
        return random.choice(invention_images)

    def get_thematic_image(self, text):
        """Тематическое изображение на основе текста"""
        if any(word in text for word in ['первый', 'рекорд', 'достижение']):
            achievement_images = [
                'https://images.unsplash.com/photo-1563089145-599997674d42?w=800&fit=crop',
                'https://images.unsplash.com/photo-1517048676732-d65bc937f952?w=800&fit=crop',
            ]
            return random.choice(achievement_images)
        else:
            return self.get_default_image()

    def get_default_image(self):
        """Изображение по умолчанию"""
        default_images = [
            'https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&fit=crop',
            'https://images.unsplash.com/photo-1481627834876-b7833e8f5570?w=800&fit=crop',
        ]
        return random.choice(default_images)

    def get_historical_image_for_event(self, event_text, year):
        """Специфичное изображение для исторического события"""
        text = event_text.lower()
        
        if any(word in text for word in ['война', 'сражение', 'битва']):
            return 'https://images.unsplash.com/photo-1547234931-12c622f4fc37?w=800&fit=crop'
        elif any(word in text for word in ['революция', 'восстание']):
            return 'https://images.unsplash.com/photo-1505664194779-8beaceb93744?w=800&fit=crop'
        else:
            return self.get_historical_image()

    def format_news_post(self, title, content, keyword):
        """Форматирует новостной пост"""
        templates = [
            "📰 АКТУАЛЬНАЯ НОВОСТЬ\n\n{title}\n\n{content}\n\n🔍 Найдено по запросу: {keyword}\n\n#новости #открытие #актуальное",
            "🌍 ВАЖНОЕ СОБЫТИЕ\n\n{title}\n\n{content}\n\n🔍 Найдено по запросу: {keyword}\n\n#событие #важно #новости"
        ]
        template = random.choice(templates)
        return template.format(title=title.upper(), content=content, keyword=keyword)

    def format_science_post(self, title, content):
        """Форматирует научный пост"""
        templates = [
            "🔬 НАУЧНОЕ ОТКРЫТИЕ\n\n{title}\n\n{content}\n\n💫 Это открытие меняет наши представления о мире\n\n#наука #открытие #исследование",
            "🌌 ПРОРЫВ В НАУКЕ\n\n{title}\n\n{content}\n\n🚀 Ученые совершили важный шаг в понимании законов природы\n\n#наука #прорыв #исследование"
        ]
        template = random.choice(templates)
        return template.format(title=title.upper(), content=content)

    def format_tech_post(self, title, content):
        """Форматирует технологический пост"""
        templates = [
            "⚡ ТЕХНОЛОГИЧЕСКАЯ РЕВОЛЮЦИЯ\n\n{title}\n\n{content}\n\n💡 Это изобретение меняет подход к решению задач\n\n#технологии #инновации #будущее",
            "🤖 ИННОВАЦИОННАЯ РАЗРАБОТКА\n\n{title}\n\n{content}\n\n🚀 Прогресс не стоит на месте\n\n#технологии #разработка #инновации"
        ]
        template = random.choice(templates)
        return template.format(title=title.upper(), content=content)

    def format_historical_post(self, title, content, year):
        """Форматирует исторический пост"""
        templates = [
            "🏆 ИСТОРИЧЕСКОЕ СОБЫТИЕ\n\n{title}\n\n{content}\n\n📅 Год: {year}\n\n📚 Это событие стало поворотным моментом в истории\n\n#история #событие #память",
            "💡 ВЕЛИКОЕ ОТКРЫТИЕ\n\n{title}\n\n{content}\n\n📅 Год: {year}\n\n🎯 Это достижение изменило ход истории\n\n#история #открытие #достижение"
        ]
        template = random.choice(templates)
        return template.format(title=title.upper(), content=content, year=year)

    def format_wikipedia_post(self, title, content, query):
        """Форматирует Wikipedia пост"""
        templates = [
            "🌍 ИСТОРИЧЕСКИЙ ФАКТ\n\n{title}\n\n{content}\n\n🔍 Найдено по запросу: {query}\n\n📚 Это событие стало важной вехой\n\n#история #факт #память",
            "💫 ПЕРВЫЙ ШАГ\n\n{title}\n\n{content}\n\n🔍 Найдено по запросу: {query}\n\n🚀 Это достижение открыло новые возможности\n\n#первый #история #достижение"
        ]
        template = random.choice(templates)
        return template.format(title=title.upper(), content=content, query=query)

    def is_relevant_content(self, text):
        """Проверяет релевантность контента"""
        keywords = [
            'первый', 'первое', 'первая', 'впервые', 'впервы',
            'изобретение', 'открытие', 'революция', 'прорыв',
            'рекорд', 'история', 'создан', 'разработан', 'запущен',
            'обнаружен', 'начало', 'возникновение', 'появление',
            'основание', 'создание', 'изобрет', 'открыт', 'новая эра',
            'переломный момент', 'знаковое', 'эпохальное', 'пионер',
            'первооткрыватель', 'новатор', 'инновац'
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
    """Инициализация системы поиска контента с передачей db_manager"""
    return ContentFinder(db_manager)
