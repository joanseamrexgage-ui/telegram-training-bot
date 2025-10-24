# 🤖 Telegram-бот для обучения сотрудников

> Production-ready Telegram-бот для обучения и проверки знаний сотрудников развлекательных парков, построенный на **Aiogram 3.x**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Aiogram](https://img.shields.io/badge/Aiogram-3.16-green.svg)](https://docs.aiogram.dev/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-orange.svg)](https://www.sqlalchemy.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[![CI/CD](https://github.com/joanseamrexgage-ui/telegram-training-bot/workflows/CI%2FCD%20Tests%20and%20Build/badge.svg)](https://github.com/joanseamrexgage-ui/telegram-training-bot/actions)
[![codecov](https://codecov.io/gh/joanseamrexgage-ui/telegram-training-bot/branch/main/graph/badge.svg)](https://codecov.io/gh/joanseamrexgage-ui/telegram-training-bot)
[![Security Rating](https://img.shields.io/badge/security-A+-brightgreen.svg)](SECURITY.md)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://github.com/joanseamrexgage-ui/telegram-training-bot/graphs/commit-activity)
[![Production Ready](https://img.shields.io/badge/Production-Ready-success.svg)](REFACTORING_SUMMARY.md)

---

## 📋 Содержание

- [Описание проекта](#-описание-проекта)
- [Функционал](#-функционал)
- [Технологический стек](#-технологический-стек)
- [Структура проекта](#-структура-проекта)
- [Установка и запуск](#-установка-и-запуск)
- [Конфигурация](#-конфигурация)
- [Использование](#-использование)
- [Админ-панель](#-админ-панель)
- [Разработка](#-разработка)
- [FAQ](#-faq)
- [Контакты](#-контакты)

---

## 🎯 Описание проекта

Многофункциональный Telegram-бот для обучения сотрудников сети развлекательных парков, расположенных в ТРЦ **Зеленопарк**, **Каширская плаза** и **Коламбус**.

Бот предоставляет структурированный доступ к:
- 📚 Обучающим материалам и инструкциям
- 🎥 Видео-контенту
- 📄 Корпоративной документации
- 📞 Контактной информации
- ⚠️ Действиям в экстренных ситуациях

---

## ✨ Функционал

### 🟢 Общая информация
- **Адреса парков** - полная информация о локациях с картами проезда
- **Важные телефоны** - контакты администрации, техподдержки, экстренных служб
- **Внештатные ситуации** - пошаговые инструкции при ЧП
- **Зарплата и аванс** - даты выплат, порядок получения
- **Приказы парка** - доступ ко всем корпоративным документам
- **Скидки партнеров** - список партнеров ТРЦ с условиями скидок

### 🔴 Отдел продаж
- **Общая информация** - оргструктура, дресс-код, графики, чаты
- **Открытие/закрытие парка** - чек-листы и видео-инструкции
- **Работа с кассой** - пошаговые алгоритмы и решение ошибок
- **Работа с amoCRM** - руководство по CRM-системе
- **Работа с гостями** - скрипты продаж, работа с возражениями
- **Мошенничество** - база знаний о типичных схемах обмана

### 🟡 Спортивный отдел
- **Общая информация** - требования, график, правила работы
- **Инструкции по оборудованию** - батуты, скалодром, веревочный парк, лабиринт
- **Правила безопасности** - ограничения по возрасту и весу
- **Действия при травмах** - первая помощь, СЛР, психологическая поддержка
- **Экстренные контакты** - номера служб спасения

### 🔒 Администрация парка
- **Авторизация по паролю** - защищенный доступ с хешированием
- **Статистика** - детальная аналитика использования бота
- **Управление пользователями** - блокировка, просмотр активности
- **Редактирование контента** - обновление материалов
- **Рассылка сообщений** - таргетированные объявления

---

## 🛠 Технологический стек

### Core
- **Python 3.11** - основной язык разработки
- **Aiogram 3.16** - асинхронный фреймворк для Telegram Bot API
- **SQLAlchemy 2.0** - ORM для работы с базой данных
- **SQLite / PostgreSQL** - хранение данных

### Additional
- **aiohttp** - асинхронные HTTP-запросы
- **aiofiles** - асинхронная работа с файлами
- **loguru** - продвинутое логирование
- **python-dotenv / environs** - управление переменными окружения
- **Docker & docker-compose** - контейнеризация

### Architecture Patterns
- **FSM (Finite State Machine)** - управление состояниями диалога
- **Middleware** - промежуточная обработка (авторизация, логирование, троттлинг)
- **CRUD паттерн** - чистая работа с БД
- **Callback routing** - структурированная навигация

---

## 📁 Структура проекта

```
training-bot/
├── .env                          # Переменные окружения (не коммитить!)
├── .env.example                  # Шаблон переменных окружения
├── .gitignore                    # Игнорируемые файлы
├── requirements.txt              # Python зависимости
├── README.md                     # Документация (этот файл)
├── Dockerfile                    # Конфигурация Docker-образа
├── docker-compose.yml            # Оркестрация контейнеров
├── bot.py                        # Точка входа приложения
├── config.py                     # Конфигурация (загрузка из .env)
│
├── handlers/                     # Обработчики команд и callback'ов
│   ├── __init__.py
│   ├── start.py                  # Стартовое меню и приветствие
│   ├── general_info.py           # Обработчики "Общая информация"
│   ├── sales.py                  # Обработчики "Отдел продаж"
│   ├── sport.py                  # Обработчики "Спортивный отдел"
│   ├── admin.py                  # Обработчики админ-панели
│   └── common.py                 # Общие обработчики (назад, помощь)
│
├── keyboards/                    # Клавиатуры (inline и reply)
│   ├── __init__.py
│   ├── main_menu.py              # Главное меню
│   ├── general_info_kb.py        # Клавиатуры общей информации
│   ├── sales_kb.py               # Клавиатуры отдела продаж
│   ├── sport_kb.py               # Клавиатуры спортивного отдела
│   └── admin_kb.py               # Админские клавиатуры
│
├── states/                       # FSM состояния
│   ├── __init__.py
│   ├── menu_states.py            # Состояния навигации по меню
│   └── admin_states.py           # Состояния админ-панели
│
├── database/                     # Работа с базой данных
│   ├── __init__.py
│   ├── models.py                 # SQLAlchemy модели
│   ├── database.py               # Инициализация БД, сессии
│   └── crud.py                   # CRUD операции
│
├── middlewares/                  # Мидлвари
│   ├── __init__.py
│   ├── auth.py                   # Авторизация и проверка доступа
│   ├── logging.py                # Логирование действий
│   └── throttling.py             # Защита от спама
│
├── utils/                        # Вспомогательные утилиты
│   ├── __init__.py
│   └── logger.py                 # Настройка логгера
│
├── content/                      # Контент бота
│   ├── texts/                    # Текстовые материалы
│   │   ├── general_info.json     # Тексты общей информации
│   │   ├── sales.json            # Тексты отдела продаж
│   │   └── sport.json            # Тексты спортивного отдела
│   └── media/                    # Медиа-файлы
│       ├── videos/               # Обучающие видео
│       ├── images/               # Инструкции-картинки
│       └── documents/            # PDF-документы, приказы
│
└── logs/                         # Логи приложения
    └── bot.log                   # Основной лог-файл
```

---

## 🚀 Установка и запуск

### Вариант 1: Локальный запуск

#### 1. Клонирование репозитория
```bash
git clone https://github.com/your-username/training-bot.git
cd training-bot
```

#### 2. Создание виртуального окружения
```bash
# Создание venv
python -m venv venv

# Активация (Linux/macOS)
source venv/bin/activate

# Активация (Windows)
venv\Scripts\activate
```

#### 3. Установка зависимостей
```bash
pip install -r requirements.txt
```

> **⚠️ ВАЖНО для Windows:** Для корректной работы временных зон (отображение времени в МСК) обязательно требуется пакет `tzdata`:
> ```bash
> pip install tzdata pytz
> ```
> На Linux/macOS эти пакеты опциональны, но рекомендуются для совместимости.

#### 4. Настройка переменных окружения
```bash
# Копируем шаблон
cp .env.example .env

# Редактируем .env и заполняем:
# - BOT_TOKEN (получите у @BotFather)
# - ADMIN_IDS (ваш Telegram ID)
# - ADMIN_PASSWORD (придумайте надежный пароль)
```

#### 5. Инициализация базы данных
```bash
# База данных создастся автоматически при первом запуске
python bot.py
```

#### 6. Запуск бота
```bash
python bot.py
```

---

### Вариант 2: Docker (рекомендуется для продакшена)

#### 1. Установите Docker и Docker Compose
- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

#### 2. Настройте .env файл
```bash
cp .env.example .env
# Отредактируйте .env
```

#### 3. Запустите контейнеры
```bash
# Сборка и запуск
docker-compose up -d --build

# Просмотр логов
docker-compose logs -f bot

# Остановка
docker-compose down

# Перезапуск
docker-compose restart bot
```

---

## ⚙️ Конфигурация

### .env файл

```env
# Telegram Bot
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz  # От @BotFather
ADMIN_IDS=123456789,987654321                    # Через запятую

# Admin Panel
ADMIN_PASSWORD=your_secure_password_here         # Сложный пароль!

# Database (для SQLite оставьте как есть)
DB_NAME=training_bot

# Database (для PostgreSQL раскомментируйте)
# DB_HOST=localhost
# DB_PORT=5432
# DB_USER=postgres
# DB_PASSWORD=your_db_password
# DB_NAME=training_bot
```

### Получение BOT_TOKEN

1. Найдите [@BotFather](https://t.me/BotFather) в Telegram
2. Отправьте команду `/newbot`
3. Следуйте инструкциям (имя и username бота)
4. Скопируйте полученный токен в `.env`

### Получение вашего Telegram ID

1. Найдите [@userinfobot](https://t.me/userinfobot)
2. Отправьте `/start`
3. Скопируйте ваш ID в `ADMIN_IDS`

---

## 📖 Использование

### Команды бота

- `/start` - Запустить бота и показать главное меню
- `/help` - Показать справку по использованию
- `/cancel` - Отменить текущее действие

### Навигация

- 🏠 **Главное меню** - возврат на стартовую страницу
- ◀️ **Назад** - возврат на предыдущий уровень
- Используйте inline-кнопки для перемещения между разделами

### Добавление контента

#### Видео-инструкции
```bash
# Поместите видео в:
content/media/videos/

# Имена файлов должны соответствовать JSON:
# - cash_register_tutorial.mp4
# - opening_closing.mp4
# - crm_tutorial.mp4
# - trampoline_safety.mp4
# и т.д.
```

#### Документы и приказы
```bash
# Поместите PDF в:
content/media/documents/

# Обновите JSON с путями к файлам
```

#### Текстовый контент
Редактируйте JSON-файлы в `content/texts/`:
- `general_info.json`
- `sales.json`
- `sport.json`

---

## 🔒 Админ-панель

### Вход в админку

1. Нажмите **🔒 Администрация парка** в главном меню
2. Введите пароль (из `ADMIN_PASSWORD` в `.env`)
3. Максимум 3 попытки → блокировка на 5 минут

### Функционал админки

#### 📊 Статистика
- Общая статистика использования бота
- Активные пользователи (сегодня, за неделю)
- Популярные разделы
- Экспорт данных

#### 👥 Управление пользователями
- Просмотр списка всех пользователей
- Поиск пользователя
- Блокировка/разблокировка
- Просмотр истории активности

#### ✏️ Редактирование контента
- Изменение текстов
- Загрузка видео-инструкций
- Загрузка документов
- Управление медиа-файлами

#### 📢 Рассылка сообщений
- Рассылка всем пользователям
- Таргетированная рассылка по отделам
- Рассылка только активным
- История рассылок

#### 📋 Логи
- Просмотр логов активности
- Отслеживание ошибок
- Мониторинг безопасности

### Безопасность админки

✅ **Реализовано:**
- Хеширование пароля (SHA-256)
- Ограничение попыток ввода (3 попытки)
- Временная блокировка (5 минут)
- Логирование всех действий
- Сброс попыток при успешной авторизации

---

## 💻 Разработка

### Добавление нового раздела

1. **Создайте JSON с контентом**
   ```json
   // content/texts/new_section.json
   {
     "main_menu": {
       "title": "Новый раздел",
       "description": "Описание раздела"
     },
     "subsection": {
       "title": "Подраздел",
       "content": "Текст..."
     }
   }
   ```

2. **Создайте клавиатуры**
   ```python
   # keyboards/new_section_kb.py
   from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
   
   def get_new_section_menu():
       return InlineKeyboardMarkup(inline_keyboard=[
           [InlineKeyboardButton(text="Подраздел", callback_data="new_subsection")],
           [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
       ])
   ```

3. **Создайте handler**
   ```python
   # handlers/new_section.py
   from aiogram import Router, F
   from aiogram.types import CallbackQuery
   
   router = Router(name='new_section')
   
   @router.callback_query(F.data == "new_section")
   async def show_new_section(callback: CallbackQuery):
       # Ваша логика
       pass
   ```

4. **Зарегистрируйте в bot.py**
   ```python
   from handlers import new_section
   dp.include_router(new_section.router)
   ```

### Структура callback_data

Используйте единообразную систему именования:
```
{section}_{subsection}_{action}

Примеры:
- general_addresses
- sales_cash_video
- sport_equipment_trampoline
- admin_stats_general
```

### Логирование

```python
from utils.logger import logger

# Уровни логирования
logger.debug("Отладочная информация")
logger.info("Информационное сообщение")
logger.warning("Предупреждение")
logger.error("Ошибка")
logger.critical("Критическая ошибка")

# Логирование исключений
try:
    risky_operation()
except Exception as e:
    logger.exception(f"Ошибка: {e}")
```

### Работа с базой данных

```python
from database.crud import get_or_create_user, log_user_activity

# Создание/получение пользователя
user = await get_or_create_user(
    telegram_id=message.from_user.id,
    username=message.from_user.username,
    first_name=message.from_user.first_name
)

# Логирование активности
await log_user_activity(
    telegram_id=message.from_user.id,
    action="viewed_section",
    section="general_info"
)
```

---

## ❓ FAQ

### Q: Как изменить пароль админки?
**A:** Измените `ADMIN_PASSWORD` в `.env` и перезапустите бота.

### Q: Как добавить нового администратора?
**A:** Добавьте его Telegram ID в `ADMIN_IDS` через запятую.

### Q: Можно ли использовать PostgreSQL вместо SQLite?
**A:** Да! Раскомментируйте PostgreSQL настройки в `.env` и `docker-compose.yml`, установите `asyncpg`.

### Q: Как посмотреть логи?
**A:** 
- Локально: `tail -f logs/bot.log`
- Docker: `docker-compose logs -f bot`

### Q: Бот не отвечает, что делать?
**A:** 
1. Проверьте логи на наличие ошибок
2. Убедитесь что токен правильный
3. Проверьте что бот запущен
4. Проверьте доступность Telegram API

### Q: Как обновить бота?
**A:**
```bash
# Локально
git pull
pip install -r requirements.txt
python bot.py

# Docker
docker-compose pull
docker-compose up -d --build
```

### Q: Как сделать бэкап базы данных?
**A:**
```bash
# SQLite
cp training_bot.db training_bot_backup_$(date +%Y%m%d).db

# PostgreSQL
docker-compose exec db pg_dump -U postgres training_bot > backup.sql
```

---

## 📞 Контакты

- **Разработчик:** Training Bot Team
- **Email:** support@trainingbot.ru
- **Telegram:** @support_trainingbot

---

## 📄 Лицензия

Этот проект распространяется под лицензией MIT. См. файл [LICENSE](LICENSE) для подробностей.

---

## 🙏 Благодарности

- [Aiogram](https://docs.aiogram.dev/) - за отличный фреймворк
- [SQLAlchemy](https://www.sqlalchemy.org/) - за мощный ORM
- Команде разработки за поддержку

---

<div align="center">

**⭐ Если проект был полезен, поставьте звездочку! ⭐**

Made with ❤️ by Training Bot Team

</div>
