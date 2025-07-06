# 🎥 Telegram Бот для Расшифровки Видео (Микросервисная Архитектура)

Высокопроизводительный бот для автоматической расшифровки видео и аудио файлов с помощью искусственного интеллекта. Построен на микросервисной архитектуре с Redis для масштабируемости и отказоустойчивости.

## ✨ Возможности

### 🎯 Основные функции
- 📹 Поддержка видео форматов: MP4, AVI, MOV, MKV, WMV
- 🎵 Поддержка аудио форматов: MP3, WAV, M4A, OGG, FLAC
- 🤖 Автоматическая расшифровка с помощью Whisper AI
- 📝 Генерация краткого содержания
- ⏰ Создание таймкодов для удобной навигации
- 🔄 Обновление статуса в реальном времени

### 🏗️ Архитектурные преимущества
- 📈 **Масштабируемость**: Несколько воркеров для параллельной обработки
- 🛡️ **Отказоустойчивость**: Изолированные контейнеры, восстановление после сбоев
- ⚡ **Производительность**: Асинхронная обработка через Redis Queue
- 🔍 **Мониторинг**: Встроенная система мониторинга очередей
- 🔄 **Автообновление**: Watchtower для автоматического обновления

## 🏛️ Архитектура системы

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Telegram Bot   │    │     Redis       │    │ Video Workers   │
│                 │    │                 │    │                 │
│ • Принимает     │◄──►│ • Очереди задач │◄──►│ • Обработка     │
│   файлы         │    │ • Статус задач  │    │   видео/аудио   │
│ • Мониторинг    │    │ • Результаты    │    │ • Whisper AI    │
│ • Уведомления   │    │                 │    │ • Масштабируется│
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Компоненты системы:
1. **Telegram Bot** - Принимает файлы и управляет пользователями
2. **Redis** - Очереди задач и хранение состояний
3. **Video Workers** - Обработка видео/аудио файлов
4. **Shared Storage** - Временные файлы между контейнерами
5. **Watchtower** - Автоматическое обновление

## 🚀 Быстрый старт

### 1. Предварительные требования
- Docker & Docker Compose
- Минимум 4 ГБ RAM
- 2 ГБ свободного места

### 2. Настройка
```bash
# Клонируйте репозиторий
git clone <your-repo-url>
cd video_summarize_bot

# Создайте файл .env
echo "BOT_TOKEN=your_bot_token_here" > .env
echo "ADMIN_USER_ID=your_admin_user_id" >> .env
```

### 3. Запуск микросервисной архитектуры
```bash
# Запуск всех сервисов
docker-compose -f docker-compose.microservices.yml up -d

# Проверка статуса
docker-compose -f docker-compose.microservices.yml ps

# Просмотр логов
docker-compose -f docker-compose.microservices.yml logs -f
```

### 4. Мониторинг (опционально)
```bash
# Запуск с мониторингом Redis
docker-compose -f docker-compose.microservices.yml --profile monitoring up -d

# Redis Commander будет доступен на http://localhost:8081
```

## 🎯 Использование

1. **Найдите бота** в Telegram по токену
2. **Отправьте** команду `/start`
3. **Загрузите** видео или аудио файл
4. **Отслеживайте** статус обработки в реальном времени
5. **Получите** расшифровку и краткое содержание

## 📚 Команды бота

- `/start` - Приветствие и инструкции
- `/help` - Подробная справка
- `/ping` - Проверка работы бота
- `/status` - Статус системы (очередь, воркеры, Redis)

## 🔧 Конфигурация

### Переменные окружения
```bash
# Основные настройки
BOT_TOKEN=your_bot_token_here
ADMIN_USER_ID=your_admin_user_id

# Redis настройки (опционально)
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# Автообновление (опционально)
REPO_USER=your_github_username
REPO_PASS=your_github_token
```

### Масштабирование воркеров
```bash
# Изменить количество воркеров
docker-compose -f docker-compose.microservices.yml up -d --scale video-worker=4
```

## 🛠️ Разработка

### Структура проекта
```
video_summarize_bot/
├── main.py                          # Основной бот
├── worker.py                        # Воркер для обработки
├── decryptor.py                     # Логика расшифровки
├── requirements.txt                 # Зависимости
├── Dockerfile                       # Контейнер бота
├── Dockerfile.worker                # Контейнер воркера
├── docker-compose.microservices.yml # Микросервисная архитектура
├── docker-compose.prod-auto.yml     # Старая монолитная версия
└── README.md                        # Документация
```

### Локальная разработка
```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск Redis локально
docker run -d -p 6379:6379 redis:7-alpine

# Запуск бота
python main.py

# Запуск воркера (в отдельном терминале)
python worker.py
```

## 📊 Мониторинг и логи

### Просмотр логов
```bash
# Все сервисы
docker-compose -f docker-compose.microservices.yml logs -f

# Конкретный сервис
docker-compose -f docker-compose.microservices.yml logs -f telegram-bot
docker-compose -f docker-compose.microservices.yml logs -f video-worker
```

### Мониторинг Redis
```bash
# Подключение к Redis CLI
docker exec -it video_bot_redis redis-cli

# Просмотр очередей
> KEYS *
> LLEN video_processing

# Статистика
> INFO stats
```

## 🔍 Устранение неполадок

### Проблемы с Redis
```bash
# Проверка подключения
docker exec -it video_bot_redis redis-cli ping

# Очистка очередей
docker exec -it video_bot_redis redis-cli FLUSHALL
```

### Проблемы с воркерами
```bash
# Перезапуск воркеров
docker-compose -f docker-compose.microservices.yml restart video-worker

# Масштабирование
docker-compose -f docker-compose.microservices.yml up -d --scale video-worker=1
```

### Проблемы с памятью
```bash
# Мониторинг использования
docker stats

# Ограничение памяти для воркеров
# Добавьте в docker-compose.yml:
# mem_limit: 2g
# mem_reservation: 1g
```

## 🔄 Миграция с монолитной архитектуры

Если у вас была запущена старая версия:

```bash
# Остановите старую версию
docker-compose -f docker-compose.prod-auto.yml down

# Запустите новую микросервисную
docker-compose -f docker-compose.microservices.yml up -d
```

## 📈 Производительность

### Рекомендуемые настройки:
- **2-4 воркера** для обычной нагрузки
- **4-8 воркеров** для высокой нагрузки
- **Минимум 4 ГБ RAM** для системы
- **SSD диск** для быстрой обработки

### Ограничения:
- Максимальный размер файла: 20 МБ
- Максимальная длительность: 10 минут
- Поддерживаемые языки: русский, английский

## 📝 Лицензия

Проект создан для личного использования.

## 🤝 Поддержка

При возникновении проблем:
1. Проверьте логи: `docker-compose logs`
2. Убедитесь, что Redis работает
3. Проверьте статус воркеров
4. Создайте Issue в репозитории 