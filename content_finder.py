# content_finder.py
import requests
import logging
from datetime import datetime, timedelta
import time
import random
from bs4 import BeautifulSoup

class ContentFinder:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Ключевые слова для поиска
        self.keywords = [
            "первое открытие", "революционная технология", "мировой рекорд",
            "впервые в истории", "прорыв в науке", "инновационное изобретение",
            "новый рекорд", "историческое событие", "технологический прорыв",
            "научное открытие", "первый в мире", "уникальное достижение"
        ]
        
        # Источники для парсинга
        self.sources = [
            {
                'name': 'Научные новости',
                'url': 'https://nplus1.ru/news',
                'parser': self.parse_nplus1
            },
            # Добавим больше источников позже
        ]

    def search_content(self, max_posts=5):
        """Основной метод поиска контента"""
        self.logger.info("🔍 Начинаю поиск контента...")
        
        found_content = []
        
        for source in self.sources:
            try:
                self.logger.info(f"📰 Проверяю {source['name']}...")
                content = source['parser']()
                if content:
                    found_content.extend(content)
                    self.logger.info(f"✅ Найдено: {len(content)} записей")
                
                # Ограничиваем общее количество
                if len(found_content) >= max_posts:
                    found_content = found_content[:max_posts]
                    break
                    
                time.sleep(2)  # Пауза между запросами
                
            except Exception as e:
                self.logger.error(f"❌ Ошибка парсинга {source['name']}: {e}")
                continue
        
        self.logger.info(f"🎯 Всего найдено материалов: {len(found_content)}")
        return found_content

    def parse_nplus1(self):
        """Парсер научного сайта nplus1.ru"""
        try:
            response = self.session.get(self.sources[0]['url'], timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            articles = []
            news_items = soup.find_all('article', class_='news')[:10]  # Берем 10 последних
            
            for item in news_items:
                try:
                    title_elem = item.find('h2') or item.find('a')
                    if not title_elem:
                        continue
                        
                    title = title_elem.get_text().strip()
                    link = title_elem.get('href') if title_elem.get('href') else ''
                    
                    # Проверяем релевантность по ключевым словам
                    if self.is_relevant_content(title):
                        # Получаем полный текст
                        full_text = self.get_article_details(link) if link else title
                        
                        article_data = {
                            'title': title,
                            'summary': full_text,
                            'source': 'N+1',
                            'url': f"https://nplus1.ru{link}" if link else '',
                            'category': self.categorize_content(title),
                            'found_date': datetime.now()
                        }
                        articles.append(article_data)
                        
                except Exception as e:
                    self.logger.debug(f"Ошибка обработки статьи: {e}")
                    continue
                    
            return articles
            
        except Exception as e:
            self.logger.error(f"Ошибка парсинга N+1: {e}")
            return []

    def is_relevant_content(self, text):
        """Проверяет релевантность контента по ключевым словам"""
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.keywords)

    def categorize_content(self, title):
        """Категоризирует контент"""
        title_lower = title.lower()
        
        if any(word in title_lower for word in ['технолог', 'инновац', 'изобрет']):
            return 'technology'
        elif any(word in title_lower for word in ['наук', 'открыт', 'исследова']):
            return 'science'
        elif any(word in title_lower for word in ['рекорд', 'первый', 'истори']):
            return 'records'
        else:
            return 'general'

    def get_article_details(self, article_url):
        """Получает детали статьи (заглушка)"""
        # TODO: Реализовать парсинг полного текста
        return "Интересная статья о последних достижениях."

    def format_for_preview(self, content):
        """Форматирует контент для предпросмотра"""
        return f"""
📰 *Новый материал для публикации*

*Заголовок:* {content['title']}
*Категория:* {content['category']}
*Источник:* {content['source']}

*Текст:*
{content['summary'][:200]}...

⏰ Найдено: {content['found_date'].strftime('%H:%M %d.%m.%Y')}
        """

# Интеграция с основным ботом
def setup_content_finder():
    """Инициализация системы поиска контента"""
    finder = ContentFinder()
    return finder
