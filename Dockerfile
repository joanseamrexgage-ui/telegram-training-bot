# ========== BASE IMAGE ==========
FROM python:3.11-slim

# Метаданные образа
LABEL maintainer="training-bot"
LABEL description="Telegram bot for employee training"

# ========== ENVIRONMENT ==========
# Python не будет создавать .pyc файлы
ENV PYTHONDONTWRITEBYTECODE=1
# Python будет выводить логи сразу, без буферизации
ENV PYTHONUNBUFFERED=1

# ========== WORK DIRECTORY ==========
WORKDIR /app

# ========== SYSTEM DEPENDENCIES ==========
# Обновляем пакеты и устанавливаем необходимые зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# ========== PYTHON DEPENDENCIES ==========
# Копируем requirements.txt отдельно для кэширования слоя
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ========== APPLICATION CODE ==========
# Копируем весь код приложения
COPY . .

# ========== DIRECTORIES ==========
# Создаем необходимые директории
RUN mkdir -p logs content/media/videos content/media/images content/media/documents

# ========== USER ==========
# Создаем непривилегированного пользователя для безопасности
RUN useradd -m -u 1000 botuser && \
    chown -R botuser:botuser /app

# Переключаемся на этого пользователя
USER botuser

# ========== HEALTHCHECK ==========
# Проверка работоспособности контейнера
# HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
#   CMD python -c "import sys; sys.exit(0)"

# ========== RUN ==========
# Запуск приложения
CMD ["python", "bot.py"]
