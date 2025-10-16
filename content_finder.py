# content_finder.py
import logging
import requests
from datetime import datetime
import random
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)

class ContentFinder:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    def search_content(self, max_posts=2):
        """Основной метод поиска контента"""
        logger.info("🔍 Начинаю поиск контента...")
        
        found_content = []
        
        # Пробуем разные источники
        sources = [
            self.parse_historical_events,
            self.parse_science_news,
            self.generate_quality_content
        ]
        
        for source in sources:
            try:
                content = source()
                if content:
                    found_content.extend(content)
                    logger.info(f"✅ Найдено: {len(content)} записей")
                
                if len(found_content) >= max_posts:
                    break
                    
            except Exception as e:
                logger.error(f"❌ Ошибка источника: {e}")
                continue
        
        return found_content[:max_posts]

    def parse_historical_events(self):
        """Парсинг исторических событий"""
        try:
            # Используем Wikipedia API для поиска исторических событий
            url = "https://ru.wikipedia.org/w/api.php"
            params = {
                'action': 'query',
                'list': 'search',
                'srsearch': 'первое изобретение открытие изобретатель',
                'format': 'json',
                'srlimit': 5
            }
            
            response = self.session.get(url, params=params, timeout=10)
            data = response.json()
            
            articles = []
            for item in data.get('query', {}).get('search', [])[:3]:
                title = item.get('title', '')
                snippet = item.get('snippet', '')
                
                # Очищаем HTML теги из сниппета
                snippet = re.sub(r'<[^>]+>', '', snippet)
                
                if self.is_relevant_content(title + snippet):
                    full_content = self.get_wikipedia_content(title)
                    if full_content:
                        image_url = self.get_wikipedia_image(title)
                        post_text = self.format_wiki_post(title, full_content)
                        
                        articles.append({
                            'title': title,
                            'summary': post_text,
                            'category': 'history',
                            'url': f"https://ru.wikipedia.org/wiki/{title.replace(' ', '_')}",
                            'image_url': image_url,
                            'found_date': datetime.now()
                        })
            
            return articles
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга Wikipedia: {e}")
            return []

    def get_wikipedia_content(self, title):
        """Получает полный контент статьи"""
        try:
            url = "https://ru.wikipedia.org/w/api.php"
            params = {
                'action': 'query',
                'prop': 'extracts',
                'titles': title,
                'explaintext': True,
                'format': 'json'
            }
            
            response = self.session.get(url, params=params, timeout=10)
            data = response.json()
            
            pages = data.get('query', {}).get('pages', {})
            for page_id, page_data in pages.items():
                extract = page_data.get('extract', '')
                # Берем первые 500 символов как основное содержание
                if extract:
                    sentences = extract.split('.')
                    main_content = '.'.join(sentences[:3]) + '.'  # Первые 3 предложения
                    return main_content.strip()
            
            return ""
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения контента: {e}")
            return ""

    def get_wikipedia_image(self, title):
        """Получает изображение из статьи"""
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
            
            return ""
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения изображения: {e}")
            return ""

    def format_wiki_post(self, title, content):
        """Форматирует пост из Wikipedia"""
        # Создаем качественный пост в стиле вашей группы ВК
        template = random.choice([
            "🏆 ИСТОРИЧЕСКОЕ СОБЫТИЕ: {title}\n\n{content}\n\n📚 Это открытие положило начало новой эре в своей области и изменило представления человечества о возможном.\n\n#история #открытие #первый",
            
            "💡 НАУЧНЫЙ ПРОРЫВ: {title}\n\n{content}\n\n🔬 Революционное открытие, которое перевернуло привычные представления и открыло новые горизонты для исследований.\n\n#наука #прорыв #изобретение",
            
            "🚀 ТЕХНОЛОГИЧЕСКАЯ РЕВОЛЮЦИЯ: {title}\n\n{content}\n\n⚡ Инновация, которая кардинально изменила образ жизни людей и стала неотъемлемой частью современного мира.\n\n#технологии #революция #инновации"
        ])
        
        return template.format(title=title.upper(), content=content)

    def parse_science_news(self):
        """Парсинг научных новостей"""
        try:
            # Парсим научные новости
            url = "https://naked-science.ru"
            response = self.session.get(url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            articles = []
            news_items = soup.find_all('article', class_='news')[:3]
            
            for item in news_items:
                try:
                    title_elem = item.find('h2') or item.find('a')
                    if not title_elem:
                        continue
                        
                    title = title_elem.get_text().strip()
                    if self.is_relevant_content(title):
                        # Получаем полный текст статьи
                        link = title_elem.get('href', '')
                        if link and not link.startswith('http'):
                            link = url + link
                        
                        full_content = self.get_article_content(link) if link else title
                        post_text = self.format_news_post(title, full_content)
                        
                        articles.append({
                            'title': title,
                            'summary': post_text,
                            'category': 'science',
                            'url': link,
                            'image_url': '',
                            'found_date': datetime.now()
                        })
                        
                except Exception as e:
                    continue
                    
            return articles
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга новостей: {e}")
            return []

    def get_article_content(self, url):
        """Получает контент статьи"""
        try:
            response = self.session.get(url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Ищем основной контент
            content_div = soup.find('div', class_='content') or soup.find('article')
            if content_div:
                paragraphs = content_div.find_all('p')[:2]  # Берем первые 2 абзаца
                content = ' '.join([p.get_text().strip() for p in paragraphs])
                return content[:300] + '...'  # Ограничиваем длину
            
            return ""
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения контента статьи: {e}")
            return ""

    def format_news_post(self, title, content):
        """Форматирует новостной пост"""
        template = random.choice([
            "🔬 НАУЧНОЕ ОТКРЫТИЕ\n\n{title}\n\n{content}\n\n💫 Это исследование открывает новые возможности для развития технологий и понимания окружающего мира.\n\n#наука #открытие #исследование",
            
            "🌍 ПЕРВЫЙ ШАГ: {title}\n\n{content}\n\n🎯 Историческое достижение, которое стало отправной точкой для дальнейших открытий в этой области.\n\n#первый #достижение #прогресс"
        ])
        
        return template.format(title=title, content=content)

    def generate_quality_content(self):
        """Генерирует качественный контент когда парсинг не работает"""
        quality_posts = [
            {
                'title': 'Первый искусственный спутник Земли',
                'summary': "🛰️ ПЕРВЫЙ ИСКУССТВЕННЫЙ СПУТНИК ЗЕМЛИ\n\n4 октября 1957 года с космодрома Байконур был запущен «Спутник-1» — первый в мире искусственный спутник Земли. Это событие положило начало космической эре человечества.\n\n• Дата: 4 октября 1957 года\n• Страна: СССР\n• Масса: 83,6 кг\n• Период обращения: 96,2 минуты\n\n🌟 Запуск первого спутника доказал возможность создания космических аппаратов и открыл дорогу для пилотируемой космонавтики. Это достижение стало символом научно-технического прогресса и вдохновило целое поколение ученых и инженеров.\n\n#космос #спутник #первый #СССР #история",
                'category': 'space',
                'url': '',
                'image_url': 'https://upload.wikimedia.org/wikipedia/commons/thumb/3/3c/Sputnik_1.jpg/500px-Sputnik_1.jpg',
                'found_date': datetime.now()
            },
            {
                'title': 'Изобретение телефона',
                'summary': "📞 ИЗОБРЕТЕНИЕ ТЕЛЕФОНА\n\n14 февраля 1876 года Александр Белл подал заявку на патент устройства, которое назвал «телефон». Это изобретение навсегда изменило способы коммуникации между людьми.\n\n• Изобретатель: Александр Белл\n• Дата патента: 7 марта 1876 года\n• Первые слова: «Мистер Ватсон, идите сюда. Вы мне нужны»\n\n💡 Телефон стал первым устройством, позволившим передавать человеческую речь на расстояние. За первые 10 лет было установлено более 100 000 аппаратов, что свидетельствует о революционности этого изобретения.\n\n#телефон #изобретение #Белл #коммуникация #история",
                'category': 'technology',
                'url': '',
                'image_url': 'https://upload.wikimedia.org/wikipedia/commons/thumb/1/10/Alexander_Graham_Bell.jpg/500px-Alexander_Graham_Bell.jpg',
                'found_date': datetime.now()
            },
            {
                'title': 'Первый полет братьев Райт',
                'summary': "✈️ ПЕРВЫЙ УПРАВЛЯЕМЫЙ ПОЛЕТ\n\n17 декабря 1903 года братья Райт совершили первый в мире управляемый полет на самолете «Флайер-1». Это событие открыло эру авиации.\n\n• Дата: 17 декабря 1903 года\n• Место: Китти Хок, Северная Каролина\n• Длительность полета: 12 секунд\n• Дистанция: 36,5 метров\n\n🚀 Несмотря на скромные показатели первого полета, он доказал принципиальную возможность управляемого полета тяжелее воздуха. Всего в тот день было совершено 4 полета, самый длинный продолжался 59 секунд.\n\n#авиация #Райт #первый_полет #история #технологии",
                'category': 'aviation',
                'url': '',
                'image_url': 'https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/First_flight2.jpg/500px-First_flight2.jpg',
                'found_date': datetime.now()
            }
        ]
        
        return random.sample(quality_posts, 2)

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
        return f"📰 ПРЕДПРОСМОТР ПОСТА\n\n{content['summary']}\n\n⏰ Найдено: {content['found_date'].strftime('%H:%M %d.%m.%Y')}"

def setup_content_finder():
    """Инициализация системы поиска контента"""
    return ContentFinder()
