#!/bin/bash
# Скрипт для запуска Redis локально без прав администратора

echo "🚀 Настройка Redis для разработки..."

# Проверяем, установлен ли Redis
if ! command -v redis-server &> /dev/null; then
    echo "❌ Redis не установлен. Установите Redis:"
    echo "   Ubuntu/Debian: sudo apt install redis-server"
    echo "   macOS: brew install redis"
    echo "   Windows: скачайте с https://redis.io/download"
    exit 1
fi

# Создаем директорию для Redis данных
mkdir -p /tmp/redis-data

# Создаем конфигурацию Redis
cat > /tmp/redis.conf << EOF
# Redis configuration for development
port 6379
bind 127.0.0.1
daemonize no
pidfile /tmp/redis.pid
loglevel notice
logfile /tmp/redis.log
databases 16
save 900 1
save 300 10
save 60 10000
stop-writes-on-bgsave-error yes
rdbcompression yes
rdbchecksum yes
dbfilename dump.rdb
dir /tmp/redis-data
EOF

echo "📝 Конфигурация Redis создана: /tmp/redis.conf"

# Запускаем Redis
echo "🔧 Запуск Redis сервера..."
redis-server /tmp/redis.conf &

# Ждем 2 секунды для запуска
sleep 2

# Проверяем, запустился ли Redis
if redis-cli ping &> /dev/null; then
    echo "✅ Redis успешно запущен!"
    echo "🔍 Проверка подключения:"
    redis-cli ping
    echo ""
    echo "📊 Информация о Redis:"
    redis-cli info | head -5
    echo ""
    echo "🎉 Redis готов к работе с ботом!"
    echo ""
    echo "💡 Для остановки Redis выполните:"
    echo "   redis-cli shutdown"
    echo "   pkill redis-server"
else
    echo "❌ Ошибка запуска Redis"
    echo "🔍 Проверьте лог: /tmp/redis.log"
    exit 1
fi