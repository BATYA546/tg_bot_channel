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
        
        # Более разнообразные источники
        self.sources = [
            self.parse_wikipedia_firsts,
            self.parse_historical_events,
            self.parse_science_discoveries,
            self.parse_tech_innovations,
            self.parse_cultural_firsts,
            self.parse_sports_records
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
                    text = title + content[:200]  # Берем только начало контента
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
        max_attempts = 10
        
        # Перемешиваем источники для разнообразия
        random.shuffle(self.sources)
        
        while len(found_content) < max_posts and attempts < max_attempts:
            attempts += 1
            logger.info(f"🔍 Попытка {attempts}/{max_attempts}")
            
            for source in self.sources:
                try:
                    if len(found_content) >= max_posts:
                        break
                        
                    logger.info(f"📡 Проверяем источник: {source.__name__}")
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
                    else:
                        logger.info(f"ℹ️ Источник {source.__name__} не вернул контент")
                
                except Exception as e:
                    logger.error(f"❌ Ошибка источника {source.__name__}: {e}")
                    continue
                
            # Увеличиваем задержку между попытками
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
            
            # Более гибкая проверка - ищем похожие заголовки
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

    def parse_wikipedia_firsts(self):
        """Парсинг первых событий из Википедии"""
        try:
            articles = []
            
            # Разнообразные запросы для поиска первых событий
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
                "первая книга",
                "первый спутник",
                "первый человек в космосе",
                "первая операция",
                "первое лекарство",
                "первый интернет",
                "первый мобильный телефон",
                "первый самолет",
                "первая электрическая лампочка",
                "первый телевизор",
                "первое радио"
            ]
            
            for query in random.sample(search_queries, 4):  # Берем 4 случайных запроса
                try:
                    url = "https://ru.wikipedia.org/w/api.php"
                    params = {
                        'action': 'query',
                        'list': 'search',
                        'srsearch': query,
                        'format': 'json',
                        'srlimit': 5,
                        'srwhat': 'text'
                    }
                    
                    response = self.session.get(url, params=params, timeout=15)
                    data = response.json()
                    
                    for item in data.get('query', {}).get('search', []):
                        title = item.get('title', '')
                        snippet = item.get('snippet', '')
                        
                        # Очищаем HTML теги из сниппета
                        soup = BeautifulSoup(snippet, 'html.parser')
                        clean_snippet = soup.get_text()
                        
                        if self.is_relevant_content(title + clean_snippet):
                            full_content = self.get_wikipedia_content(title)
                            if full_content and len(full_content) > 80:
                                # Создаем уникальное описание
                                formatted_post = self.create_wikipedia_post(title, full_content, query)
                                
                                articles.append({
                                    'title': title,
                                    'summary': formatted_post,
                                    'category': self.detect_category(title, full_content),
                                    'url': f"https://ru.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}",
                                    'image_url': self.get_wikipedia_image(title),
                                    'found_date': datetime.now()
                                })
                                
                                if len(articles) >= 3:
                                    return articles
                    
                    time.sleep(1.5)  # Задержка между запросами
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка парсинга запроса {query}: {e}")
                    continue
                    
            return articles[:2]  # Возвращаем не более 2 статей
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга Wikipedia: {e}")
            return []

    def parse_historical_events(self):
        """Парсинг исторических событий"""
        try:
            articles = []
            
            # Используем разные подходы для получения исторических фактов
            historical_methods = [
                self.parse_historical_dates,
                self.parse_famous_firsts,
                self.parse_invention_history
            ]
            
            for method in random.sample(historical_methods, 2):
                try:
                    content = method()
                    if content:
                        articles.extend(content)
                        if len(articles) >= 2:
                            break
                except Exception as e:
                    logger.error(f"❌ Ошибка метода истории: {e}")
                    continue
            
            return articles[:2]
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга исторических событий: {e}")
            return []

    def parse_historical_dates(self):
        """Парсинг исторических дат"""
        try:
            # Исторические события с упором на "первые"
            historical_events = [
                {
                    'title': 'Первая печатная книга',
                    'content': 'Библия Гутенберга, изданная в 1455 году, стала первой книгой, напечатанной с использованием подвижного шрифта. Это изобретение Иоганна Гутенберга революционизировало распространение знаний.',
                    'year': '1455'
                },
                {
                    'title': 'Первая фотография',
                    'content': 'В 1826 году Жозеф Нисефор Ньепс создал первую в истории фотографию «Вид из окна в Ле Гра». Экспозиция длилась 8 часов.',
                    'year': '1826'
                },
                {
                    'title': 'Первый полет братьев Райт',
                    'content': '17 декабря 1903 года братья Райт совершили первый управляемый полет на самолете с двигателем. Продолжительность полета составила 12 секунд.',
                    'year': '1903'
                },
                {
                    'title': 'Первая успешная трансплантация сердца',
                    'content': '3 декабря 1967 года Кристиан Барнард провел первую успешную пересадку сердца человеку. Операция длилась 9 часов.',
                    'year': '1967'
                }
            ]
            
            articles = []
            for event in random.sample(historical_events, 2):
                formatted_post = self.format_historical_post(event['title'], event['content'], event['year'])
                
                articles.append({
                    'title': event['title'],
                    'summary': formatted_post,
                    'category': 'history',
                    'url': '',
                    'image_url': self.get_historical_image(),
                    'found_date': datetime.now()
                })
            
            return articles
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания исторических дат: {e}")
            return []

    def parse_famous_firsts(self):
        """Известные первые достижения"""
        try:
            firsts = [
                {
                    'title': 'Первая женщина-космонавт',
                    'content': 'Валентина Терешкова стала первой женщиной в космосе 16 июня 1963 года на корабле Восток-6. Ее полет длился почти трое суток.',
                    'person': 'Валентина Терешкова'
                },
                {
                    'title': 'Первый программист',
                    'content': 'Ада Лавлейс считается первым программистом в истории. В 1843 году она написала первую в мире программу для аналитической машины Чарльза Бэббиджа.',
                    'person': 'Ада Лавлейс'
                },
                {
                    'title': 'Первый нобелевский лауреат',
                    'content': 'Вильгельм Конрад Рентген стал первым лауреатом Нобелевской премии по физике в 1901 году за открытие рентгеновских лучей.',
                    'person': 'Вильгельм Рентген'
                }
            ]
            
            articles = []
            for first in random.sample(firsts, 2):
                formatted_post = self.format_person_post(first['title'], first['content'], first['person'])
                
                articles.append({
                    'title': first['title'],
                    'summary': formatted_post,
                    'category': 'achievement',
                    'url': '',
                    'image_url': self.get_achievement_image(),
                    'found_date': datetime.now()
                })
            
            return articles
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания первых достижений: {e}")
            return []

    def parse_science_discoveries(self):
        """Парсинг научных открытий"""
        try:
            articles = []
            
            # Научные открытия и изобретения
            discoveries = [
                {
                    'title': 'Открытие пенициллина',
                    'content': 'Александр Флеминг случайно открыл пенициллин в 1928 году. Это первый антибиотик, который произвел революцию в медицине.',
                    'year': '1928',
                    'scientist': 'Александр Флеминг'
                },
                {
                    'title': 'Первая вакцина',
                    'content': 'Эдвард Дженнер создал первую вакцину против оспы в 1796 году. Он использовал вирус коровьей оспы для защиты от натуральной оспы.',
                    'year': '1796',
                    'scientist': 'Эдвард Дженнер'
                },
                {
                    'title': 'Открытие структуры ДНК',
                    'content': 'Джеймс Уотсон и Фрэнсис Крик открыли двойную спираль ДНК в 1953 году. Это фундаментальное открытие в генетике.',
                    'year': '1953',
                    'scientist': 'Уотсон и Крик'
                },
                {
                    'title': 'Первый телескоп',
                    'content': 'Галилео Галилей первым использовал телескоп для астрономических наблюдений в 1609 году. Он открыл спутники Юпитера и фазы Венеры.',
                    'year': '1609',
                    'scientist': 'Галилео Галилей'
                }
            ]
            
            for discovery in random.sample(discoveries, 2):
                formatted_post = self.format_science_post(
                    discovery['title'], 
                    discovery['content'], 
                    discovery['year'], 
                    discovery['scientist']
                )
                
                articles.append({
                    'title': discovery['title'],
                    'summary': formatted_post,
                    'category': 'science',
                    'url': '',
                    'image_url': self.get_science_image(),
                    'found_date': datetime.now()
                })
            
            return articles
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания научных открытий: {e}")
            return []

    def parse_tech_innovations(self):
        """Парсинг технологических инноваций"""
        try:
            articles = []
            
            # Технологические инновации
            innovations = [
                {
                    'title': 'Первый смартфон',
                    'content': 'IBM Simon, выпущенный в 1994 году, считается первым смартфоном. Он сочетал функции телефона и КПК.',
                    'year': '1994',
                    'company': 'IBM'
                },
                {
                    'title': 'Первый веб-сайт',
                    'content': 'Первый в мире веб-сайт info.cern.ch был запущен Тимом Бернерсом-Ли в 1991 году. Он объяснял концепцию Всемирной паутины.',
                    'year': '1991',
                    'company': 'CERN'
                },
                {
                    'title': 'Первый микропроцессор',
                    'content': 'Intel 4004, выпущенный в 1971 году, стал первым коммерческим микропроцессором. Он содержал 2300 транзисторов.',
                    'year': '1971',
                    'company': 'Intel'
                },
                {
                    'title': 'Первая компьютерная мышь',
                    'content': 'Дуглас Энгельбарт изобрел первую компьютерную мышь в 1964 году. Устройство было деревянным с двумя металлическими колесами.',
                    'year': '1964',
                    'company': 'Stanford Research Institute'
                }
            ]
            
            for innovation in random.sample(innovations, 2):
                formatted_post = self.format_tech_post(
                    innovation['title'], 
                    innovation['content'], 
                    innovation['year'], 
                    innovation['company']
                )
                
                articles.append({
                    'title': innovation['title'],
                    'summary': formatted_post,
                    'category': 'technology',
                    'url': '',
                    'image_url': self.get_tech_image(),
                    'found_date': datetime.now()
                })
            
            return articles
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания технологических инноваций: {e}")
            return []

    def parse_cultural_firsts(self):
        """Парсинг культурных первых"""
        try:
            articles = []
            
            cultural_firsts = [
                {
                    'title': 'Первый полнометражный мультфильм',
                    'content': '«Белоснежка и семь гномов» (1937) стал первым полнометражным анимационным фильмом. Производство заняло 3 года.',
                    'year': '1937',
                    'studio': 'Walt Disney'
                },
                {
                    'title': 'Первая звуковая кинокартина',
                    'content': '«Певец джаза» (1927) стал первым полнометражным фильмом с синхронной звуковой дорожкой.',
                    'year': '1927',
                    'studio': 'Warner Bros.'
                },
                {
                    'title': 'Первый роман-антиутопия',
                    'content': '«Мы» Евгения Замятина (1920) считается первым романом-антиутопией, повлиявшим на Оруэлла и Хаксли.',
                    'year': '1920',
                    'author': 'Евгений Замятин'
                }
            ]
            
            for cultural in random.sample(cultural_firsts, 2):
                formatted_post = self.format_cultural_post(
                    cultural['title'], 
                    cultural['content'], 
                    cultural['year'], 
                    cultural.get('studio') or cultural.get('author')
                )
                
                articles.append({
                    'title': cultural['title'],
                    'summary': formatted_post,
                    'category': 'culture',
                    'url': '',
                    'image_url': self.get_cultural_image(),
                    'found_date': datetime.now()
                })
            
            return articles
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания культурных первых: {e}")
            return []

    def parse_sports_records(self):
        """Парсинг спортивных рекордов"""
        try:
            articles = []
            
            sports_records = [
                {
                    'title': 'Первый четырехминутный миля',
                    'content': 'Роджер Баннистер первым пробежал милю быстрее 4 минут 6 мая 1954 года. Его результат: 3 минуты 59.4 секунды.',
                    'year': '1954',
                    'athlete': 'Роджер Баннистер'
                },
                {
                    'title': 'Первое восхождение на Эверест',
                    'content': 'Эдмунд Хиллари и Тенцинг Норгей первыми покорили Эверест 29 мая 1953 года.',
                    'year': '1953',
                    'athlete': 'Хиллари и Норгей'
                },
                {
                    'title': 'Первый олимпийский чемпион',
                    'content': 'Джеймс Конноли стал первым олимпийским чемпионом современности, выиграв тройной прыжок 6 апреля 1896 года.',
                    'year': '1896',
                    'athlete': 'Джеймс Конноли'
                }
            ]
            
            for record in random.sample(sports_records, 2):
                formatted_post = self.format_sports_post(
                    record['title'], 
                    record['content'], 
                    record['year'], 
                    record['athlete']
                )
                
                articles.append({
                    'title': record['title'],
                    'summary': formatted_post,
                    'category': 'sports',
                    'url': '',
                    'image_url': self.get_sports_image(),
                    'found_date': datetime.now()
                })
            
            return articles
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания спортивных рекордов: {e}")
            return []

    def parse_invention_history(self):
        """История изобретений"""
        try:
            articles = []
            
            inventions = [
                {
                    'title': 'Изобретение печатного станка',
                    'content': 'Иоганн Гутенберг изобрел печатный станок с подвижными литерами около 1440 года. Это изобретение революционизировало распространение информации.',
                    'year': '1440',
                    'inventor': 'Иоганн Гутенберг'
                },
                {
                    'title': 'Изобретение лампочки',
                    'content': 'Томас Эдисон запатентовал первую практическую лампу накаливания в 1879 году. Она могла гореть до 1200 часов.',
                    'year': '1879',
                    'inventor': 'Томас Эдисон'
                },
                {
                    'title': 'Изобретение радио',
                    'content': 'Александр Попов продемонстрировал первый радиоприемник 7 мая 1895 года. Гульельмо Маркони независимо разработал похожую систему.',
                    'year': '1895',
                    'inventor': 'Александр Попов'
                }
            ]
            
            for invention in random.sample(inventions, 2):
                formatted_post = self.format_invention_post(
                    invention['title'], 
                    invention['content'], 
                    invention['year'], 
                    invention['inventor']
                )
                
                articles.append({
                    'title': invention['title'],
                    'summary': formatted_post,
                    'category': 'invention',
                    'url': '',
                    'image_url': self.get_invention_image(),
                    'found_date': datetime.now()
                })
            
            return articles
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания истории изобретений: {e}")
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
            
            response = self.session.get(url, params=params, timeout=15)
            data = response.json()
            
            pages = data.get('query', {}).get('pages', {})
            for page_id, page_data in pages.items():
                extract = page_data.get('extract', '')
                if extract:
                    # Берем первый значимый абзац
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
            
            return self.get_random_image()
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения изображения Wikipedia: {e}")
            return self.get_random_image()

    def create_wikipedia_post(self, title, content, query):
        """Создает пост на основе Wikipedia контента"""
        templates = [
            "🌍 ИСТОРИЧЕСКОЕ СОБЫТИЕ\n\n{title}\n\n{content}\n\n🔍 Найдено по запросу: {query}\n\n📚 Это событие стало важной вехой в истории человечества.\n\n#история #событие #память",
            
            "💫 ПЕРВЫЙ ШАГ\n\n{title}\n\n{content}\n\n🔍 Найдено по запросу: {query}\n\n🚀 Это достижение открыло новые возможности для развития цивилизации.\n\n#первый #история #достижение",
            
            "🏆 ВАЖНОЕ ОТКРЫТИЕ\n\n{title}\n\n{content}\n\n🔍 Найдено по запросу: {query}\n\n💡 Это изобретение изменило ход истории и продолжает влиять на нашу жизнь.\n\n#открытие #изобретение #история"
        ]
        
        template = random.choice(templates)
        return template.format(title=title.upper(), content=content, query=query)

    def format_historical_post(self, title, content, year):
        """Форматирует исторический пост"""
        templates = [
            "📜 ИСТОРИЧЕСКИЙ ФАКТ\n\n{title}\n\n{content}\n\n📅 Год: {year}\n\n📚 Это событие стало поворотным моментом в истории.\n\n#история #факт #память",
            
            "🕰️ ВЕХА ИСТОРИИ\n\n{title}\n\n{content}\n\n📅 Год: {year}\n\n🎯 Это достижение изменило ход истории.\n\n#история #веха #достижение"
        ]
        
        template = random.choice(templates)
        return template.format(title=title.upper(), content=content, year=year)

    def format_science_post(self, title, content, year, scientist):
        """Форматирует научный пост"""
        templates = [
            "🔬 НАУЧНОЕ ОТКРЫТИЕ\n\n{title}\n\n{content}\n\n📅 Год: {year}\n👨‍🔬 Ученый: {scientist}\n\n💫 Это открытие изменило наши представления о мире.\n\n#наука #открытие #исследование",
            
            "🌌 ПРОРЫВ В НАУКЕ\n\n{title}\n\n{content}\n\n📅 Год: {year}\n👨‍🔬 Ученый: {scientist}\n\n🚀 Ученые совершили важный шаг в понимании законов природы.\n\n#наука #прорыв #исследование"
        ]
        
        template = random.choice(templates)
        return template.format(title=title.upper(), content=content, year=year, scientist=scientist)

    def format_tech_post(self, title, content, year, company):
        """Форматирует технологический пост"""
        templates = [
            "⚡ ТЕХНОЛОГИЧЕСКАЯ РЕВОЛЮЦИЯ\n\n{title}\n\n{content}\n\n📅 Год: {year}\n🏢 Компания: {company}\n\n💡 Это изобретение изменило подход к решению задач.\n\n#технологии #инновации #будущее",
            
            "🤖 ИННОВАЦИОННАЯ РАЗРАБОТКА\n\n{title}\n\n{content}\n\n📅 Год: {year}\n🏢 Компания: {company}\n\n🚀 Прогресс не стоит на месте - это достижение демонстрирует новые горизонты.\n\n#технологии #разработка #инновации"
        ]
        
        template = random.choice(templates)
        return template.format(title=title.upper(), content=content, year=year, company=company)

    def format_person_post(self, title, content, person):
        """Форматирует пост о личности"""
        templates = [
            "🌟 ИСТОРИЧЕСКАЯ ЛИЧНОСТЬ\n\n{title}\n\n{content}\n\n👤 Персона: {person}\n\n💫 Это достижение навсегда изменило мир.\n\n#история #личность #достижение",
            
            "🎯 ПЕРВЫЙ ШАГ\n\n{title}\n\n{content}\n\n👤 Персона: {person}\n\n🚀 С этого момента началась новая эра.\n\n#первый #история #изобретение"
        ]
        
        template = random.choice(templates)
        return template.format(title=title.upper(), content=content, person=person)

    def format_cultural_post(self, title, content, year, creator):
        """Форматирует культурный пост"""
        templates = [
            "🎭 КУЛЬТУРНОЕ СОБЫТИЕ\n\n{title}\n\n{content}\n\n📅 Год: {year}\n🎬 Создатель: {creator}\n\n📚 Это произведение изменило культурный ландшафт.\n\n#культура #искусство #история",
            
            "🎨 ТВОРЧЕСКИЙ ПРОРЫВ\n\n{title}\n\n{content}\n\n📅 Год: {year}\n🎬 Создатель: {creator}\n\n💫 Это достижение открыло новые горизонты в искусстве.\n\n#культура #творчество #инновации"
        ]
        
        template = random.choice(templates)
        return template.format(title=title.upper(), content=content, year=year, creator=creator)

    def format_sports_post(self, title, content, year, athlete):
        """Форматирует спортивный пост"""
        templates = [
            "🏆 СПОРТИВНЫЙ РЕКОРД\n\n{title}\n\n{content}\n\n📅 Год: {year}\n🏃‍♂️ Спортсмен: {athlete}\n\n💪 Это достижение показало новые возможности человека.\n\n#спорт #рекорд #достижение",
            
            "🚀 ИСТОРИЧЕСКИЙ МОМЕНТ\n\n{title}\n\n{content}\n\n📅 Год: {year}\n🏃‍♂️ Спортсмен: {athlete}\n\n🎯 Этот рекорд навсегда вошел в историю спорта.\n\n#спорт #история #момент"
        ]
        
        template = random.choice(templates)
        return template.format(title=title.upper(), content=content, year=year, athlete=athlete)

    def format_invention_post(self, title, content, year, inventor):
        """Форматирует пост об изобретении"""
        templates = [
            "💡 ВЕЛИКОЕ ИЗОБРЕТЕНИЕ\n\n{title}\n\n{content}\n\n📅 Год: {year}\n👨‍🔬 Изобретатель: {inventor}\n\n⚡ Это изобретение кардинально изменило жизнь людей.\n\n#изобретение #инновации #история",
            
            "🔧 ТЕХНИЧЕСКИЙ ПРОРЫВ\n\n{title}\n\n{content}\n\n📅 Год: {year}\n👨‍🔬 Изобретатель: {inventor}\n\n🚀 Это достижение открыло новые технологические горизонты.\n\n#технологии #прорыв #изобретение"
        ]
        
        template = random.choice(templates)
        return template.format(title=title.upper(), content=content, year=year, inventor=inventor)

    def detect_category(self, title, content):
        """Определяет категорию контента"""
        text = (title + content).lower()
        
        if any(word in text for word in ['наука', 'ученый', 'открытие', 'исследование']):
            return 'science'
        elif any(word in text for word in ['технология', 'компьютер', 'интернет', 'смартфон']):
            return 'technology'
        elif any(word in text for word in ['история', 'исторический', 'прошлое', 'древний']):
            return 'history'
        elif any(word in text for word in ['культура', 'искусство', 'кино', 'музыка']):
            return 'culture'
        elif any(word in text for word in ['спорт', 'спортсмен', 'рекорд', 'олимпийский']):
            return 'sports'
        else:
            return 'achievement'

    def get_science_image(self):
        """Возвращает изображение для научных постов"""
        science_images = [
            'https://images.unsplash.com/photo-1532094349884-543bc11b234d?w=500&fit=crop',
            'https://images.unsplash.com/photo-1563089145-599997674d42?w=500&fit=crop',
            'https://images.unsplash.com/photo-1554475900-0a0350e3fc7b?w=500&fit=crop',
            'https://images.unsplash.com/photo-1507413245164-6160d8298b31?w=500&fit=crop'
        ]
        return random.choice(science_images)

    def get_tech_image(self):
        """Возвращает изображение для технологических постов"""
        tech_images = [
            'https://images.unsplash.com/photo-1518709268805-4e9042af2176?w=500&fit=crop',
            'https://images.unsplash.com/photo-1517077304055-6e89abbf09b0?w=500&fit=crop',
            'https://images.unsplash.com/photo-1542831371-29b0f74f9713?w=500&fit=crop',
            'https://images.unsplash.com/photo-1550751827-4bd374c3f58b?w=500&fit=crop'
        ]
        return random.choice(tech_images)

    def get_historical_image(self):
        """Возвращает изображение для исторических постов"""
        historical_images = [
            'https://images.unsplash.com/photo-1481627834876-b7833e8f5570?w=500&fit=crop',
            'https://images.unsplash.com/photo-1589652717521-10c0d092dea9?w=500&fit=crop',
            'https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=500&fit=crop',
            'https://images.unsplash.com/photo-1505664194779-8beaceb93744?w=500&fit=crop'
        ]
        return random.choice(historical_images)

    def get_cultural_image(self):
        """Возвращает изображение для культурных постов"""
        cultural_images = [
            'https://images.unsplash.com/photo-1514320291840-2e0a9bf2a9ae?w=500&fit=crop',
            'https://images.unsplash.com/photo-1492684223066-81342ee5ff30?w=500&fit=crop',
            'https://images.unsplash.com/photo-1503095396549-807759245b35?w=500&fit=crop'
        ]
        return random.choice(cultural_images)

    def get_sports_image(self):
        """Возвращает изображение для спортивных постов"""
        sports_images = [
            'https://images.unsplash.com/photo-1461896836934-ffe607ba8211?w=500&fit=crop',
            'https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=500&fit=crop',
            'https://images.unsplash.com/photo-1556817411-31ae72fa3ea0?w=500&fit=crop'
        ]
        return random.choice(sports_images)

    def get_achievement_image(self):
        """Возвращает изображение для постов о достижениях"""
        achievement_images = [
            'https://images.unsplash.com/photo-1563089145-599997674d42?w=500&fit=crop',
            'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=500&fit=crop',
            'https://images.unsplash.com/photo-1517048676732-d65bc937f952?w=500&fit=crop'
        ]
        return random.choice(achievement_images)

    def get_invention_image(self):
        """Возвращает изображение для постов об изобретениях"""
        invention_images = [
            'https://images.unsplash.com/photo-1506744038136-46273834b3fb?w=500&fit=crop',
            'https://images.unsplash.com/photo-1518709268805-4e9042af2176?w=500&fit=crop',
            'https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=500&fit=crop'
        ]
        return random.choice(invention_images)

    def get_random_image(self):
        """Возвращает случайное изображение"""
        all_images = (
            self.get_science_image(),
            self.get_tech_image(),
            self.get_historical_image(),
            self.get_cultural_image(),
            self.get_sports_image(),
            self.get_achievement_image(),
            self.get_invention_image()
        )
        return random.choice(all_images)

    def is_relevant_content(self, text):
        """Проверяет релевантность контента - ищем упоминания первых событий"""
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
