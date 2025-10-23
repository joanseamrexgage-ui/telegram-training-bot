#!/usr/bin/env python3
"""
Скрипт для генерации SHA-256 хеша пароля администратора

Использование:
    python generate_admin_hash.py

Или через make:
    make generate-hash
"""

import hashlib
import sys


def generate_password_hash(password: str) -> str:
    """
    Генерирует SHA-256 хеш пароля

    Args:
        password: Пароль в открытом виде

    Returns:
        Hex-строка с хешем пароля
    """
    return hashlib.sha256(password.encode()).hexdigest()


def main():
    print("=" * 60)
    print("ГЕНЕРАТОР ХЕША ПАРОЛЯ АДМИНИСТРАТОРА")
    print("=" * 60)
    print()
    print("Этот скрипт создаст SHA-256 хеш для вашего админ-пароля.")
    print("Хеш нужно добавить в .env файл как ADMIN_PASS_HASH")
    print()
    print("⚠️  ВАЖНО:")
    print("  - Используйте сложный пароль (минимум 12 символов)")
    print("  - Включите буквы, цифры и спецсимволы")
    print("  - Не используйте стандартные пароли")
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
        print("✅ ХЕШ УСПЕШНО СГЕНЕРИРОВАН")
        print("=" * 60)
        print()
        print(f"Ваш пароль: {password}")
        print(f"SHA-256 хеш: {password_hash}")
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
        print("⚠️  НЕ ХРАНИТЕ ЭТО СООБЩЕНИЕ И НЕ КОММИТЬТЕ .env В GIT!")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n\nОтменено пользователем.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
