# Инструкция по развёртыванию Telegram бота

## Описание

Простой Telegram бот на aiogram, который отвечает "pong" на команду "/ping".

## Требования

- Docker
- Docker Compose
- Токен Telegram бота от @BotFather

## Подготовка

### 1. Получение токена бота

1. Откройте Telegram и найдите бота @BotFather
2. Отправьте команду `/newbot`
3. Следуйте инструкциям для создания нового бота
4. Сохраните полученный токен

### 2. Настройка переменных окружения

Создайте файл `.env` в корне проекта со следующим содержимым:

```bash
# Токен Telegram бота
BOT_TOKEN=YOUR_BOT_TOKEN_HERE
```

**Важно!** Замените `YOUR_BOT_TOKEN_HERE` на токен, полученный от @BotFather.

## Развёртывание

### Способ 1: Через Docker Compose (рекомендуется)

1. Клонируйте репозиторий:
```bash
git clone <repository-url>
cd video_summarize_bot
```

2. Создайте файл `.env` с токеном бота (см. выше)

3. Запустите бота:
```bash
docker-compose up -d
```

4. Проверьте статус:
```bash
docker-compose ps
```

5. Просмотр логов:
```bash
docker-compose logs -f
```

### Способ 2: Через Docker без Compose

1. Соберите образ:
```bash
docker build -t telegram-bot .
```

2. Запустите контейнер:
```bash
docker run -d \
  --name video_summarize_bot \
  --restart unless-stopped \
  -e BOT_TOKEN=YOUR_BOT_TOKEN_HERE \
  telegram-bot
```

## Управление ботом

### Остановка бота
```bash
# Через Docker Compose
docker-compose down

# Через Docker
docker stop video_summarize_bot
```

### Перезапуск бота
```bash
# Через Docker Compose
docker-compose restart

# Через Docker
docker restart video_summarize_bot
```

### Обновление бота
```bash
# Остановите текущий контейнер
docker-compose down

# Пересоберите образ
docker-compose build --no-cache

# Запустите обновленный контейнер
docker-compose up -d
```

### Просмотр логов
```bash
# Через Docker Compose
docker-compose logs -f

# Через Docker
docker logs -f video_summarize_bot
```

## Использование бота

1. Найдите вашего бота в Telegram по username
2. Отправьте команду `/start` для начала работы
3. Отправьте команду `/ping` - бот ответит "pong"

## Команды бота

- `/start` - Приветственное сообщение
- `/ping` - Бот отвечает "pong"

## Структура проекта

```
video_summarize_bot/
├── main.py              # Основной код бота
├── requirements.txt     # Зависимости Python
├── Dockerfile          # Docker образ
├── docker-compose.yml  # Docker Compose конфигурация
├── .dockerignore       # Исключения для Docker
├── .env               # Переменные окружения (создать самостоятельно)
└── DEPLOYMENT.md      # Данная инструкция
```

## Устранение проблем

### Бот не отвечает
1. Проверьте, что токен бота указан правильно
2. Убедитесь, что контейнер запущен: `docker-compose ps`
3. Проверьте логи: `docker-compose logs`

### Ошибки при сборке
1. Убедитесь, что Docker и Docker Compose установлены
2. Проверьте, что все файлы присутствуют в директории
3. Попробуйте пересобрать образ: `docker-compose build --no-cache`

### Проблемы с сетью
1. Убедитесь, что у Docker есть доступ к интернету
2. Проверьте настройки брандмауэра
3. Попробуйте перезапустить Docker

## Безопасность

- Никогда не публикуйте токен бота в открытом доступе
- Используйте файл `.env` для хранения секретных данных
- Добавьте `.env` в `.gitignore` если используете Git
- Регулярно обновляйте зависимости

## Поддержка

Если у вас возникли вопросы или проблемы, создайте issue в репозитории проекта. 