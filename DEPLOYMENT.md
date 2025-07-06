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

## Автоматическая пересборка через GitHub Actions

### Настройка GitHub Container Registry

GitHub Container Registry (GHCR) автоматически настроен для вашего репозитория. Никаких дополнительных настроек не требуется.

### Обновление конфигурации

Конфигурация готова к использованию без дополнительных настроек.

### Как это работает

После настройки, при каждом коммите в ветку `main`:
1. GitHub Actions автоматически соберёт Docker образ
2. Загрузит его в GitHub Container Registry с тегом `latest`
3. Образ будет доступен для развёртывания на любом сервере

## Развёртывание

### Способ 1: Локальная разработка (сборка из исходников)

1. Клонируйте репозиторий:
```bash
git clone <repository-url>
cd video_summarize_bot
```

2. Создайте файл `.env` с токеном бота (см. выше)

3. Соберите и запустите бота:
```bash
docker build -t telegram-bot .
docker run -d \
  --name video_summarize_bot \
  --restart unless-stopped \
  --env-file .env \
  telegram-bot
```

### Способ 2: Продакшн (готовый образ с автообновлением)

1. Создайте папку для проекта:
```bash
mkdir video_summarize_bot
cd video_summarize_bot
```

2. Скачайте продакшн конфигурацию с Watchtower:
```bash
curl -o docker-compose.yml https://raw.githubusercontent.com/piton-vas/video_summarize_bot/main/docker-compose.prod-auto.yml
```

3. Создайте файл `.env` с токеном бота (см. выше)

4. Запустите бота с автообновлением:
```bash
docker-compose up -d
```



## Управление ботом

### Остановка бота
```bash
# Для продакшн (с Watchtower)
docker-compose down

# Для локальной разработки
docker stop video_summarize_bot
```

### Перезапуск бота
```bash
# Для продакшн (с Watchtower)
docker-compose restart

# Для локальной разработки
docker restart video_summarize_bot
```

### Обновление бота

#### Локальная разработка
```bash
# Остановите и удалите текущий контейнер
docker stop video_summarize_bot
docker rm video_summarize_bot

# Пересоберите образ
docker build -t telegram-bot . --no-cache

# Запустите обновленный контейнер
docker run -d \
  --name video_summarize_bot \
  --restart unless-stopped \
  --env-file .env \
  telegram-bot
```

#### Продакшн (ручное обновление)
```bash
# Остановите текущий контейнер
docker-compose down

# Скачайте последнюю версию образа
docker-compose pull

# Запустите обновленный контейнер
docker-compose up -d
```

**Примечание:** При использовании Watchtower обновления происходят автоматически, ручное обновление не требуется.

### Просмотр логов
```bash
# Для продакшн (с Watchtower)
docker-compose logs -f

# Для локальной разработки
docker logs -f video_summarize_bot
```

## Автоматическое обновление на сервере

### Watchtower - автоматическое обновление контейнеров

Watchtower уже включён в основную конфигурацию и автоматически обновляет контейнеры при появлении новых версий образов.


**Настройка интервала обновления:**
```yaml
# В docker-compose.prod-auto.yml можно изменить интервал
command: --interval 600 --cleanup --label-enable  # 10 минут
```

## Мониторинг

### Проверка статуса
```bash
# Для продакшн - статус всех контейнеров
docker-compose ps

# Для любого - использование ресурсов
docker stats video_summarize_bot

# Для продакшн - логи в реальном времени
docker-compose logs -f --tail 50

# Для локальной разработки - логи
docker logs -f --tail 50 video_summarize_bot
```

### Webhook для уведомлений

Можно настроить webhook в GitHub Actions для уведомлений о деплое в Telegram/Slack:

```yaml
- name: Notify deployment
  if: success()
  run: |
    curl -X POST "https://api.telegram.org/bot${{ secrets.NOTIFY_BOT_TOKEN }}/sendMessage" \
    -d chat_id="${{ secrets.NOTIFY_CHAT_ID }}" \
    -d text="✅ Бот успешно обновлён! Версия: ${{ github.sha }}"
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
├── .github/
│   └── workflows/
│       └── docker-build.yml        # GitHub Actions для GHCR
├── main.py                         # Основной код бота
├── requirements.txt                # Зависимости Python
├── Dockerfile                      # Docker образ
├── docker-compose.prod-auto.yml    # Продакшн с Watchtower (автообновление)
├── .dockerignore                   # Исключения для Docker
├── .env                           # Переменные окружения (создать самостоятельно)
└── DEPLOYMENT.md                  # Данная инструкция
```

## Устранение проблем

### Бот не отвечает
1. Проверьте, что токен бота указан правильно
2. Убедитесь, что контейнер запущен: `docker ps` или `docker-compose ps` (для продакшн)
3. Проверьте логи: `docker logs video_summarize_bot` или `docker-compose logs` (для продакшн)

### Ошибки при сборке
1. Убедитесь, что Docker установлен
2. Проверьте, что все файлы присутствуют в директории
3. Попробуйте пересобрать образ: `docker build -t telegram-bot . --no-cache`

### Проблемы с GitHub Actions
1. Убедитесь, что у репозитория есть права на запись в packages
2. Убедитесь, что имя образа в `.github/workflows/docker-build.yml` корректное
3. Проверьте логи GitHub Actions во вкладке "Actions" репозитория

### Проблемы с автообновлением (Watchtower)
1. Убедитесь, что Watchtower имеет доступ к Docker socket
2. Проверьте, что образ в GitHub Container Registry обновляется после коммитов
3. Проверьте логи Watchtower: `docker logs watchtower`
4. Убедитесь, что используется `docker-compose.prod-auto.yml` с Watchtower
5. Проверьте, что контейнер имеет правильные labels для Watchtower

### Проблемы с сетью
1. Убедитесь, что у Docker есть доступ к интернету
2. Проверьте настройки брандмауэра
3. Попробуйте перезапустить Docker

## Безопасность

- Никогда не публикуйте токен бота в открытом доступе
- Используйте файл `.env` для хранения секретных данных
- Добавьте `.env` в `.gitignore` если используете Git
- GitHub Container Registry автоматически приватный для вашего репозитория
- Регулярно обновляйте зависимости
- Используйте непривилегированного пользователя в Docker контейнере

## Производительность

### Оптимизация Docker образа
- Используйте многоэтапную сборку для уменьшения размера образа
- Очищайте кеш pip после установки зависимостей
- Используйте `.dockerignore` для исключения ненужных файлов

### Мониторинг ресурсов
```bash
# Использование памяти и CPU
docker stats video_summarize_bot

# Размер образа
docker images | grep video-summarize-bot
```

## Поддержка

Если у вас возникли вопросы или проблемы, создайте issue в репозитории проекта. 