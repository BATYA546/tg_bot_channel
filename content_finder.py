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
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Для отслеживания уникальности постов
        self.post_hashes = set()
        
        # Источники для парсинга
        self.sources = [
            self.parse_science_news,
            self.parse_tech_news,
            self.parse_historical_facts,
            self.generate_ai_content
        ]

    def search_content(self, max_posts=3):
        """Основной метод поиска контента"""
        logger.info("🔍 Начинаю поиск уникального контента...")
        
        found_content = []
        attempts = 0
        
        while len(found_content) < max_posts and attempts < 10:
            attempts += 1
            
            for source in self.sources:
                try:
                    content_list = source()
                    if content_list:
                        for content in content_list:
                            if self.is_unique_content(content) and len(found_content) < max_posts:
                                found_content.append(content)
                                self.post_hashes.add(self.get_content_hash(content))
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

    def is_unique_content(self, content):
        """Проверяет уникальность контента"""
        content_hash = self.get_content_hash(content)
        return content_hash not in self.post_hashes

    def get_content_hash(self, content):
        """Создает хеш контента для проверки уникальности"""
        text = content['title'] + content['summary']
        return hashlib.md5(text.encode()).hexdigest()

    def parse_science_news(self):
        """Парсинг научных новостей"""
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
                    
                    # Ищем описание
                    description_elem = item.find('p') or item.find('div', class_='description')
                    description = description_elem.get_text().strip() if description_elem else ""
                    
                    if self.is_relevant_content(title + description):
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

    def parse_tech_news(self):
        """Парсинг технологических новостей"""
        try:
            # 3D News
            url = "https://3dnews.ru"
            response = self.session.get(url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            articles = []
            news_items = soup.find_all('article')[:5] or soup.find_all('div', class_='news-item')[:5]
            
            for item in news_items:
                try:
                    title_elem = item.find('h2') or item.find('h3') or item.find('a')
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text().strip()
                    
                    if self.is_relevant_content(title):
                        formatted_post = self.format_tech_post(title)
                        
                        articles.append({
                            'title': title,
                            'summary': formatted_post,
                            'category': 'technology',
                            'url': url,
                            'image_url': self.get_tech_image(),
                            'found_date': datetime.now()
                        })
                        
                except Exception:
                    continue
                    
            return articles
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга техновостей: {e}")
            return []

    def parse_historical_facts(self):
        """Парсинг исторических фактов"""
        try:
            # Используем Wikipedia API для исторических событий
            url = "https://ru.wikipedia.org/w/api.php"
            params = {
                'action': 'query',
                'list': 'search',
                'srsearch': 'первый изобретение открытие изобретатель первооткрыватель',
                'format': 'json',
                'srlimit': 5
            }
            
            response = self.session.get(url, params=params, timeout=10)
            data = response.json()
            
            articles = []
            for item in data.get('query', {}).get('search', [])[:3]:
                title = item.get('title', '')
                
                if self.is_relevant_content(title):
                    full_content = self.get_wikipedia_content(title)
                    if full_content:
                        formatted_post = self.format_historical_post(title, full_content)
                        
                        articles.append({
                            'title': title,
                            'summary': formatted_post,
                            'category': 'history',
                            'url': f"https://ru.wikipedia.org/wiki/{title.replace(' ', '_')}",
                            'image_url': self.get_historical_image(),
                            'found_date': datetime.now()
                        })
            
            return articles
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга исторических фактов: {e}")
            return []

    def generate_ai_content(self):
        """Генерация качественного контента"""
        historical_events = [
            {
                'title': 'Первый искусственный спутник Земли',
                'content': """4 октября 1957 года с космодрома Байконур был запущен «Спутник-1» — первый в мире искусственный спутник Земли.

📅 Дата: 4 октября 1957 года
🏳️ Страна: СССР
⚖️ Масса: 83,6 кг
🕒 Период обращения: 96,2 минуты

Запуск первого спутника доказал возможность создания космических аппаратов и открыл дорогу для пилотируемой космонавтики.""",
                'category': 'space'
            },
            {
                'title': 'Изобретение телеграфа',
                'content': """В 1837 году Сэмюэл Морзе создал первый практический телеграфный аппарат и разработал азбуку Морзе.

📅 Год изобретения: 1837
👨‍💼 Изобретатель: Сэмюэл Морзе
💡 Ключевое: азбука Морзе
🌍 Значение: революция в коммуникациях

Это изобретение позволило передавать сообщения на большие расстояния за секунды.""",
                'category': 'technology'
            },
            {
                'title': 'Первая фотография',
                'content': """В 1826 году Жозеф Нисефор Ньепс сделал первую в истории фотографию «Вид из окна в Ле Гра».

📅 Год: 1826
👨‍🔬 Изобретатель: Жозеф Нисефор Ньепс
🖼️ Техника: гелиография
⏱️ Время экспозиции: 8 часов

Эта фотография положила начало развитию фотографии как искусства и технологии.""",
                'category': 'photography'
            }
        ]
        
        articles = []
        for event in random.sample(historical_events, 2):
            formatted_post = self.format_ai_post(event['title'], event['content'])
            
            articles.append({
                'title': event['title'],
                'summary': formatted_post,
                'category': event['category'],
                'url': '',
                'image_url': self.get_category_image(event['category']),
                'found_date': datetime.now()
            })
        
        return articles

    def format_science_post(self, title, content):
        """Форматирует научный пост в стиле ВК"""
        templates = [
            "🔬 НАУЧНОЕ ОТКРЫТИЕ\n\n{title}\n\n{content}\n\n💫 Это открытие меняет наши представления о мире и открывает новые горизонты для исследований.\n\n#наука #открытие #исследование",
            
            "🌌 ПРОРЫВ В НАУКЕ\n\n{title}\n\n{content}\n\n🚀 Ученые совершили важный шаг в понимании фундаментальных законов природы.\n\n#наука #прорыв #исследование"
        ]
        
        template = random.choice(templates)
        return template.format(title=title.upper(), content=content)

    def format_tech_post(self, title):
        """Форматирует технологический пост в стиле ВК"""
        templates = [
            "⚡ ТЕХНОЛОГИЧЕСКАЯ РЕВОЛЮЦИЯ\n\n{title}\n\n💡 Это изобретение кардинально меняет подход к решению повседневных задач и открывает новые возможности.\n\n#технологии #инновации #будущее",
            
            "🤖 ИННОВАЦИОННАЯ РАЗРАБОТКА\n\n{title}\n\n🚀 Прогресс не стоит на месте - это достижение демонстрирует новые горизонты technological развития.\n\n#технологии #разработка #инновации"
        ]
        
        template = random.choice(templates)
        return template.format(title=title.upper())

    def format_historical_post(self, title, content):
        """Форматирует исторический пост в стиле ВК"""
        templates = [
            "🏆 ИСТОРИЧЕСКОЕ СОБЫТИЕ\n\n{title}\n\n{content}\n\n📚 Это событие стало поворотным моментом в истории и оказало влияние на развитие человечества.\n\n#история #событие #память",
            
            "💡 ВЕЛИКОЕ ОТКРЫТИЕ\n\n{title}\n\n{content}\n\n🎯 Это достижение изменило ход истории и продолжает влиять на нашу жизнь сегодня.\n\n#история #открытие #достижение"
        ]
        
        template = random.choice(templates)
        return template.format(title=title.upper(), content=content)

    def format_ai_post(self, title, content):
        """Форматирует AI-пост в стиле ВК"""
        templates = [
            "🌟 ИСТОРИЧЕСКИЙ ПРОРЫВ\n\n{title}\n\n{content}\n\n💫 Это достижение навсегда изменило мир и стало важной вехой в развитии человечества.\n\n#история #прорыв #достижение",
            
            "🎯 ПЕРВЫЙ ШАГ\n\n{title}\n\n{content}\n\n🚀 С этого момента началась новая эра, изменившая привычный уклад жизни миллионов людей.\n\n#первый #история #изобретение"
        ]
        
        template = random.choice(templates)
        return template.format(title=title.upper(), content=content)

    def get_article_content(self, item):
        """Получает контент статьи"""
        try:
            # Ищем текст статьи в различных элементах
            content_elems = item.find_all('p') + item.find_all('div', class_=re.compile('content|description|text'))
            
            content_parts = []
            for elem in content_elems[:2]:
                text = elem.get_text().strip()
                if len(text) > 50:  # Берем только значимые блоки
                    content_parts.append(text)
            
            return ' '.join(content_parts)[:300] + '...' if content_parts else ""
            
        except Exception as e:
            return ""

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
                    return first_para[:400] + '...'
            
            return ""
            
        except Exception as e:
            return ""

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
            'photography': 'https://images.unsplash.com/photo-1516035069371-29a1b244cc32?w=500&fit=crop'
        }
        return category_images.get(category, 'https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=500&fit=crop')

    def is_relevant_content(self, text):
        """Проверяет релевантность контента"""
        keywords = [
            'первый', 'первое', 'изобретение', 'открытие', 'революция',
            'прорыв', 'рекорд', 'история', 'создан', 'разработан',
            'запущен', 'обнаружен', 'научный', 'технология', 'инновац',
            'исторический', 'впервые', 'новая технология', 'прорыв'
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

def setup_content_finder():
    """Инициализация системы поиска контента"""
    return ContentFinder()
