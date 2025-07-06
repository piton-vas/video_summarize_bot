import asyncio
import logging
import os
import tempfile
import json
import uuid
import re
import aiohttp
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiogram.client.default import DefaultBotProperties
from rq import Queue
import redis

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Получаем токен бота из переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("BOT_TOKEN не найден в переменных окружения!")
    exit(1)

# Получаем ID администратора из переменных окружения
ADMIN_USER_ID = os.getenv('ADMIN_USER_ID')
if ADMIN_USER_ID:
    ADMIN_USER_ID = int(ADMIN_USER_ID)
    logger.info(f"ID администратора: {ADMIN_USER_ID}")
else:
    logger.warning("ADMIN_USER_ID не найден в переменных окружения!")

# Настройки Redis
REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))

# Создаём объекты бота и диспетчера
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Подключения к Redis
redis_conn = None
redis_conn_rq = None
video_queue = None

# Словарь для хранения состояний пользователей
user_states = {}

async def init_redis():
    """Инициализация Redis подключений"""
    global redis_conn, redis_conn_rq, video_queue
    
    try:
        # Подключение для RQ (без decode_responses)
        redis_conn_rq = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=False)
        redis_conn_rq.ping()
        
        # Подключение для данных (с decode_responses)  
        redis_conn = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
        
        # Очередь для видео обработки
        video_queue = Queue('video_processing', connection=redis_conn_rq)
        
        logger.info(f"Подключен к Redis: {REDIS_HOST}:{REDIS_PORT}")
        return True
    except Exception as e:
        logger.error(f"Ошибка подключения к Redis: {e}")
        return False

async def add_video_task(user_id, file_path, task_id):
    """Добавляет задачу обработки видео в очередь"""
    try:
        if not video_queue:
            logger.error("Redis очередь не инициализирована")
            return None
            
        task_data = {
            'task_id': task_id,
            'user_id': user_id,
            'file_path': file_path,
            'created_at': datetime.now().isoformat()
        }
        
        # Добавляем задачу в очередь
        job = video_queue.enqueue('worker.process_video_sync', task_data, timeout=1800)  # 30 минут
        
        logger.info(f"Задача {task_id} добавлена в очередь для пользователя {user_id}")
        return job
    except Exception as e:
        logger.error(f"Ошибка добавления задачи в очередь: {e}")
        return None

def get_task_status(task_id):
    """Получает статус задачи из Redis"""
    try:
        if not redis_conn:
            logger.error("Redis подключение не инициализировано")
            return None
            
        task_key = f"task:{task_id}"
        task_data = redis_conn.hgetall(task_key)
        
        if task_data:
            return {
                'status': task_data.get('status', 'unknown'),
                'message': task_data.get('message', ''),
                'result': task_data.get('result', ''),
                'updated_at': task_data.get('updated_at', '')
            }
        return None
    except Exception as e:
        logger.error(f"Ошибка получения статуса задачи {task_id}: {e}")
        return None

async def monitor_task(task_id, user_id, status_message):
    """Мониторит выполнение задачи и обновляет статус"""
    try:
        last_status = ""
        
        while True:
            task_status = get_task_status(task_id)
            
            if not task_status:
                await asyncio.sleep(5)
                continue
            
            current_status = task_status['status']
            current_message = task_status['message']
            
            # Обновляем статус только если он изменился
            if current_message != last_status:
                try:
                    await status_message.edit_text(f"🔄 {current_message}")
                    last_status = current_message
                except Exception as e:
                    logger.error(f"Ошибка обновления статуса: {e}")
            
            # Проверяем завершение задачи
            if current_status == 'completed':
                # Задача завершена успешно
                result_data = json.loads(task_status['result'])
                await handle_task_completion(user_id, result_data, status_message)
                break
            elif current_status == 'failed':
                # Задача завершена с ошибкой
                await status_message.edit_text(f"❌ {current_message}")
                break
            
            await asyncio.sleep(3)  # Проверяем каждые 3 секунды
            
    except Exception as e:
        logger.error(f"Ошибка мониторинга задачи {task_id}: {e}")
        await status_message.edit_text("❌ Произошла ошибка при мониторинге задачи")

async def handle_task_completion(user_id, result_data, status_message):
    """Обрабатывает завершение задачи"""
    try:
        # Отправляем результат
        response_text = (
            f"✅ <b>Обработка завершена!</b>\n\n"
            f"📝 <b>Краткое содержание:</b>\n"
            f"{result_data['summary']}\n\n"
            f"📜 <b>Полная расшифровка:</b>\n"
            f"{result_data['transcript'][:1000]}{'...' if len(result_data['transcript']) > 1000 else ''}"
        )
        
        await status_message.edit_text(response_text)
        
        # Отправляем файл с полными результатами
        if 'output_file' in result_data and os.path.exists(result_data['output_file']):
            with open(result_data['output_file'], 'rb') as f:
                await bot.send_document(
                    chat_id=user_id,
                    document=types.BufferedInputFile(f.read(), filename=os.path.basename(result_data['output_file'])),
                    caption="📄 Полная расшифровка с таймкодами"
                )
            # Удаляем временный файл результата
            os.unlink(result_data['output_file'])
            
    except Exception as e:
        logger.error(f"Ошибка обработки завершения задачи: {e}")
        await status_message.edit_text("❌ Ошибка при отправке результатов")


async def download_file_from_url(url, max_size=500*1024*1024):
    """Скачивает файл по URL с проверкой размера"""
    try:
        # Увеличиваем лимиты для заголовков (для cloud.mail.ru)
        connector = aiohttp.TCPConnector(limit_per_host=10)
        timeout = aiohttp.ClientTimeout(total=300)  # 5 минут
        
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
            max_line_size=16384,  # Увеличиваем лимит строки заголовка
            max_field_size=16384   # Увеличиваем лимит поля заголовка
        ) as session:
            # Специальная обработка для Яндекс.Диска API
            if 'cloud-api.yandex.net' in url:
                try:
                    async with session.get(url) as response:
                        if response.status != 200:
                            return None, f"Не удалось получить ссылку с Яндекс.Диска (код {response.status})"
                        
                        result = await response.json()
                        if 'href' not in result:
                            return None, "Не удалось получить прямую ссылку с Яндекс.Диска"
                        
                        # Получаем прямую ссылку из API
                        download_url = result['href']
                        
                        # Теперь работаем с прямой ссылкой
                        # Для Яндекс.Диска нужно разрешить редиректы
                        async with session.head(download_url, allow_redirects=True) as dl_response:
                            if dl_response.status != 200:
                                return None, f"Не удалось получить файл с Яндекс.Диска (код {dl_response.status})"
                            
                            # Проверяем размер файла
                            content_length = dl_response.headers.get('content-length')
                            if content_length and int(content_length) > max_size:
                                size_mb = int(content_length) / (1024 * 1024)
                                return None, f"Файл слишком большой ({size_mb:.1f} МБ). Максимум: {max_size/(1024*1024):.0f} МБ"
                            
                            # Получаем имя файла
                            file_name = None
                            content_disposition = dl_response.headers.get('content-disposition')
                            if content_disposition:
                                filename_match = re.search(r'filename[*]?=([^;]+)', content_disposition)
                                if filename_match:
                                    file_name = filename_match.group(1).strip('"\'')
                            
                            if not file_name:
                                file_name = os.path.basename(download_url.split('?')[0])
                            
                            if not file_name or '.' not in file_name:
                                file_name = 'yandex_disk_file'
                        
                        # Скачиваем файл
                        temp_dir = '/tmp/shared' if os.path.exists('/tmp/shared') else '/tmp'
                        with tempfile.NamedTemporaryFile(delete=False, dir=temp_dir) as tmp_file:
                            tmp_path = tmp_file.name
                            
                            async with session.get(download_url, allow_redirects=True) as dl_response:
                                if dl_response.status != 200:
                                    return None, f"Не удалось скачать файл с Яндекс.Диска (код {dl_response.status})"
                                
                                downloaded_size = 0
                                async for chunk in dl_response.content.iter_chunked(8192):
                                    downloaded_size += len(chunk)
                                    if downloaded_size > max_size:
                                        os.unlink(tmp_path)
                                        return None, f"Файл слишком большой (больше {max_size/(1024*1024):.0f} МБ)"
                                    tmp_file.write(chunk)
                            
                            return tmp_path, file_name
                        
                except Exception as e:
                    return None, f"Ошибка обработки Яндекс.Диска: {str(e)}"
            
            # Обычная обработка для других URL
            async with session.head(url, allow_redirects=True) as response:
                if response.status != 200:
                    return None, f"Не удалось получить файл (код {response.status})"
                
                # Проверяем размер файла
                content_length = response.headers.get('content-length')
                if content_length and int(content_length) > max_size:
                    size_mb = int(content_length) / (1024 * 1024)
                    return None, f"Файл слишком большой ({size_mb:.1f} МБ). Максимум: {max_size/(1024*1024):.0f} МБ"
                
                # Получаем имя файла из заголовков или URL
                file_name = None
                content_disposition = response.headers.get('content-disposition')
                if content_disposition:
                    # Пытаемся извлечь filename из content-disposition
                    filename_match = re.search(r'filename[*]?=([^;]+)', content_disposition)
                    if filename_match:
                        file_name = filename_match.group(1).strip('"\'')
                
                if not file_name:
                    # Получаем имя файла из URL
                    file_name = os.path.basename(url.split('?')[0])
                
                if not file_name or '.' not in file_name:
                    file_name = 'downloaded_file'
            
            # Скачиваем файл
            temp_dir = '/tmp/shared' if os.path.exists('/tmp/shared') else '/tmp'
            with tempfile.NamedTemporaryFile(delete=False, dir=temp_dir) as tmp_file:
                tmp_path = tmp_file.name
                
                async with session.get(url, allow_redirects=True) as response:
                    if response.status != 200:
                        return None, f"Не удалось скачать файл (код {response.status})"
                    
                    downloaded_size = 0
                    async for chunk in response.content.iter_chunked(8192):
                        downloaded_size += len(chunk)
                        if downloaded_size > max_size:
                            os.unlink(tmp_path)
                            return None, f"Файл слишком большой (больше {max_size/(1024*1024):.0f} МБ)"
                        tmp_file.write(chunk)
                
                return tmp_path, file_name
                
    except Exception as e:
        logger.error(f"Ошибка скачивания файла по URL: {e}")
        error_msg = str(e)
        

        
        return None, f"Ошибка скачивания: {error_msg}"


def is_valid_url(url):
    """Проверяет, является ли строка валидным URL"""
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return url_pattern.match(url) is not None


async def convert_cloud_url_to_direct(url):
    """Преобразует ссылки облачных хранилищ в прямые ссылки"""
    try:
        # Обработка Google Drive
        if 'drive.google.com' in url:
            # Извлекаем ID файла
            file_id = None
            if '/file/d/' in url:
                match = re.search(r'/file/d/([a-zA-Z0-9-_]+)', url)
                if match:
                    file_id = match.group(1)
            elif 'id=' in url:
                match = re.search(r'id=([a-zA-Z0-9-_]+)', url)
                if match:
                    file_id = match.group(1)
            
            if file_id:
                # Формируем прямую ссылку для скачивания
                direct_url = f"https://drive.google.com/uc?export=download&id={file_id}"
                return direct_url
        
        # Обработка Dropbox
        elif 'dropbox.com' in url and '?dl=0' in url:
            # Заменяем ?dl=0 на ?dl=1 для прямого скачивания
            direct_url = url.replace('?dl=0', '?dl=1')
            return direct_url
        
        # Обработка OneDrive
        elif 'onedrive.live.com' in url or '1drv.ms' in url:
            # Для OneDrive нужно добавить &download=1
            if '?' in url:
                direct_url = url + '&download=1'
            else:
                direct_url = url + '?download=1'
            return direct_url
        
        # Обработка Яндекс.Диска
        elif 'disk.yandex.ru/d/' in url:
            # Извлекаем ключ из URL вида https://disk.yandex.ru/d/KEY
            match = re.search(r'disk\.yandex\.ru/d/([^/?]+)', url)
            if match:
                key = match.group(1)
                # Используем публичный API Яндекс.Диска для получения прямой ссылки
                direct_url = f"https://cloud-api.yandex.net/v1/disk/public/resources/download?public_key=https://disk.yandex.ru/d/{key}"
                return direct_url
        
        # Обработка других форматов Яндекс.Диска
        elif 'disk.yandex.ru' in url and ('/i/' in url or '/d/' in url):
            # Для старых форматов ссылок Яндекс.Диска
            if '?download=1' not in url:
                separator = '&' if '?' in url else '?'
                direct_url = url + separator + 'download=1'
                return direct_url
            
        # Если не удалось преобразовать, возвращаем исходный URL
        return url
        
    except Exception as e:
        logger.error(f"Ошибка преобразования URL: {e}")
        return url


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    """
    Обработчик команды /start
    """
    await message.answer(
        f"Привет, <b>{message.from_user.full_name}!</b>\n\n"
        f"Я бот для расшифровки видео и аудио файлов.\n\n"
        f"<b>Доступные команды:</b>\n"
        f"• /start - показать это сообщение\n"
        f"• /ping - проверить работу бота\n"
        f"• /help - подробная справка\n"
        f"• /status - статус системы\n\n"
        f"<b>Как использовать:</b>\n"
        f"Отправьте мне видео/аудио файл или ссылку на файл, и я создам расшифровку с кратким содержанием!\n\n"
        f"📎 Файлы до 20 МБ - прикрепите напрямую\n"
        f"🔗 Файлы до 500 МБ - отправьте ссылку\n"
        f"☁️ Поддерживаются облачные хранилища (включая Яндекс.Диск)"
    )


@dp.message(Command('ping'))
async def ping_handler(message: Message) -> None:
    """
    Обработчик команды /ping
    """
    user_id = message.from_user.id
    await message.answer(f"pong _ (Твой ID: {user_id})")


@dp.message(Command('status'))
async def status_handler(message: Message) -> None:
    """
    Обработчик команды /status
    """
    try:
        if not redis_conn or not video_queue:
            status_text = (
                f"🔴 <b>Статус системы</b>\n\n"
                f"• Redis: не инициализирован\n"
                f"• Система: недоступна"
            )
        else:
            # Проверяем подключение к Redis
            redis_conn.ping()
            queue_length = len(video_queue)
            
            status_text = (
                f"🟢 <b>Статус системы</b>\n\n"
                f"• Redis: подключен\n"
                f"• Очередь обработки: {queue_length} задач\n"
                f"• Воркеры: активны\n"
                f"• Система: работает нормально"
            )
    except Exception as e:
        status_text = (
            f"🔴 <b>Статус системы</b>\n\n"
            f"• Ошибка подключения к Redis\n"
            f"• Система: недоступна\n"
            f"• Детали: {str(e)}"
        )
    
    await message.answer(status_text)


@dp.message(Command('help'))
async def help_handler(message: Message) -> None:
    """
    Обработчик команды /help
    """
    await message.answer(
        "<b>🎥 Бот для расшифровки видео и аудио</b>\n\n"
        "<b>Поддерживаемые форматы:</b>\n"
        "• Видео: MP4, AVI, MOV, MKV, WMV, WEBM\n"
        "• Аудио: MP3, WAV, M4A, OGG, FLAC\n\n"
        "<b>Способы отправки файлов:</b>\n"
        "1. 📎 Прикрепить файл напрямую (до 20 МБ)\n"
        "2. 🔗 Отправить ссылку на файл (до 500 МБ)\n"
        "   • Прямые ссылки на файлы\n"
        "   • Google Drive, Dropbox, OneDrive\n"
        "   • Яндекс.Диск\n\n"
        "<b>Что делает бот:</b>\n"
        "1. Принимает ваш файл или ссылку\n"
        "2. Ставит задачу в очередь обработки\n"
        "3. Воркеры обрабатывают файл в фоне\n"
        "4. Создает расшифровку с помощью AI\n"
        "5. Делает краткое содержание\n"
        "6. Отправляет результат с таймкодами\n\n"
        "<b>Ограничения:</b>\n"
        "• Файлы через Telegram: до 20 МБ\n"
        "• Файлы по ссылке: до 500 МБ\n"
        "• Максимальная длительность: 10 минут\n\n"
        "<b>Преимущества новой архитектуры:</b>\n"
        "• Высокая производительность\n"
        "• Масштабируемость\n"
        "• Отказоустойчивость\n\n"
        "<b>Просто отправьте файл и ждите результат!</b>"
    )


@dp.message(lambda message: message.content_type in ['video', 'audio', 'document'])
async def media_handler(message: Message) -> None:
    """
    Обработчик видео, аудио и документов
    """
    user_id = message.from_user.id
    
    # Проверяем, не обрабатывается ли уже файл от этого пользователя
    if user_id in user_states and user_states[user_id].get('processing'):
        await message.answer("⏳ Пожалуйста, подождите. Ваш предыдущий файл еще обрабатывается.")
        return
    
    # Определяем тип файла
    file_info = None
    file_name = None
    
    if message.content_type == 'video':
        file_info = message.video
        file_name = f"video_{user_id}_{message.message_id}.mp4"
    elif message.content_type == 'audio':
        file_info = message.audio
        file_name = f"audio_{user_id}_{message.message_id}.mp3"
    elif message.content_type == 'document':
        file_info = message.document
        file_name = message.document.file_name or f"document_{user_id}_{message.message_id}"
        
        # Отбрасываем последние символы подчеркивания из имени файла
        clean_file_name = file_name.rstrip('_')
        
        # Проверяем расширение файла
        allowed_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.webm', '.mp3', '.wav', '.m4a', '.ogg', '.flac']
        if not any(clean_file_name.lower().endswith(ext) for ext in allowed_extensions):
            await message.answer(
                "❌ Неподдерживаемый формат файла.\n\n"
                "Поддерживаемые форматы:\n"
                "• Видео: MP4, AVI, MOV, MKV, WMV, WEBM\n"
                "• Аудио: MP3, WAV, M4A, OGG, FLAC"
            )
            return
    
    if not file_info:
        await message.answer("❌ Не удалось получить информацию о файле.")
        return
    
    # Проверяем размер файла (20 МБ лимит - ограничение Telegram Bot API)
    if file_info.file_size > 20 * 1024 * 1024:
        await message.answer("❌ Файл слишком большой. Максимальный размер: 20 МБ.\n\nЭто ограничение Telegram Bot API для скачивания файлов.")
        return
    

    
    # Устанавливаем состояние обработки
    user_states[user_id] = {'processing': True}
    
    # Отправляем сообщение о начале обработки
    status_message = await message.answer("📥 Загружаю файл...")
    
    try:
        # Получаем файл
        file = await bot.get_file(file_info.file_id)
        
        # Создаем временный файл в shared volume
        temp_dir = '/tmp/shared' if os.path.exists('/tmp/shared') else '/tmp'
        # Для документов используем очищенное имя файла для получения правильного расширения
        if message.content_type == 'document' and file_name:
            clean_file_name = file_name.rstrip('_')
            suffix = os.path.splitext(clean_file_name)[1] if clean_file_name else '.tmp'
        else:
            suffix = os.path.splitext(file_name)[1] if file_name else '.tmp'
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=temp_dir) as tmp_file:
            tmp_path = tmp_file.name
            
            # Скачиваем файл
            await status_message.edit_text("📥 Скачиваю файл...")
            await bot.download_file(file.file_path, tmp_path)
            
            # Генерируем уникальный ID задачи
            task_id = str(uuid.uuid4())
            
            # Добавляем задачу в очередь
            await status_message.edit_text("📋 Добавляю в очередь обработки...")
            job = await add_video_task(user_id, tmp_path, task_id)
            
            if job:
                await status_message.edit_text("⏳ Задача добавлена в очередь. Ожидание обработки...")
                
                # Запускаем мониторинг задачи
                asyncio.create_task(monitor_task(task_id, user_id, status_message))
            else:
                await status_message.edit_text("❌ Ошибка добавления задачи в очередь")
                # Удаляем временный файл при ошибке
                os.unlink(tmp_path)
                
    except Exception as e:
        logger.error(f"Ошибка обработки файла: {e}")
        await status_message.edit_text(f"❌ Произошла ошибка: {str(e)}")
    
    finally:
        # Сбрасываем состояние обработки
        if user_id in user_states:
            user_states[user_id]['processing'] = False


@dp.message(lambda message: message.text and is_valid_url(message.text.strip()))
async def url_handler(message: Message) -> None:
    """
    Обработчик URL-ссылок для скачивания файлов
    """
    user_id = message.from_user.id
    url = message.text.strip()
    
    # Проверяем, не обрабатывается ли уже файл от этого пользователя
    if user_id in user_states and user_states[user_id].get('processing'):
        await message.answer("⏳ Пожалуйста, подождите. Ваш предыдущий файл еще обрабатывается.")
        return
    
    # Устанавливаем состояние обработки
    user_states[user_id] = {'processing': True}
    
    # Отправляем сообщение о начале обработки
    status_message = await message.answer("🔗 Анализирую ссылку...")
    
    try:
        # Преобразуем ссылку облачного хранилища в прямую ссылку
        await status_message.edit_text("🔗 Обрабатываю ссылку...")
        direct_url = await convert_cloud_url_to_direct(url)
        
        # Скачиваем файл по прямой ссылке
        await status_message.edit_text("📥 Скачиваю файл...")
        tmp_path, file_name = await download_file_from_url(direct_url)
        
        if not tmp_path:
            await status_message.edit_text(f"❌ {file_name}")
            return
        
        # Отбрасываем последние символы подчеркивания из имени файла
        clean_file_name = file_name.rstrip('_')
        
        # Проверяем расширение файла
        allowed_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.webm', '.mp3', '.wav', '.m4a', '.ogg', '.flac']
        if not any(clean_file_name.lower().endswith(ext) for ext in allowed_extensions):
            await status_message.edit_text(
                "❌ Неподдерживаемый формат файла.\n\n"
                "Поддерживаемые форматы:\n"
                "• Видео: MP4, AVI, MOV, MKV, WMV, WEBM\n"
                "• Аудио: MP3, WAV, M4A, OGG, FLAC"
            )
            # Удаляем временный файл
            os.unlink(tmp_path)
            return
        
        # Генерируем уникальный ID задачи
        task_id = str(uuid.uuid4())
        
        # Добавляем задачу в очередь
        await status_message.edit_text("📋 Добавляю в очередь обработки...")
        job = await add_video_task(user_id, tmp_path, task_id)
        
        if job:
            await status_message.edit_text("⏳ Задача добавлена в очередь. Ожидание обработки...")
            
            # Запускаем мониторинг задачи
            asyncio.create_task(monitor_task(task_id, user_id, status_message))
        else:
            await status_message.edit_text("❌ Ошибка добавления задачи в очередь")
            # Удаляем временный файл при ошибке
            os.unlink(tmp_path)
            
    except Exception as e:
        logger.error(f"Ошибка обработки URL: {e}")
        await status_message.edit_text(f"❌ Произошла ошибка: {str(e)}")
    
    finally:
        # Сбрасываем состояние обработки
        if user_id in user_states:
            user_states[user_id]['processing'] = False


@dp.message()
async def echo_handler(message: Message) -> None:
    """
    Обработчик всех остальных сообщений
    """
    await message.answer(
        "🤖 Я умею обрабатывать видео и аудио файлы.\n\n"
        "Отправьте мне:\n"
        "• Видео файл (MP4, AVI, MOV, MKV, WMV, WEBM)\n"
        "• Аудио файл (MP3, WAV, M4A, OGG, FLAC)\n"
        "• Ссылку на файл (до 500 МБ)\n"
        "• Файлы из облачных хранилищ (Google Drive, Dropbox, OneDrive, Яндекс.Диск)\n\n"
        "Или используйте команду /help для подробной справки."
    )


async def send_startup_notification() -> None:
    """
    Отправляет уведомление администратору о запуске бота
    """
    if ADMIN_USER_ID:
        try:
            startup_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            queue_length = len(video_queue) if video_queue else 0
            
            await bot.send_message(
                chat_id=ADMIN_USER_ID,
                text="🚀 <b>Бот запущен!</b>\n\n"
                     f"⏰ Время запуска: {startup_time}\n"
                     f"📦 Версия: microservices\n"
                     f"🆔 ID бота: {bot.id if hasattr(bot, 'id') else 'Unknown'}\n"
                     f"📋 Очередь обработки: {queue_length} задач\n"
                     f"🔧 Архитектура: Redis + Workers"
            )
            logger.info("Уведомление о запуске отправлено администратору")
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления администратору: {e}")


async def main() -> None:
    """
    Основная функция для запуска бота
    """
    logger.info("Запуск бота...")
    
    # Инициализируем Redis
    if not await init_redis():
        logger.error("Не удалось подключиться к Redis. Завершение работы.")
        return
    
    # Удаляем старые апдейты
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Отправляем уведомление о запуске
    await send_startup_notification()
    
    # Запускаем polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
