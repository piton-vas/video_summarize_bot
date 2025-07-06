import asyncio
import logging
import os
import tempfile
import json
import uuid
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
        f"Просто отправьте мне видео или аудио файл, и я создам его расшифровку с кратким содержанием!"
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
        "<b>Что делает бот:</b>\n"
        "1. Принимает ваш файл\n"
        "2. Ставит задачу в очередь обработки\n"
        "3. Воркеры обрабатывают файл в фоне\n"
        "4. Создает расшифровку с помощью AI\n"
        "5. Делает краткое содержание\n"
        "6. Отправляет результат с таймкодами\n\n"
        "<b>Ограничения:</b>\n"
        "• Максимальный размер файла: 500 МБ\n"
        "• Максимальная длительность: 10 минут\n\n"
        "<b>⚠️ Важно для больших файлов:</b>\n"
        "• Файлы до 50 МБ можно отправлять как видео/аудио\n"
        "• Файлы больше 50 МБ отправляйте как <b>документы</b> (через скрепку 📎)\n"
        "• Это ограничение Telegram Bot API\n\n"
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
    
    # Проверяем размер файла (500 МБ лимит)
    if file_info.file_size > 500 * 1024 * 1024:
        await message.answer("❌ Файл слишком большой. Максимальный размер: 500 МБ.")
        return
    
    # Проверяем ограничения Telegram Bot API
    if message.content_type in ['video', 'audio'] and file_info.file_size > 50 * 1024 * 1024:
        await message.answer(
            "⚠️ Файл превышает лимит Telegram для видео/аудио (50 МБ).\n\n"
            "📎 Пожалуйста, отправьте файл как <b>документ</b> (прикрепите через скрепку), "
            "а не как видео/аудио сообщение.\n\n"
            "Максимальный размер для документов: 500 МБ"
        )
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
        if message.content_type == 'document':
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


@dp.message()
async def echo_handler(message: Message) -> None:
    """
    Обработчик всех остальных сообщений
    """
    await message.answer(
        "🤖 Я умею обрабатывать только видео и аудио файлы.\n\n"
        "Отправьте мне:\n"
        "• Видео файл (MP4, AVI, MOV, MKV, WMV, WEBM)\n"
        "• Аудио файл (MP3, WAV, M4A, OGG, FLAC)\n\n"
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
