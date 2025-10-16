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
        
        # Используем качественный контент с правильными изображениями
        quality_content = self.generate_quality_content_with_images()
        found_content.extend(quality_content)
        
        logger.info(f"🎯 Сгенерировано материалов: {len(found_content)}")
        return found_content[:max_posts]

    def generate_quality_content_with_images(self):
        """Генерирует качественный контент с работающими изображениями"""
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
            },
            {
                'title': 'Первая фотография',
                'summary': "📷 ПЕРВАЯ В МИРЕ ФОТОГРАФИЯ\n\nВ 1826 году Жозеф Нисефор Ньепс сделал первую в истории фотографию под названием «Вид из окна в Ле Гра». Снимок создавался в течение 8 часов.\n\n• Год: 1826\n• Изобретатель: Жозеф Нисефор Ньепс\n• Техника: гелиография\n• Время экспозиции: 8 часов\n\n🎞️ Эта фотография положила начало развитию фотографии как искусства и технологии. Сегодня мы делаем миллиарды снимков ежедневно, но все началось с этого единственного изображения.\n\n#фотография #первая #история #изобретение",
                'category': 'photography',
                'url': '',
                'image_url': 'https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/View_from_the_Window_at_Le_Gras%2C_Joseph_Nic%C3%A9phore_Ni%C3%A9pce.jpg/500px-View_from_the_Window_at_Le_Gras%2C_Joseph_Nic%C3%A9phore_Ni%C3%A9pce.jpg',
                'found_date': datetime.now()
            },
            {
                'title': 'Первый компьютер',
                'summary': "💻 ПЕРВЫЙ ЭЛЕКТРОННЫЙ КОМПЬЮТЕР\n\nENIAC (Electronic Numerical Integrator and Computer), созданный в 1946 году, считается первым электронным компьютером общего назначения.\n\n• Год создания: 1946\n• Вес: 27 тонн\n• Площадь: 167 м²\n• Процессоров: 17 468 ламп\n\n⚡ ENIAC мог выполнять 5000 операций сложения в секунду. Его создание положило начало компьютерной революции и стало основой для всех современных вычислительных систем.\n\n#компьютер #технологии #история #ENIAC",
                'category': 'computers',
                'url': '',
                'image_url': 'https://upload.wikimedia.org/wikipedia/commons/thumb/6/6c/ENIAC_Penn1.jpg/500px-ENIAC_Penn1.jpg',
                'found_date': datetime.now()
            },
            {
                'title': 'Первая вакцина',
                'summary': "💉 ПЕРВАЯ ВАКЦИНА В ИСТОРИИ\n\nВ 1796 году Эдвард Дженнер создал первую в мире вакцину — против оспы. Он заметил, что доярки, переболевшие коровьей оспой, не заболевали натуральной оспой.\n\n• Год: 1796\n• Ученый: Эдвард Дженнер\n• Болезнь: оспа\n• Метод: коровья оспа\n\n🩺 Это открытие спасло миллионы жизней и положило начало иммунологии. Сегодня вакцинация предотвращает 2-3 миллиона смертей ежегодно.\n\n#медицина #вакцина #здоровье #история",
                'category': 'medicine',
                'url': '',
                'image_url': 'https://upload.wikimedia.org/wikipedia/commons/thumb/c/c0/Edward_Jenner._Oil_painting._Wellcome_L0005043.jpg/500px-Edward_Jenner._Oil_painting._Wellcome_L0005043.jpg',
                'found_date': datetime.now()
            }
        ]
        
        return random.sample(quality_posts, 3)

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
        preview_text = f"📰 ПРЕДПРОСМОТР ПОСТА\n\n{content['summary']}\n\n"
        
        if content.get('image_url'):
            preview_text += f"🖼️ Есть изображение: {content['image_url'][:50]}...\n\n"
        
        preview_text += f"⏰ Найдено: {current_time.strftime('%H:%M %d.%m.%Y')}"
        
        return preview_text

def setup_content_finder():
    """Инициализация системы поиска контента"""
    return ContentFinder()
