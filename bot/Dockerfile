FROM python:3.11-slim

WORKDIR /app

# Копируем и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY main.py .

# Создаем папку для временных файлов
RUN mkdir -p /tmp/shared

# Пользователь для безопасности
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app /tmp/shared
USER botuser

# Запускаем бота
CMD ["python", "main.py"] 