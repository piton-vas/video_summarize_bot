import asyncio
import logging
import os
import tempfile
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from decryptor import decrypt_process

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

# Создаём объекты бота и диспетчера
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# Словарь для хранения состояний пользователей
user_states = {}


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
        f"• /help - подробная справка\n\n"
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


@dp.message(Command('help'))
async def help_handler(message: Message) -> None:
    """
    Обработчик команды /help
    """
    await message.answer(
        "<b>🎥 Бот для расшифровки видео и аудио</b>\n\n"
        "<b>Поддерживаемые форматы:</b>\n"
        "• Видео: MP4, AVI, MOV, MKV, WMV\n"
        "• Аудио: MP3, WAV, M4A, OGG, FLAC\n\n"
        "<b>Что делает бот:</b>\n"
        "1. Принимает ваш файл\n"
        "2. Конвертирует его в аудио\n"
        "3. Создает расшифровку с помощью AI\n"
        "4. Делает краткое содержание\n"
        "5. Отправляет результат с таймкодами\n\n"
        "<b>Ограничения:</b>\n"
        "• Максимальный размер файла: 20 МБ\n"
        "• Максимальная длительность: 10 минут\n\n"
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
        
        # Проверяем расширение файла
        allowed_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.mp3', '.wav', '.m4a', '.ogg', '.flac']
        if not any(file_name.lower().endswith(ext) for ext in allowed_extensions):
            await message.answer(
                "❌ Неподдерживаемый формат файла.\n\n"
                "Поддерживаемые форматы:\n"
                "• Видео: MP4, AVI, MOV, MKV, WMV\n"
                "• Аудио: MP3, WAV, M4A, OGG, FLAC"
            )
            return
    
    if not file_info:
        await message.answer("❌ Не удалось получить информацию о файле.")
        return
    
    # Проверяем размер файла (20 МБ лимит)
    if file_info.file_size > 20 * 1024 * 1024:
        await message.answer("❌ Файл слишком большой. Максимальный размер: 20 МБ.")
        return
    
    # Устанавливаем состояние обработки
    user_states[user_id] = {'processing': True}
    
    # Отправляем сообщение о начале обработки
    status_message = await message.answer("📥 Загружаю файл...")
    
    async def update_status(status_text):
        try:
            await status_message.edit_text(f"🔄 {status_text}")
        except Exception as e:
            logger.error(f"Ошибка обновления статуса: {e}")
    
    try:
        # Получаем файл
        file = await bot.get_file(file_info.file_id)
        
        # Создаем временный файл
        suffix = os.path.splitext(file_name)[1] if file_name else '.tmp'
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_path = tmp_file.name
            
            # Скачиваем файл
            await update_status("Скачиваю файл...")
            await bot.download_file(file.file_path, tmp_path)
            
            # Обрабатываем файл
            await update_status("Начинаю обработку...")
            result = await decrypt_process(tmp_path, update_status)
            
            if result:
                # Отправляем результат
                response_text = (
                    f"✅ <b>Обработка завершена!</b>\n\n"
                    f"📝 <b>Краткое содержание:</b>\n"
                    f"{result['summary']}\n\n"
                    f"📜 <b>Полная расшифровка:</b>\n"
                    f"{result['transcript'][:1000]}{'...' if len(result['transcript']) > 1000 else ''}"
                )
                
                await status_message.edit_text(response_text)
                
                # Отправляем файл с полными результатами
                if os.path.exists(result['output_file']):
                    with open(result['output_file'], 'rb') as f:
                        await message.answer_document(
                            types.BufferedInputFile(f.read(), filename=os.path.basename(result['output_file'])),
                            caption="📄 Полная расшифровка с таймкодами"
                        )
                    # Удаляем временный файл результата
                    os.unlink(result['output_file'])
            else:
                await status_message.edit_text("❌ Произошла ошибка при обработке файла.")
                
    except Exception as e:
        logger.error(f"Ошибка обработки файла: {e}")
        await status_message.edit_text(f"❌ Произошла ошибка: {str(e)}")
    
    finally:
        # Удаляем временный файл
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        
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
        "• Видео файл (MP4, AVI, MOV, MKV, WMV)\n"
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
            await bot.send_message(
                chat_id=ADMIN_USER_ID,
                text="🚀 <b>Бот запущен!</b>\n\n"
                     f"⏰ Время запуска: {startup_time}\n"
                     f"📦 Версия: latest\n"
                     f"🆔 ID бота: {bot.id if hasattr(bot, 'id') else 'Unknown'}"
            )
            logger.info("Уведомление о запуске отправлено администратору")
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления администратору: {e}")


async def main() -> None:
    """
    Основная функция для запуска бота
    """
    logger.info("Запуск бота...")
    
    # Удаляем старые апдейты
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Отправляем уведомление о запуске
    await send_startup_notification()
    
    # Запускаем polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
