#!/usr/bin/env python3
"""
Production-Ready Admin Password Hash Generator v2.0

SEC-001 FIX: bcrypt с солью вместо SHA-256

Использование:
    python generate_admin_hash.py

Или через make:
    make generate-hash
"""

import sys

try:
    import bcrypt
except ImportError:
    print("❌ ERROR: bcrypt not installed!")
    print("Run: pip install bcrypt")
    sys.exit(1)


def generate_password_hash(password: str) -> str:
    """
    Генерирует bcrypt хеш пароля с солью

    SEC-001 FIX: bcrypt вместо SHA-256 для безопасности

    Args:
        password: Пароль в открытом виде

    Returns:
        bcrypt хеш с солью (decoded string)
    """
    # Generate salt and hash
    salt = bcrypt.gensalt(rounds=12)  # 12 rounds = good security/performance balance
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def main():
    print("=" * 60)
    print("PRODUCTION PASSWORD HASH GENERATOR v2.0")
    print("=" * 60)
    print()
    print("SEC-001 FIX: Использует bcrypt с солью (безопаснее SHA-256)")
    print("Хеш нужно добавить в .env файл как ADMIN_PASS_HASH")
    print()
    print("⚠️  ВАЖНО:")
    print("  - Используйте СЛОЖНЫЙ пароль (минимум 12 символов)")
    print("  - Включите буквы, цифры и спецсимволы")
    print("  - Не используйте стандартные пароли")
    print("  - bcrypt автоматически добавляет уникальную соль")
    print()
    print("-" * 60)

    # Запрашиваем пароль
    try:
        password = input("Введите пароль администратора: ")

        if not password:
            print("\n❌ Ошибка: пароль не может быть пустым!")
            sys.exit(1)

        if len(password) < 8:
            print("\n⚠️  Предупреждение: пароль слишком короткий!")
            print("   Рекомендуем минимум 12 символов.")

            confirm = input("\nПродолжить с таким паролем? (yes/no): ")
            if confirm.lower() not in ['yes', 'y', 'да']:
                print("Отменено.")
                sys.exit(0)

        # Подтверждение пароля
        password_confirm = input("Подтвердите пароль: ")

        if password != password_confirm:
            print("\n❌ Ошибка: пароли не совпадают!")
            sys.exit(1)

        # Генерируем хеш
        password_hash = generate_password_hash(password)

        print()
        print("=" * 60)
        print("✅ BCRYPT ХЕШ УСПЕШНО СГЕНЕРИРОВАН")
        print("=" * 60)
        print()
        print(f"Ваш пароль: {password}")
        print(f"bcrypt хеш: {password_hash}")
        print()
        print("ℹ️  Информация о хеше:")
        print(f"   - Алгоритм: bcrypt (с уникальной солью)")
        print(f"   - Длина: {len(password_hash)} символов")
        print(f"   - Rounds: 12 (баланс безопасности/производительности)")
        print()
        print("-" * 60)
        print("ИНСТРУКЦИЯ:")
        print("-" * 60)
        print()
        print("1. Откройте файл .env")
        print()
        print("2. Добавьте или обновите строку:")
        print(f"   ADMIN_PASS_HASH={password_hash}")
        print()
        print("3. Сохраните файл .env")
        print()
        print("4. Перезапустите бота")
        print()
        print("⚠️  SECURITY WARNING:")
        print("  - НЕ ХРАНИТЕ этот вывод в логах или истории команд")
        print("  - НЕ КОММИТЬТЕ .env в Git")
        print("  - УДАЛИТЕ хеш из терминала после копирования")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n\nОтменено пользователем.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
