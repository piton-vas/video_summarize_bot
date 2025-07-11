# Оптимизация памяти для сервера с 2 ГБ RAM

## Распределение памяти

- **Worker**: 1.5 ГБ (основная обработка)
- **Bot**: 256 МБ
- **Redis**: 128 МБ
- **Система**: остальное

## Настройка swap-файла на сервере

### 1. Проверить текущий swap
```bash
free -h
swapon --show
```

### 2. Создать swap-файл 2ГБ
```bash
# Создать файл
sudo fallocate -l 2G /swapfile

# Установить права
sudo chmod 600 /swapfile

# Настроить как swap
sudo mkswap /swapfile

# Активировать
sudo swapon /swapfile
```

### 3. Добавить в fstab для автозагрузки
```bash
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 4. Оптимизировать использование swap
```bash
# Установить swappiness (как часто использовать swap)
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf

# Применить настройки
sudo sysctl vm.swappiness=10
```

## Оптимизации в коде

### Для больших файлов:
- **Конвертация**: ffmpeg с низким битрейтом (64k, моно, 16кГц)
- **Whisper**: модель "tiny" вместо "base" (-2ГБ памяти)
- **Обработка частями**: файлы >25МБ обрабатываются по 10-минутным кускам
- **Очистка памяти**: автоматическая очистка после каждого этапа

### Преимущества:
- ✅ Нет ограничений на размер файлов
- ✅ Стабильная работа на 2ГБ RAM
- ✅ Медленно, но надежно
- ✅ Автоматическое использование swap при нехватке RAM

### Ожидаемая производительность:
- **Файлы до 25МБ**: обычная скорость
- **Большие файлы**: медленнее, но стабильно
- **1 часовое видео**: ~30-60 минут обработки 