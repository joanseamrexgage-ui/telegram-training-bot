# ========================================
# VERSION 2.0: Multi-Stage Docker Build
# Оптимизированный production-ready образ
# ========================================

# ========== STAGE 1: BUILDER ==========
# Этап сборки для установки зависимостей
FROM python:3.11-slim AS builder

# Метаданные
LABEL maintainer="training-bot"
LABEL stage="builder"

# Переменные окружения для Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Устанавливаем системные зависимости для сборки
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements и устанавливаем зависимости в виртуальное окружение
COPY requirements.txt .

# Создаем виртуальное окружение и устанавливаем зависимости
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip setuptools wheel && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt


# ========== STAGE 2: RUNTIME ==========
# Финальный минимальный образ для production
FROM python:3.11-slim AS runtime

# Метаданные
LABEL maintainer="training-bot" \
      description="Telegram bot for employee training - Production" \
      version="2.0"

# Переменные окружения
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app:$PYTHONPATH"

WORKDIR /app

# Устанавливаем только runtime зависимости (без компиляторов)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Копируем виртуальное окружение из builder stage
COPY --from=builder /opt/venv /opt/venv

# Создаем непривилегированного пользователя
RUN useradd -m -u 1000 botuser && \
    mkdir -p /app/logs /app/content/media/videos /app/content/media/images /app/content/media/documents && \
    chown -R botuser:botuser /app

# Копируем код приложения
COPY --chown=botuser:botuser . .

# Переключаемся на непривилегированного пользователя
USER botuser

# ========== HEALTHCHECK (VERSION 2.0) ==========
# Проверка работоспособности бота
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python healthcheck.py || exit 1

# ========== EXPOSE ==========
# Документируем, что бот не использует порты (polling mode)
# Если планируется webhook - раскомментируйте нужный порт
# EXPOSE 8080

# ========== RUN ==========
CMD ["python", "-u", "bot.py"]
