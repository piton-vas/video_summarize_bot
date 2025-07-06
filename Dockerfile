# Используем официальный образ Python
FROM python:3.11-slim

# Устанавливаем системные зависимости для обработки аудио/видео
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY main.py .
COPY decryptor.py .

# Создаём непривилегированного пользователя
RUN useradd --create-home --shell /bin/bash bot_user && \
    chown -R bot_user:bot_user /app

# Переключаемся на непривилегированного пользователя
USER bot_user

# Запускаем бота
CMD ["python", "main.py"] 