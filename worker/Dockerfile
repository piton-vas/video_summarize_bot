FROM python:3.11-slim

WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Копируем и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY worker.py .
COPY decryptor.py .

# Создаем папку для временных файлов
RUN mkdir -p /tmp/shared

# Пользователь для безопасности
RUN useradd -m -u 1000 worker && chown -R worker:worker /app /tmp/shared
USER worker

# Запускаем воркера
CMD ["python", "worker.py"] 