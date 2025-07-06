# 🎥 Video Summarize Bot

Telegram бот для автоматической расшифровки и саммаризации видео/аудио файлов с использованием микросервисной архитектуры.

## 📋 Возможности

- 🎞️ Поддержка видео: MP4, AVI, MOV, MKV, WMV
- 🎵 Поддержка аудио: MP3, WAV, M4A, OGG, FLAC
- 🤖 Автоматическая расшифровка с помощью OpenAI Whisper
- 📝 Создание краткого содержания
- ⏱️ Генерация временных меток
- 🔄 Асинхронная обработка через очереди
- 📊 Масштабируемая архитектура

## 🏗️ Архитектура

Проект разделен на отдельные микросервисы:

```
video_summarize_bot/
├── bot/                    # Telegram Bot
│   ├── main.py            # Основной код бота
│   ├── requirements.txt   # Зависимости бота
│   ├── Dockerfile         # Контейнер бота
│   └── .dockerignore      # Исключения для Docker
├── worker/                # Video Processing Worker
│   ├── worker.py          # Обработчик задач
│   ├── decryptor.py       # Логика расшифровки
│   ├── requirements.txt   # Зависимости воркера
│   ├── Dockerfile         # Контейнер воркера
│   └── .dockerignore      # Исключения для Docker
├── docker-compose.yml     # Конфигурация всех сервисов
├── .env                   # Переменные окружения
└── README.md             # Документация
```

### Компоненты системы:

1. **Redis** - Очереди задач и хранение состояний
2. **Telegram Bot** - Взаимодействие с пользователями
3. **Video Workers** - Обработка видео/аудио файлов
4. **Shared Storage** - Общие временные файлы
5. **Redis Commander** - Веб-интерфейс для мониторинга (опционально)
6. **Watchtower** - Автоматическое обновление контейнеров (опционально)

## 🚀 Быстрый старт

### 1. Клонирование репозитория

```bash
git clone <repository-url>
cd video_summarize_bot
```

### 2. Создание .env файла

```bash
cp .env.example .env
```

Заполните переменные окружения:

```env
# Токен бота (получить у @BotFather)
BOT_TOKEN=your_bot_token_here

# ID администратора (необязательно)
ADMIN_USER_ID=123456789
```

### 3. Запуск всех сервисов

```bash
# Запуск основных сервисов
docker-compose up -d

# Запуск с мониторингом Redis
docker-compose --profile monitoring up -d

# Запуск с автообновлением
docker-compose --profile auto-update up -d

# Запуск всех сервисов
docker-compose --profile monitoring --profile auto-update up -d
```

### 4. Проверка статуса

```bash
# Проверка работы всех сервисов
docker-compose ps

# Просмотр логов
docker-compose logs -f

# Просмотр логов конкретного сервиса
docker-compose logs -f bot
docker-compose logs -f worker
```

## 📱 Получение токена бота

1. Напишите [@BotFather](https://t.me/BotFather) в Telegram
2. Отправьте команду `/newbot`
3. Укажите имя вашего бота
4. Укажите username бота (должен заканчиваться на `bot`)
5. Скопируйте полученный токен в файл `.env`

## 🔧 Управление сервисами

### Основные команды

```bash
# Запуск сервисов
docker-compose up -d

# Остановка сервисов
docker-compose down

# Перезапуск сервисов
docker-compose restart

# Пересборка контейнеров
docker-compose build

# Пересборка без кэша
docker-compose build --no-cache

# Просмотр логов
docker-compose logs -f

# Масштабирование воркеров
docker-compose up -d --scale worker=3
```

### Управление воркерами

```bash
# Увеличение количества воркеров
docker-compose up -d --scale worker=5

# Уменьшение количества воркеров
docker-compose up -d --scale worker=1

# Перезапуск только воркеров
docker-compose restart worker
```

### Обновление кода

```bash
# Остановка сервисов
docker-compose down

# Пересборка контейнеров
docker-compose build

# Запуск с новой версией
docker-compose up -d
```

## 📊 Мониторинг

### Redis Commander

Веб-интерфейс для мониторинга Redis доступен по адресу: http://localhost:8081

Запуск с мониторингом:
```bash
docker-compose --profile monitoring up -d
```

### Логи сервисов

```bash
# Все логи
docker-compose logs -f

# Логи бота
docker-compose logs -f bot

# Логи воркеров
docker-compose logs -f worker

# Логи Redis
docker-compose logs -f redis
```

### Проверка состояния

```bash
# Статус всех контейнеров
docker-compose ps

# Использование ресурсов
docker stats

# Информация о системе
docker system df
```

## 🛠️ Разработка

### Локальная разработка

```bash
# Клонирование репозитория
git clone <repository-url>
cd video_summarize_bot

# Установка зависимостей для бота
cd bot
pip install -r requirements.txt

# Установка зависимостей для воркера
cd ../worker
pip install -r requirements.txt

# Возврат в корень проекта
cd ..
```

### Структура зависимостей

**Bot сервис (`bot/requirements.txt`):**
- `aiogram` - Telegram Bot API
- `aiohttp` - HTTP клиент
- `python-dotenv` - Переменные окружения
- `redis` - Redis клиент
- `rq` - Redis Queue

**Worker сервис (`worker/requirements.txt`):**
- `redis` - Redis клиент
- `rq` - Redis Queue
- `python-dotenv` - Переменные окружения
- `pydub` - Аудио обработка
- `openai-whisper` - Распознавание речи
- `ffmpeg-python` - Работа с медиа файлами
- `torch` - PyTorch для ML модели
- `transformers` - Hugging Face модели

### Добавление новых функций

1. **Для бота** - редактируйте файлы в папке `bot/`
2. **Для воркера** - редактируйте файлы в папке `worker/`
3. **Пересборка** - запустите `docker-compose build`
4. **Перезапуск** - запустите `docker-compose up -d`

## 🐛 Устранение неполадок

### Проблемы с подключением к Redis

```bash
# Проверка Redis
docker-compose exec redis redis-cli ping

# Перезапуск Redis
docker-compose restart redis
```

### Проблемы с воркерами

```bash
# Просмотр логов воркеров
docker-compose logs -f worker

# Перезапуск воркеров
docker-compose restart worker

# Увеличение количества воркеров
docker-compose up -d --scale worker=3
```

### Проблемы с памятью

```bash
# Очистка неиспользуемых контейнеров
docker system prune

# Очистка всех данных Docker
docker system prune -a

# Мониторинг использования ресурсов
docker stats
```

### Проблемы с ffmpeg

```bash
# Пересборка контейнера воркера
docker-compose build worker

# Проверка ffmpeg в контейнере
docker-compose exec worker ffmpeg -version
```

## 🔐 Безопасность

- Используйте `.env` файл для хранения секретных данных
- Не коммитьте `.env` файл в репозиторий
- Ограничьте доступ к Redis Commander в продакшене
- Используйте Docker secrets для продакшена

## 📄 Лицензия

MIT License

## 🤝 Участие в разработке

1. Форкните репозиторий
2. Создайте ветку для новой функции
3. Внесите изменения
4. Создайте Pull Request

## 📞 Поддержка

При возникновении проблем:

1. Проверьте логи: `docker-compose logs -f`
2. Убедитесь, что все сервисы запущены: `docker-compose ps`
3. Проверьте переменные окружения в `.env`
4. Попробуйте пересобрать контейнеры: `docker-compose build --no-cache`

## 🔗 Полезные ссылки

- [Aiogram Documentation](https://docs.aiogram.dev/)
- [OpenAI Whisper](https://github.com/openai/whisper)
- [Redis Queue](https://python-rq.org/)
- [Docker Compose](https://docs.docker.com/compose/) 