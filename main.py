import asyncio
import logging
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.webhook.aiohttp_server import SimpleRequestHandler

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


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    """
    Обработчик команды /start
    """
    await message.answer(f"Привет, <b>{message.from_user.full_name}!</b>\n"
                        f"Я простой бот. Отправь мне команду /ping, и я отвечу pong!")


@dp.message(Command('ping'))
async def ping_handler(message: Message) -> None:
    """
    Обработчик команды /ping
    """
    user_id = message.from_user.id
    await message.answer(f"pong ({user_id})")


@dp.message()
async def echo_handler(message: Message) -> None:
    """
    Обработчик всех остальных сообщений
    """
    await message.answer(f"Я не понимаю это сообщение. Попробуй /ping")


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
