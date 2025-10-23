# ========================================
# VERSION 2.0: Makefile for Telegram Training Bot
# Автоматизация часто используемых команд
# ========================================

.PHONY: help run test lint format clean build docker-build docker-run docker-stop install dev-install migrate backup

# Переменные
PYTHON := python
PIP := pip
PYTEST := pytest
BLACK := black
ISORT := isort
FLAKE8 := flake8
MYPY := mypy
DOCKER := docker
DOCKER_COMPOSE := docker-compose

# Цвета для вывода
COLOR_RESET := \033[0m
COLOR_BOLD := \033[1m
COLOR_GREEN := \033[32m
COLOR_YELLOW := \033[33m
COLOR_BLUE := \033[34m

# ========== HELP ==========
help: ## Показать это сообщение помощи
	@echo "$(COLOR_BOLD)Доступные команды:$(COLOR_RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(COLOR_GREEN)%-20s$(COLOR_RESET) %s\n", $$1, $$2}'

# ========== INSTALLATION ==========
install: ## Установить production зависимости
	@echo "$(COLOR_BLUE)📦 Установка production зависимостей...$(COLOR_RESET)"
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo "$(COLOR_GREEN)✅ Зависимости установлены$(COLOR_RESET)"

dev-install: ## Установить development зависимости
	@echo "$(COLOR_BLUE)📦 Установка development зависимостей...$(COLOR_RESET)"
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install pytest pytest-asyncio pytest-cov black isort flake8 mypy bandit
	@echo "$(COLOR_GREEN)✅ Dev зависимости установлены$(COLOR_RESET)"

# ========== RUN ==========
run: ## Запустить бота
	@echo "$(COLOR_BLUE)🚀 Запуск бота...$(COLOR_RESET)"
	$(PYTHON) bot.py

run-dev: ## Запустить бота в dev режиме с автоперезагрузкой
	@echo "$(COLOR_BLUE)🚀 Запуск в dev режиме...$(COLOR_RESET)"
	$(PYTHON) -m watchdog.watchmedo auto-restart --patterns="*.py" --recursive --signal SIGTERM $(PYTHON) bot.py

# ========== TESTING ==========
test: ## Запустить все тесты
	@echo "$(COLOR_BLUE)🧪 Запуск тестов...$(COLOR_RESET)"
	$(PYTEST) tests/ -v

test-cov: ## Запустить тесты с coverage
	@echo "$(COLOR_BLUE)🧪 Запуск тестов с coverage...$(COLOR_RESET)"
	$(PYTEST) tests/ -v --cov=. --cov-report=html --cov-report=term

test-unit: ## Запустить только unit тесты
	@echo "$(COLOR_BLUE)🧪 Запуск unit тестов...$(COLOR_RESET)"
	$(PYTEST) tests/ -v -m "not integration"

test-fsm: ## Запустить FSM тесты
	@echo "$(COLOR_BLUE)🧪 Запуск FSM тестов...$(COLOR_RESET)"
	$(PYTEST) tests/test_fsm.py -v

test-crud: ## Запустить CRUD тесты
	@echo "$(COLOR_BLUE)🧪 Запуск CRUD тестов...$(COLOR_RESET)"
	$(PYTEST) tests/test_crud.py -v

test-middleware: ## Запустить middleware тесты
	@echo "$(COLOR_BLUE)🧪 Запуск middleware тестов...$(COLOR_RESET)"
	$(PYTEST) tests/test_middleware.py -v

# ========== CODE QUALITY ==========
lint: ## Проверить код линтерами
	@echo "$(COLOR_BLUE)🔍 Запуск линтеров...$(COLOR_RESET)"
	@echo "$(COLOR_YELLOW)Running flake8...$(COLOR_RESET)"
	-$(FLAKE8) . --count --select=E9,F63,F7,F82 --show-source --statistics
	-$(FLAKE8) . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
	@echo "$(COLOR_YELLOW)Running mypy...$(COLOR_RESET)"
	-$(MYPY) . --ignore-missing-imports
	@echo "$(COLOR_GREEN)✅ Линтинг завершен$(COLOR_RESET)"

format: ## Форматировать код (black + isort)
	@echo "$(COLOR_BLUE)✨ Форматирование кода...$(COLOR_RESET)"
	$(BLACK) . --line-length=100
	$(ISORT) . --profile black
	@echo "$(COLOR_GREEN)✅ Код отформатирован$(COLOR_RESET)"

format-check: ## Проверить форматирование без изменений
	@echo "$(COLOR_BLUE)🔍 Проверка форматирования...$(COLOR_RESET)"
	$(BLACK) . --check --line-length=100
	$(ISORT) . --check-only --profile black

security: ## Проверка безопасности с bandit
	@echo "$(COLOR_BLUE)🔒 Проверка безопасности...$(COLOR_RESET)"
	bandit -r . -x tests/,venv/
	@echo "$(COLOR_GREEN)✅ Проверка безопасности завершена$(COLOR_RESET)"

# ========== DATABASE ==========
migrate: ## Создать/обновить схему БД
	@echo "$(COLOR_BLUE)🗄️  Создание/обновление схемы БД...$(COLOR_RESET)"
	$(PYTHON) -c "import asyncio; from database.database import init_db; asyncio.run(init_db())"
	@echo "$(COLOR_GREEN)✅ Миграция выполнена$(COLOR_RESET)"

backup: ## Создать бэкап базы данных
	@echo "$(COLOR_BLUE)💾 Создание backup...$(COLOR_RESET)"
	bash scripts/backup_database.sh
	@echo "$(COLOR_GREEN)✅ Backup создан$(COLOR_RESET)"

# ========== DOCKER ==========
build: docker-build ## Собрать Docker образ

docker-build: ## Собрать Docker образ
	@echo "$(COLOR_BLUE)🐳 Сборка Docker образа...$(COLOR_RESET)"
	$(DOCKER_COMPOSE) build
	@echo "$(COLOR_GREEN)✅ Docker образ собран$(COLOR_RESET)"

docker-run: ## Запустить в Docker
	@echo "$(COLOR_BLUE)🐳 Запуск в Docker...$(COLOR_RESET)"
	$(DOCKER_COMPOSE) up -d
	@echo "$(COLOR_GREEN)✅ Контейнеры запущены$(COLOR_RESET)"
	@echo "$(COLOR_YELLOW)Просмотр логов: make docker-logs$(COLOR_RESET)"

docker-stop: ## Остановить Docker контейнеры
	@echo "$(COLOR_BLUE)🐳 Остановка контейнеров...$(COLOR_RESET)"
	$(DOCKER_COMPOSE) down
	@echo "$(COLOR_GREEN)✅ Контейнеры остановлены$(COLOR_RESET)"

docker-logs: ## Показать логи Docker контейнеров
	$(DOCKER_COMPOSE) logs -f

docker-restart: ## Перезапустить Docker контейнеры
	@echo "$(COLOR_BLUE)🐳 Перезапуск контейнеров...$(COLOR_RESET)"
	$(DOCKER_COMPOSE) restart
	@echo "$(COLOR_GREEN)✅ Контейнеры перезапущены$(COLOR_RESET)"

docker-clean: ## Удалить Docker контейнеры и образы
	@echo "$(COLOR_BLUE)🐳 Очистка Docker...$(COLOR_RESET)"
	$(DOCKER_COMPOSE) down -v --rmi all
	@echo "$(COLOR_GREEN)✅ Docker очищен$(COLOR_RESET)"

# ========== CLEANUP ==========
clean: ## Очистить временные файлы
	@echo "$(COLOR_BLUE)🧹 Очистка временных файлов...$(COLOR_RESET)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.log" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete
	@echo "$(COLOR_GREEN)✅ Очистка завершена$(COLOR_RESET)"

clean-all: clean docker-clean ## Полная очистка (включая Docker)

# ========== DEVELOPMENT ==========
dev: dev-install ## Настроить dev окружение
	@echo "$(COLOR_GREEN)✅ Dev окружение готово$(COLOR_RESET)"
	@echo "$(COLOR_YELLOW)Используйте 'make run-dev' для запуска в dev режиме$(COLOR_RESET)"

check: format-check lint test ## Проверить код перед commit
	@echo "$(COLOR_GREEN)✅ Все проверки пройдены$(COLOR_RESET)"

pre-commit: format lint test ## Запустить все проверки перед commit
	@echo "$(COLOR_GREEN)✅ Готово к commit$(COLOR_RESET)"

# ========== MONITORING ==========
health: ## Проверить здоровье бота
	@echo "$(COLOR_BLUE)🏥 Проверка здоровья...$(COLOR_RESET)"
	$(PYTHON) healthcheck.py
	@echo "$(COLOR_GREEN)✅ Health check пройден$(COLOR_RESET)"

logs: ## Показать логи бота
	@echo "$(COLOR_BLUE)📋 Логи бота:$(COLOR_RESET)"
	tail -f logs/bot.log

logs-error: ## Показать логи ошибок
	@echo "$(COLOR_BLUE)📋 Логи ошибок:$(COLOR_RESET)"
	tail -f logs/errors.log

# ========== INFO ==========
info: ## Показать информацию о проекте
	@echo "$(COLOR_BOLD)=== Telegram Training Bot ===$(COLOR_RESET)"
	@echo "$(COLOR_BLUE)Python:$(COLOR_RESET)       $$(python --version)"
	@echo "$(COLOR_BLUE)Pip:$(COLOR_RESET)          $$(pip --version | cut -d' ' -f1-2)"
	@echo "$(COLOR_BLUE)Pytest:$(COLOR_RESET)       $$(pytest --version 2>/dev/null || echo 'Not installed')"
	@echo "$(COLOR_BLUE)Docker:$(COLOR_RESET)       $$(docker --version 2>/dev/null || echo 'Not installed')"
	@echo "$(COLOR_BLUE)Git branch:$(COLOR_RESET)   $$(git branch --show-current 2>/dev/null || echo 'Not a git repo')"

# ========== DEFAULT ==========
.DEFAULT_GOAL := help
