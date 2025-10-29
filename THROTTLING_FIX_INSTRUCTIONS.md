# 🚨 URGENT: Throttling Fix Instructions

## Проблема
Бот показывает "Предупреждение 1/3" - используется **старая агрессивная конфигурация** throttling.

## Причина
Production бот работает на ветке без новой конфигурации (вероятно `main` или `feature/phase0-redis-infrastructure`).

Новая конфигурация находится в ветке: **`claude/enterprise-production-readiness-011CUTyYVVwpE2VSmE7uvAuZ`**

---

## 🛠️ РЕШЕНИЕ 1: Merge новой конфигурации в production (РЕКОМЕНДУЕТСЯ)

### Шаг 1: Определите production ветку
```bash
# На production сервере:
git branch --show-current
# Вероятно выведет: main или feature/phase0-redis-infrastructure
```

### Шаг 2: Merge изменений
```bash
# Если production = main:
git checkout main
git merge claude/enterprise-production-readiness-011CUTyYVVwpE2VSmE7uvAuZ --no-ff
git push origin main

# Если production = feature/phase0-redis-infrastructure:
git checkout feature/phase0-redis-infrastructure
git merge claude/enterprise-production-readiness-011CUTyYVVwpE2VSmE7uvAuZ --no-ff
git push origin feature/phase0-redis-infrastructure
```

### Шаг 3: Перезапустите бота
```bash
# Остановите старый процесс
pkill -f "python bot.py"
# ИЛИ если используется systemd:
sudo systemctl restart telegram-bot

# Запустите заново
python bot.py
# ИЛИ
sudo systemctl start telegram-bot
```

### Шаг 4: Проверьте логи
```bash
# Должны увидеть новую конфигурацию:
tail -f logs/bot.log | grep -E "Max tokens: 15|Violation threshold: 8"

# Ожидаемый вывод:
# ✅ ThrottlingMiddlewareV2 initialized with Redis backend
#    Max tokens: 15
#    Refill rate: 2.0 tokens/sec
#    Violation threshold: 8
#    Block duration: 10s
```

---

## 🔥 РЕШЕНИЕ 2: Temporary Quick Fix (если merge невозможен)

Если не можете сделать merge прямо сейчас, примените временный фикс на production:

### На production сервере отредактируйте `bot.py`:

**Найдите строки (около 210-245):**
```python
# Sentinel mode:
throttle_config = RateLimitConfig(
    max_tokens=5,              # Найти эту строку
    refill_rate=0.5,
    violation_threshold=3,
    block_duration=60
)

# Simple mode:
throttling_middleware = await create_redis_throttling(
    redis_url=f"{config.redis.url}/{config.redis.throttle_db}",
    max_tokens=5,              # Найти эту строку
    refill_rate=0.5,
    violation_threshold=3,
    block_duration=60
)
```

**Замените на:**
```python
# Sentinel mode:
throttle_config = RateLimitConfig(
    max_tokens=15,              # ИЗМЕНЕНО: было 5
    refill_rate=2.0,           # ИЗМЕНЕНО: было 0.5
    violation_threshold=8,      # ИЗМЕНЕНО: было 3
    block_duration=10          # ИЗМЕНЕНО: было 60
)

# Simple mode:
throttling_middleware = await create_redis_throttling(
    redis_url=f"{config.redis.url}/{config.redis.throttle_db}",
    max_tokens=15,              # ИЗМЕНЕНО: было 5
    refill_rate=2.0,           # ИЗМЕНЕНО: было 0.5
    violation_threshold=8,      # ИЗМЕНЕНО: было 3
    block_duration=10          # ИЗМЕНЕНО: было 60
)
```

**Перезапустите бота:**
```bash
pkill -f "python bot.py" && python bot.py
```

---

## ⚡ РЕШЕНИЕ 3: Экстренное отключение throttling

Если нужно **полностью отключить** throttling на время:

### На production сервере отредактируйте `bot.py`:

**Найдите строки регистрации middleware (около 226 и 246):**
```python
dp.message.middleware(throttling_middleware)
dp.callback_query.middleware(throttling_middleware)
```

**Закомментируйте:**
```python
# ВРЕМЕННО ОТКЛЮЧЕНО для устранения проблемы с предупреждениями
# dp.message.middleware(throttling_middleware)
# dp.callback_query.middleware(throttling_middleware)
```

**Перезапустите бота:**
```bash
pkill -f "python bot.py" && python bot.py
```

⚠️ **ВНИМАНИЕ**: При этом бот **не защищен от спама**! Используйте только временно.

---

## 🎯 РЕШЕНИЕ 4: Admin bypass для всех пользователей

Если нужно временно отключить throttling для **всех пользователей**:

### На production сервере отредактируйте `middlewares/throttling_v2.py`:

**Найдите метод `__call__` (около строки 314-350):**
```python
async def __call__(self, handler, event, data):
    # Extract user from event
    user = None
    if isinstance(event, Message):
        user = event.from_user
    elif isinstance(event, CallbackQuery):
        user = event.from_user

    # Skip check if user not found
    if not user:
        return await handler(event, data)
```

**Добавьте СРАЗУ после проверки user:**
```python
async def __call__(self, handler, event, data):
    # Extract user from event
    user = None
    if isinstance(event, Message):
        user = event.from_user
    elif isinstance(event, CallbackQuery):
        user = event.from_user

    # Skip check if user not found
    if not user:
        return await handler(event, data)

    # ВРЕМЕННЫЙ BYPASS ДЛЯ ВСЕХ ПОЛЬЗОВАТЕЛЕЙ
    logger.debug(f"⚠️ TEMPORARY: Throttling bypassed for all users")
    return await handler(event, data)
```

**Перезапустите бота:**
```bash
pkill -f "python bot.py" && python bot.py
```

---

## 📊 Проверка после применения

После любого из решений, проверьте:

### 1. Проверка в логах
```bash
tail -100 logs/bot.log | grep -i throttling

# Ожидаемый результат (для РЕШЕНИЯ 1-2):
# Max tokens: 15
# Violation threshold: 8
# Block duration: 10s
```

### 2. Проверка Redis
```bash
redis-cli
> KEYS throttle:*
> TTL throttle:USER_ID:violations

# Если нужно сбросить старые violation counters:
> FLUSHDB
```

### 3. Тестирование в боте
1. Откройте бота
2. Быстро нажмите 10-15 раз на любую кнопку
3. **НЕ должны** увидеть "Подождите немного между действиями"

---

## 🆘 Если ничего не помогло

### Диагностика:
```bash
# 1. Проверьте что бот работает
ps aux | grep bot.py

# 2. Проверьте версию кода
git log --oneline -1

# 3. Проверьте конфигурацию в коде
grep -n "max_tokens" bot.py

# 4. Проверьте логи на ошибки
tail -50 logs/bot.log
```

### Крайняя мера: Полная переинициализация
```bash
# 1. Остановите бота
pkill -f "python bot.py"

# 2. Очистите Redis
redis-cli FLUSHALL

# 3. Переключитесь на ветку с фиксом
git fetch origin
git checkout claude/enterprise-production-readiness-011CUTyYVVwpE2VSmE7uvAuZ
git pull origin claude/enterprise-production-readiness-011CUTyYVVwpE2VSmE7uvAuZ

# 4. Запустите бота
python bot.py
```

---

## ✅ Ожидаемый результат

После применения любого решения:

**До:**
```
Пользователь кликает 6 раз:
⏳ Подождите немного между действиями.
Предупреждение 1/3
```

**После:**
```
Пользователь кликает 15 раз:
✅ Все работает плавно, без предупреждений
```

---

## 📞 Поддержка

Если проблема сохраняется:
1. Проверьте что используется правильная ветка: `git branch --show-current`
2. Проверьте что бот перезапущен: `ps aux | grep bot.py`
3. Проверьте логи на ошибки: `tail -100 logs/bot.log`
4. Сделайте FLUSHDB в Redis для сброса счетчиков

**Коммиты с фиксом:**
- `0f3fc46` - ux: Configure "Invisible" Throttling
- Ветка: `claude/enterprise-production-readiness-011CUTyYVVwpE2VSmE7uvAuZ`
