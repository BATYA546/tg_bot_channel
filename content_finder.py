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
            self.parse_wikipedia_firsts,
            self.parse_historical_firsts,
            self.parse_science_firsts,
            self.parse_tech_firsts
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
        max_attempts = 8  # Уменьшим количество попыток
        
        while len(found_content) < max_posts and attempts < max_attempts:
            attempts += 1
            logger.info(f"🔍 Попытка {attempts}/{max_attempts}")
            
            # Перемешиваем источники для разнообразия
            random.shuffle(self.sources)
            
            for source in self.sources:
                try:
                    if len(found_content) >= max_posts:
                        break
                        
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
                
            # Небольшая задержка между попытками
            time.sleep(1)
        
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
            
            # Более гибкая проверка - ищем похожие заголовки
            cursor.execute('''
                SELECT id FROM found_content 
                WHERE title LIKE %s OR content LIKE %s
            ''', (f"%{content['title'][:30]}%", f"%{content['title'][:20]}%"))
            
            result = cursor.fetchone()
            return result is not None
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки БД: {e}")
            return False

    def get_content_hash(self, content):
        """Создает хеш контента"""
        text = content['title'] + content['summary'][:100]
        return hashlib.md5(text.encode()).hexdigest()

    def parse_wikipedia_firsts(self):
        """Парсинг первых событий из Википедии"""
        try:
            articles = []
            
            # Список тем для поиска первых событий
            search_queries = [
                "первый в мире",
                "первое изобретение", 
                "первое открытие",
                "первый полет",
                "первая фотография",
                "первый компьютер",
                "первый телефон",
                "первый автомобиль",
                "первый фильм",
                "первая книга"
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
                    
                    response = self.session.get(url, params=params, timeout=10)
                    data = response.json()
                    
                    for item in data.get('query', {}).get('search', []):
                        title = item.get('title', '')
                        snippet = item.get('snippet', '')
                        
                        # Очищаем HTML теги из сниппета
                        soup = BeautifulSoup(snippet, 'html.parser')
                        clean_snippet = soup.get_text()
                        
                        if self.is_relevant_content(title + clean_snippet):
                            full_content = self.get_wikipedia_content(title)
                            if full_content and len(full_content) > 50:
                                formatted_post = self.format_wikipedia_post(title, full_content)
                                
                                articles.append({
                                    'title': title,
                                    'summary': formatted_post,
                                    'category': 'history',
                                    'url': f"https://ru.wikipedia.org/wiki/{title.replace(' ', '_')}",
                                    'image_url': self.get_wikipedia_image(title),
                                    'found_date': datetime.now()
                                })
                                
                                if len(articles) >= 2:
                                    break
                    
                    time.sleep(1)  # Задержка между запросами
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка парсинга запроса {query}: {e}")
                    continue
                    
            return articles
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга Wikipedia: {e}")
            return []

    def parse_historical_firsts(self):
        """Парсинг исторических первых событий"""
        try:
            # Используем исторические API и сайты
            articles = []
            
            # Попробуем получить данные с исторических сайтов
            sources = [
                self.parse_russian_history,
                self.parse_science_history
            ]
            
            for source in sources:
                try:
                    content = source()
                    if content:
                        articles.extend(content)
                        if len(articles) >= 2:
                            break
                except Exception as e:
                    logger.error(f"❌ Ошибка источника истории: {e}")
                    continue
            
            return articles
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга исторических событий: {e}")
            return []

    def parse_russian_history(self):
        """Парсинг русской истории - первые события"""
        try:
            # Исторические события России
            url = "https://histrf.ru/read/articles"
            response = self.session.get(url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            articles = []
            
            # Ищем статьи с упоминанием первых событий
            news_items = soup.find_all('article', class_=re.compile('article|news|item'))[:5]
            
            for item in news_items:
                try:
                    title_elem = item.find('h2') or item.find('h3') or item.find('a')
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text().strip()
                    
                    if self.is_relevant_content(title):
                        # Получаем описание
                        desc_elem = item.find('p') or item.find('div', class_=re.compile('desc|text|content'))
                        description = desc_elem.get_text().strip() if desc_elem else ""
                        
                        formatted_post = self.format_historical_post(title, description)
                        
                        articles.append({
                            'title': title,
                            'summary': formatted_post,
                            'category': 'history',
                            'url': "https://histrf.ru",
                            'image_url': self.get_historical_image(),
                            'found_date': datetime.now()
                        })
                        
                except Exception as e:
                    continue
                    
            return articles
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга русской истории: {e}")
            return []

    def parse_science_firsts(self):
        """Парсинг научных первых открытий"""
        try:
            articles = []
            
            # Популярные научные сайты
            science_sources = [
                "https://naked-science.ru",
                "https://elementy.ru",
                "https://scientificrussia.ru"
            ]
            
            for source_url in random.sample(science_sources, 2):
                try:
                    response = self.session.get(source_url, timeout=10)
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Ищем статьи
                    items = soup.find_all('article')[:3] or soup.find_all('div', class_=re.compile('article|news|post'))[:3]
                    
                    for item in items:
                        try:
                            title_elem = item.find('h2') or item.find('h3') or item.find('a')
                            if not title_elem:
                                continue
                            
                            title = title_elem.get_text().strip()
                            
                            if self.is_relevant_content(title):
                                desc_elem = item.find('p') or item.find('div', class_=re.compile('desc|text|excerpt'))
                                description = desc_elem.get_text().strip() if desc_elem else ""
                                
                                formatted_post = self.format_science_post(title, description)
                                
                                articles.append({
                                    'title': title,
                                    'summary': formatted_post,
                                    'category': 'science',
                                    'url': source_url,
                                    'image_url': self.get_science_image(),
                                    'found_date': datetime.now()
                                })
                                
                                if len(articles) >= 2:
                                    break
                                    
                        except Exception as e:
                            continue
                            
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка парсинга {source_url}: {e}")
                    continue
                    
            return articles
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга научных новостей: {e}")
            return []

    def parse_tech_firsts(self):
        """Парсинг технологических первых изобретений"""
        try:
            articles = []
            
            # Технологические сайты
            tech_sources = [
                "https://3dnews.ru",
                "https://hi-news.ru",
                "https://www.popmech.ru"
            ]
            
            for source_url in random.sample(tech_sources, 2):
                try:
                    response = self.session.get(source_url, timeout=10)
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Ищем технологические новости
                    items = soup.find_all('article')[:3] or soup.find_all('div', class_=re.compile('news|item|post'))[:3]
                    
                    for item in items:
                        try:
                            title_elem = item.find('h2') or item.find('h3') or item.find('a')
                            if not title_elem:
                                continue
                            
                            title = title_elem.get_text().strip()
                            
                            if self.is_relevant_content(title):
                                desc_elem = item.find('p') or item.find('div', class_=re.compile('desc|text|excerpt'))
                                description = desc_elem.get_text().strip() if desc_elem else ""
                                
                                formatted_post = self.format_tech_post(title, description)
                                
                                articles.append({
                                    'title': title,
                                    'summary': formatted_post,
                                    'category': 'technology',
                                    'url': source_url,
                                    'image_url': self.get_tech_image(),
                                    'found_date': datetime.now()
                                })
                                
                                if len(articles) >= 2:
                                    break
                                    
                        except Exception as e:
                            continue
                            
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка парсинга {source_url}: {e}")
                    continue
                    
            return articles
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга технологических новостей: {e}")
            return []

    def parse_science_history(self):
        """Парсинг истории науки"""
        try:
            # Альтернативный источник исторических фактов
            articles = []
            
            # Создаем контент на основе известных исторических фактов
            historical_facts = [
                {
                    'title': 'Первый искусственный спутник Земли',
                    'content': 'Запуск первого в мире искусственного спутника Земли состоялся 4 октября 1957 года. Спутник ПС-1 был запущен с космодрома Байконур и открыл космическую эру человечества.',
                    'category': 'space'
                },
                {
                    'title': 'Первая фотография в истории',
                    'content': 'Первая в истории фотография была сделана Жозефом Нисефором Ньепсом в 1826 году. Снимок «Вид из окна в Ле Гра» создавался в течение 8 часов экспозиции.',
                    'category': 'photography'
                },
                {
                    'title': 'Первый полет человека в космос',
                    'content': '12 апреля 1961 года Юрий Гагарин стал первым человеком, совершившим полет в космос на корабле «Восток-1». Полет длился 108 минут.',
                    'category': 'space'
                },
                {
                    'title': 'Первое использование анестезии',
                    'content': '16 октября 1846 года Уильям Мортон впервые публично продемонстрировал применение эфирной анестезии во время операции в Массачусетской больнице.',
                    'category': 'medicine'
                },
                {
                    'title': 'Первый телефонный разговор',
                    'content': '10 марта 1876 года Александр Белл произнес первые слова по телефону: «Мистер Ватсон, идите сюда, вы мне нужны».',
                    'category': 'technology'
                }
            ]
            
            for fact in random.sample(historical_facts, 2):
                formatted_post = self.format_historical_post(fact['title'], fact['content'])
                
                articles.append({
                    'title': fact['title'],
                    'summary': formatted_post,
                    'category': fact['category'],
                    'url': '',
                    'image_url': self.get_category_image(fact['category']),
                    'found_date': datetime.now()
                })
            
            return articles
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания исторического контента: {e}")
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
                    # Берем первый абзац
                    first_para = extract.split('\n')[0]
                    return first_para[:500] + '...' if len(first_para) > 500 else first_para
            
            return ""
            
        except Exception as e:
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
            
            response = self.session.get(url, params=params, timeout=10)
            data = response.json()
            
            pages = data.get('query', {}).get('pages', {})
            for page_id, page_data in pages.items():
                thumbnail = page_data.get('thumbnail')
                if thumbnail:
                    return thumbnail.get('source', '')
            
            return self.get_category_image('history')
            
        except Exception as e:
            return self.get_category_image('history')

    def format_wikipedia_post(self, title, content):
        """Форматирует Wikipedia пост"""
        templates = [
            "🌍 ИСТОРИЧЕСКОЕ СОБЫТИЕ\n\n{title}\n\n{content}\n\n📚 Это событие стало важной вехой в истории человечества.\n\n#история #событие #память",
            
            "💫 ПЕРВЫЙ ШАГ\n\n{title}\n\n{content}\n\n🚀 Это достижение открыло новые возможности для развития цивилизации.\n\n#первый #история #достижение"
        ]
        
        template = random.choice(templates)
        return template.format(title=title.upper(), content=content)

    def format_science_post(self, title, content):
        """Форматирует научный пост"""
        templates = [
            "🔬 НАУЧНОЕ ОТКРЫТИЕ\n\n{title}\n\n{content}\n\n💫 Это открытие изменило наши представления о мире.\n\n#наука #открытие #исследование",
            
            "🌌 ПРОРЫВ В НАУКЕ\n\n{title}\n\n{content}\n\n🚀 Ученые совершили важный шаг в понимании законов природы.\n\n#наука #прорыв #исследование"
        ]
        
        template = random.choice(templates)
        return template.format(title=title.upper(), content=content)

    def format_tech_post(self, title, content):
        """Форматирует технологический пост"""
        templates = [
            "⚡ ТЕХНОЛОГИЧЕСКАЯ РЕВОЛЮЦИЯ\n\n{title}\n\n{content}\n\n💡 Это изобретение изменило подход к решению задач.\n\n#технологии #инновации #будущее",
            
            "🤖 ИННОВАЦИОННАЯ РАЗРАБОТКА\n\n{title}\n\n{content}\n\n🚀 Прогресс не стоит на месте - это достижение демонстрирует новые горизонты.\n\n#технологии #разработка #инновации"
        ]
        
        template = random.choice(templates)
        return template.format(title=title.upper(), content=content)

    def format_historical_post(self, title, content):
        """Форматирует исторический пост"""
        templates = [
            "🏆 ИСТОРИЧЕСКИЙ ФАКТ\n\n{title}\n\n{content}\n\n📚 Это событие стало поворотным моментом в истории.\n\n#история #факт #память",
            
            "💡 ВЕЛИКОЕ ОТКРЫТИЕ\n\n{title}\n\n{content}\n\n🎯 Это достижение изменило ход истории.\n\n#история #открытие #достижение"
        ]
        
        template = random.choice(templates)
        return template.format(title=title.upper(), content=content)

    def get_science_image(self):
        """Возвращает изображение для научных постов"""
        science_images = [
            'https://images.unsplash.com/photo-1532094349884-543bc11b234d?w=500&fit=crop',
            'https://images.unsplash.com/photo-1563089145-599997674d42?w=500&fit=crop',
            'https://images.unsplash.com/photo-1554475900-0a0350e3fc7b?w=500&fit=crop'
        ]
        return random.choice(science_images)

    def get_tech_image(self):
        """Возвращает изображение для технологических постов"""
        tech_images = [
            'https://images.unsplash.com/photo-1518709268805-4e9042af2176?w=500&fit=crop',
            'https://images.unsplash.com/photo-1517077304055-6e89abbf09b0?w=500&fit=crop',
            'https://images.unsplash.com/photo-1542831371-29b0f74f9713?w=500&fit=crop'
        ]
        return random.choice(tech_images)

    def get_historical_image(self):
        """Возвращает изображение для исторических постов"""
        historical_images = [
            'https://images.unsplash.com/photo-1481627834876-b7833e8f5570?w=500&fit=crop',
            'https://images.unsplash.com/photo-1589652717521-10c0d092dea9?w=500&fit=crop',
            'https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=500&fit=crop'
        ]
        return random.choice(historical_images)

    def get_category_image(self, category):
        """Возвращает изображение по категории"""
        category_images = {
            'space': 'https://images.unsplash.com/photo-1446776653964-20c1d3a81b06?w=500&fit=crop',
            'technology': 'https://images.unsplash.com/photo-1518709268805-4e9042af2176?w=500&fit=crop',
            'photography': 'https://images.unsplash.com/photo-1516035069371-29a1b244cc32?w=500&fit=crop',
            'medicine': 'https://images.unsplash.com/photo-1559757148-5c350d0d3c56?w=500&fit=crop',
            'history': 'https://images.unsplash.com/photo-1481627834876-b7833e8f5570?w=500&fit=crop',
            'science': 'https://images.unsplash.com/photo-1532094349884-543bc11b234d?w=500&fit=crop'
        }
        return category_images.get(category, 'https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=500&fit=crop')

    def is_relevant_content(self, text):
        """Проверяет релевантность контента - ищем упоминания первых событий"""
        keywords = [
            'первый', 'первое', 'первая', 'впервые', 'впервы',
            'изобретение', 'открытие', 'революция', 'прорыв',
            'рекорд', 'история', 'создан', 'разработан', 'запущен',
            'обнаружен', 'начало', 'возникновение', 'появление',
            'основание', 'создание', 'изобрет', 'открыт'
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
