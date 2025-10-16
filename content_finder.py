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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Расширяем ключевые слова
        self.keywords = [
            "перв", "революц", "рекорд", "прорыв", "инновац", "открытие",
            "изобрет", "технолог", "наук", "истори", "уникальн", "новый",
            "прогресс", "разработк", "создан", "запуск", "обнаружен"
        ]
        
        # Исправляем источники - убираем параметр url из вызовов
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
                # Передаем URL в парсер
                content = source['parser'](source['url'])
                if content:
                    found_content.extend(content)
                    logger.info(f"✅ Найдено: {len(content)} записей")
                
                if len(found_content) >= max_posts:
                    found_content = found_content[:max_posts]
                    break
                    
                time.sleep(3)
                
            except Exception as e:
                logger.error(f"❌ Ошибка парсинга {source['name']}: {e}")
                continue
        
        # Если ничего не нашли, используем fallback
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
            # Ищем различные элементы с новостями
            news_items = soup.find_all(['div', 'article'], class_=True)
            
            for item in news_items[:20]:
                try:
                    # Ищем заголовок в разных тегах
                    title_elem = (item.find('h2') or 
                                 item.find('h3') or 
                                 item.find('h4') or
                                 item.find('a') or
                                 item.find('span'))
                    
                    if not title_elem:
                        continue
                        
                    title = title_elem.get_text().strip()
                    if len(title) < 15:  # Минимальная длина
                        continue
                    
                    # Более мягкая проверка релевантности
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
            # Ищем заголовки новостей ТАСС
            news_items = soup.find_all(['article', 'div', 'li'], class_=True)
            
            for item in news_items[:25]:
                try:
                    # Ищем заголовки в различных тегах
                    title_elem = (item.find('h2') or 
                                 item.find('h3') or 
                                 item.find('h4') or
                                 item.find('a') or 
                                 item.find('span'))
                    
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
            # Более широкий поиск элементов
            news_items = soup.find_all(['article', 'div', 'section'], class_=True)
            
            for item in news_items[:15]:
                try:
                    title_elem = (item.find('h2') or 
                                 item.find('h3') or
                                 item.find('h1') or
                                 item.find('a'))
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

    def is_relevant_content(self, text):
        """Более мягкая проверка релевантности"""
        text_lower = text.lower()
        
        # Проверяем по ключевым словам (частичное совпадение)
        for keyword in self.keywords:
            if keyword in text_lower:
                return True
                
        # Дополнительные проверки для научного контента
        science_words = ['учен', 'исследова', 'разработ', 'созда', 'обнаруж']
        for word in science_words:
            if word in text_lower:
                return True
                
        return False

    def generate_summary(self, title):
        """Генерирует краткое описание на основе заголовка"""
        summaries = [
            f"Интересное открытие в области науки и технологий: {title}",
            f"Новое достижение исследователей: {title}",
            f"Прогресс в развитии технологий: {title}",
            f"Важное научное событие: {title}",
            f"Инновационная разработка: {title}",
            f"Революционное открытие: {title}",
            f"Историческое достижение: {title}",
            f"Уникальная технология: {title}"
        ]
        return random.choice(summaries)

    def categorize_content(self, title):
        """Категоризирует контент"""
        title_lower = title.lower()
        
        if any(word in title_lower for word in ['технолог', 'инновац', 'изобрет', 'разработ', 'компьютер', 'ии']):
            return 'technology'
        elif any(word in title_lower for word in ['наук', 'открыт', 'исследова', 'учен', 'физик', 'хими']):
            return 'science'
        elif any(word in title_lower for word in ['рекорд', 'первый', 'истори', 'уникальн', 'впервые']):
            return 'records'
        else:
            return 'discovery'

    def generate_fallback_content(self):
        """Генерирует тестовый контент если ничего не найдено"""
        logger.info("🔄 Генерирую тестовый контент...")
        
        fallback_titles = [
            "Ученые создали первый в мире квантовый компьютер с рекордной производительностью",
            "Революционная технология позволила впервые получить энергию из вакуума",
            "Историческое открытие: обнаружена новая частица, меняющая представления о физике",
            "Первый в мире искусственный интеллект прошел тест Тьюринга с рекордным результатом",
            "Инновационная разработка: созданы солнечные батареи с КПД более 50%",
            "Ученые впервые создали искусственный мозг с возможностью самообучения",
            "Рекордный прорыв: разработана технология телепортация информации на расстояние 100 км",
            "Впервые в истории: обнаружена планета с условиями, идентичными Земле"
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

    def format_for_preview(self, content):
        """Форматирует контент для предпросмотра"""
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
