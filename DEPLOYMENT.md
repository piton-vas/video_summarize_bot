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

### Настройка Docker Hub

1. Создайте аккаунт на [Docker Hub](https://hub.docker.com/)
2. Создайте новый репозиторий (например: `your-username/video-summarize-bot`)
3. Создайте Access Token:
   - Перейдите в Account Settings → Security
   - Нажмите "New Access Token"
   - Сохраните токен

### Настройка GitHub Secrets

1. Откройте ваш репозиторий на GitHub
2. Перейдите в Settings → Secrets and variables → Actions
3. Добавьте следующие секреты:
   - `DOCKERHUB_USERNAME` - ваш логин Docker Hub
   - `DOCKERHUB_TOKEN` - токен доступа Docker Hub

### Обновление конфигурации

1. Откройте файл `.github/workflows/docker-build.yml`
2. Замените `your-dockerhub-username` на ваш реальный логин Docker Hub
3. Откройте файл `docker-compose.prod.yml`
4. Замените `your-dockerhub-username` на ваш реальный логин Docker Hub

### Как это работает

После настройки, при каждом коммите в ветку `main`:
1. GitHub Actions автоматически соберёт Docker образ
2. Загрузит его в Docker Hub с тегом `latest`
3. Образ будет доступен для развёртывания на любом сервере

## Развёртывание

### Способ 1: Локальная разработка (сборка из исходников)

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

### Способ 2: Продакшн (готовый образ из Docker Hub)

1. Создайте папку для проекта:
```bash
mkdir video_summarize_bot
cd video_summarize_bot
```

2. Скачайте продакшн конфигурацию:
```bash
curl -o docker-compose.yml https://raw.githubusercontent.com/your-username/video_summarize_bot/main/docker-compose.prod.yml
```

3. Создайте файл `.env` с токеном бота (см. выше)

4. Запустите бота:
```bash
docker-compose up -d
```

### Способ 3: Через Docker без Compose

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

#### Локальная разработка
```bash
# Остановите текущий контейнер
docker-compose down

# Пересоберите образ
docker-compose build --no-cache

# Запустите обновленный контейнер
docker-compose up -d
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
# Через Docker Compose
docker-compose logs -f

# Через Docker
docker logs -f video_summarize_bot
```

## Автоматическое обновление на сервере

### Watchtower - автоматическое обновление контейнеров

Для автоматического обновления используйте готовую конфигурацию `docker-compose.prod-auto.yml`:

```bash
# Скачайте конфигурацию с Watchtower
curl -o docker-compose.yml https://raw.githubusercontent.com/your-username/video_summarize_bot/main/docker-compose.prod-auto.yml

# Запустите бота с автообновлением
docker-compose up -d
```

**Как работает Watchtower:**
- Проверяет обновления каждые 5 минут (300 секунд)
- Автоматически скачивает новые версии образов
- Перезапускает контейнеры с новыми версиями
- Очищает старые образы для экономии места

**Настройка интервала обновления:**
```yaml
# В docker-compose.prod-auto.yml можно изменить интервал
command: --interval 600 --cleanup --label-enable  # 10 минут
```

## Мониторинг

### Проверка статуса
```bash
# Статус контейнеров
docker-compose ps

# Использование ресурсов
docker stats video_summarize_bot

# Логи в реальном времени
docker-compose logs -f --tail 50
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
│       └── docker-build.yml        # GitHub Actions для автосборки
├── main.py                         # Основной код бота
├── requirements.txt                # Зависимости Python
├── Dockerfile                      # Docker образ
├── docker-compose.yml              # Локальная разработка
├── docker-compose.prod.yml         # Продакшн конфигурация
├── docker-compose.prod-auto.yml    # Продакшн с Watchtower (автообновление)
├── .dockerignore                   # Исключения для Docker
├── .env                           # Переменные окружения (создать самостоятельно)
└── DEPLOYMENT.md                  # Данная инструкция
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

### Проблемы с GitHub Actions
1. Проверьте, что секреты `DOCKERHUB_USERNAME` и `DOCKERHUB_TOKEN` добавлены в GitHub
2. Убедитесь, что имя образа в `.github/workflows/docker-build.yml` корректное
3. Проверьте логи GitHub Actions во вкладке "Actions" репозитория

### Проблемы с автообновлением (Watchtower)
1. Убедитесь, что Watchtower имеет доступ к Docker socket
2. Проверьте, что образ в Docker Hub обновляется после коммитов
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
- Используйте GitHub Secrets для хранения токенов Docker Hub
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