"""
Минимальные тесты для проверки CI infrastructure.
Эти тесты должны всегда проходить и проверять базовую работоспособность.
"""

import sys
import os


def test_python_version():
    """Проверка версии Python >= 3.10"""
    assert sys.version_info >= (3, 10), f"Python 3.10+ required, got {sys.version_info}"
    print(f"✓ Python version: {sys.version_info.major}.{sys.version_info.minor}")


def test_basic_imports():
    """Проверка базовых Python модулей"""
    try:
        import asyncio
        import logging
        import json
        import os
        import sys
        assert True
    except ImportError as e:
        assert False, f"Basic imports failed: {e}"
    print("✓ Basic Python imports work")


def test_core_dependencies():
    """Проверка установки ключевых зависимостей"""
    dependencies = [
        'aiogram',
        'sqlalchemy',
        'redis',
        'pytest',
        'aiohttp',
    ]

    missing = []
    for dep in dependencies:
        try:
            __import__(dep)
        except ImportError:
            missing.append(dep)

    assert not missing, f"Missing dependencies: {', '.join(missing)}"
    print(f"✓ All {len(dependencies)} core dependencies installed")


def test_bot_file_exists():
    """Проверка существования bot.py"""
    assert os.path.exists('bot.py'), "bot.py not found"
    print("✓ bot.py exists")


def test_bot_syntax():
    """Проверка синтаксиса bot.py"""
    import ast
    try:
        with open('bot.py', 'r', encoding='utf-8') as f:
            code = f.read()
            ast.parse(code)
        assert True
    except SyntaxError as e:
        assert False, f"bot.py has syntax errors: {e}"
    print("✓ bot.py has valid syntax")


def test_config_file_exists():
    """Проверка существования config.py"""
    assert os.path.exists('config.py'), "config.py not found"
    print("✓ config.py exists")


def test_config_syntax():
    """Проверка синтаксиса config.py"""
    import ast
    try:
        with open('config.py', 'r', encoding='utf-8') as f:
            code = f.read()
            ast.parse(code)
        assert True
    except SyntaxError as e:
        assert False, f"config.py has syntax errors: {e}"
    print("✓ config.py has valid syntax")


def test_environment_variable():
    """Проверка переменной окружения ENVIRONMENT"""
    env = os.getenv('ENVIRONMENT', 'unknown')
    assert env in ['unknown', 'testing', 'development', 'production'], \
        f"Invalid ENVIRONMENT: {env}"
    print(f"✓ ENVIRONMENT = {env}")


def test_math_sanity():
    """Санитарная проверка математики"""
    assert 2 + 2 == 4, "Math is broken!"
    assert 10 - 5 == 5, "Math is broken!"
    print("✓ Math works correctly")


def test_async_support():
    """Проверка поддержки asyncio"""
    import asyncio

    async def dummy():
        return 42

    # Запускаем async функцию
    result = asyncio.run(dummy())
    assert result == 42, f"Async failed, got {result}"
    print("✓ Asyncio support works")


def test_pytest_working():
    """Проверка работы pytest"""
    import pytest
    assert pytest is not None
    print(f"✓ Pytest {pytest.__version__} is working")


def test_directory_structure():
    """Проверка структуры директорий проекта"""
    required_dirs = [
        'handlers',
        'database',
        'utils',
        'tests',
    ]

    missing_dirs = [d for d in required_dirs if not os.path.isdir(d)]
    assert not missing_dirs, f"Missing directories: {', '.join(missing_dirs)}"
    print(f"✓ All {len(required_dirs)} required directories exist")


def test_requirements_file():
    """Проверка существования requirements.txt"""
    assert os.path.exists('requirements.txt'), "requirements.txt not found"

    # Читаем и проверяем что файл не пустой
    with open('requirements.txt', 'r') as f:
        content = f.read().strip()
        assert len(content) > 0, "requirements.txt is empty"

    print("✓ requirements.txt exists and is not empty")


if __name__ == "__main__":
    # Можно запустить тесты напрямую
    print("Running minimal tests...")
    test_python_version()
    test_basic_imports()
    test_core_dependencies()
    test_bot_file_exists()
    test_bot_syntax()
    test_config_file_exists()
    test_config_syntax()
    test_environment_variable()
    test_math_sanity()
    test_async_support()
    test_pytest_working()
    test_directory_structure()
    test_requirements_file()
    print("\n✅ All minimal tests passed!")
