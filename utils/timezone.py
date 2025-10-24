"""
Утилиты для работы с временными зонами.

Все даты в БД хранятся в UTC, но для пользователей отображаются в московском времени (МСК, UTC+3).

ТРЕБОВАНИЯ:
- Python 3.9+ с zoneinfo (стандартная библиотека)
- tzdata - обязателен для Windows: pip install tzdata
- pytz - используется как fallback: pip install pytz

Если tzdata не установлена, будет использован pytz.
"""

from datetime import datetime
from typing import Optional, Any
import sys


# Попытка использовать zoneinfo (Python 3.9+) с fallback на pytz
MOSCOW_TZ: Any = None
TIMEZONE_SOURCE = "unknown"

try:
    # Попытка 1: zoneinfo (стандартная библиотека Python 3.9+)
    from zoneinfo import ZoneInfo
    try:
        MOSCOW_TZ = ZoneInfo("Europe/Moscow")
        TIMEZONE_SOURCE = "zoneinfo"
        print("✓ Timezone: Используется zoneinfo (Python 3.9+)")
    except Exception as ze:
        # Если ошибка с zoneinfo (нет tzdata на Windows)
        print(f"⚠ Ошибка zoneinfo: {ze}")
        print("ℹ Установите tzdata: pip install tzdata")
        raise
except ImportError:
    # Python < 3.9 или zoneinfo недоступен
    print("⚠ zoneinfo недоступен (Python < 3.9 или не установлен)")
    TIMEZONE_SOURCE = "none"

# Fallback на pytz если zoneinfo не удалось
if MOSCOW_TZ is None:
    try:
        import pytz
        MOSCOW_TZ = pytz.timezone("Europe/Moscow")
        TIMEZONE_SOURCE = "pytz"
        print("✓ Timezone: Используется pytz (fallback)")
    except ImportError as pe:
        error_msg = (
            "❌ КРИТИЧЕСКАЯ ОШИБКА: Не найдены библиотеки для работы с временными зонами!\n"
            "\n"
            "Требуется одно из:\n"
            "1. Python 3.9+ с tzdata: pip install tzdata\n"
            "2. pytz (fallback): pip install pytz\n"
            "\n"
            "Установите зависимости:\n"
            "  pip install tzdata pytz\n"
        )
        print(error_msg, file=sys.stderr)
        raise ImportError(error_msg) from pe
    except Exception as pte:
        error_msg = f"❌ Ошибка инициализации pytz: {pte}"
        print(error_msg, file=sys.stderr)
        raise RuntimeError(error_msg) from pte

# Проверка что MOSCOW_TZ успешно инициализирован
if MOSCOW_TZ is None:
    error_msg = (
        "❌ КРИТИЧЕСКАЯ ОШИБКА: Не удалось инициализировать временную зону Moscow!\n"
        "Установите: pip install tzdata pytz\n"
    )
    print(error_msg, file=sys.stderr)
    raise RuntimeError(error_msg)


def utc_to_msk(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Конвертирует datetime из UTC в московское время (МСК, Europe/Moscow).

    Поддерживает как zoneinfo (Python 3.9+), так и pytz (fallback).

    Args:
        dt: datetime объект в UTC (с timezone или naive)

    Returns:
        datetime объект в московском времени или None если dt is None

    Examples:
        >>> from datetime import datetime
        >>> utc_time = datetime(2025, 10, 24, 12, 0, 0)  # 12:00 UTC
        >>> msk_time = utc_to_msk(utc_time)
        >>> print(msk_time)  # 15:00 MSK (UTC+3)
    """
    if dt is None:
        return None

    # Если datetime naive (без timezone), считаем что это UTC
    if dt.tzinfo is None:
        if TIMEZONE_SOURCE == "zoneinfo":
            from zoneinfo import ZoneInfo
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        else:  # pytz
            import pytz
            dt = pytz.utc.localize(dt)

    # Конвертируем в московское время
    if TIMEZONE_SOURCE == "zoneinfo":
        return dt.astimezone(MOSCOW_TZ)
    else:  # pytz
        # pytz требует normalize после astimezone для корректной работы с DST
        return MOSCOW_TZ.normalize(dt.astimezone(MOSCOW_TZ))


def format_msk_datetime(dt: Optional[datetime], fmt: str = "%d.%m.%Y %H:%M:%S") -> str:
    """
    Форматирует datetime в строку с московским временем.

    Args:
        dt: datetime объект (в любой timezone или naive UTC)
        fmt: Формат строки (по умолчанию "DD.MM.YYYY HH:MM:SS")

    Returns:
        Отформатированная строка с датой и временем по МСК или "-" если dt is None

    Examples:
        >>> from datetime import datetime
        >>> utc_time = datetime(2025, 10, 24, 12, 0, 0)
        >>> formatted = format_msk_datetime(utc_time)
        >>> print(formatted)  # "24.10.2025 15:00:00" (МСК)
    """
    if dt is None:
        return "-"

    msk_time = utc_to_msk(dt)
    return msk_time.strftime(fmt)


def format_msk_datetime_with_label(dt: Optional[datetime], fmt: str = "%d.%m.%Y %H:%M:%S") -> str:
    """
    Форматирует datetime в строку с московским временем и меткой (МСК).

    Args:
        dt: datetime объект (в любой timezone или naive UTC)
        fmt: Формат строки (по умолчанию "DD.MM.YYYY HH:MM:SS")

    Returns:
        Отформатированная строка с датой, временем и меткой (МСК) или "-"

    Examples:
        >>> from datetime import datetime
        >>> utc_time = datetime(2025, 10, 24, 12, 0, 0)
        >>> formatted = format_msk_datetime_with_label(utc_time)
        >>> print(formatted)  # "24.10.2025 15:00:00 (МСК)"
    """
    if dt is None:
        return "-"

    msk_time = utc_to_msk(dt)
    return f"{msk_time.strftime(fmt)} (МСК)"


def get_msk_now() -> datetime:
    """
    Получить текущее московское время.

    Поддерживает как zoneinfo (Python 3.9+), так и pytz (fallback).

    Returns:
        datetime объект с текущим временем в timezone Europe/Moscow
    """
    if TIMEZONE_SOURCE == "zoneinfo":
        return datetime.now(MOSCOW_TZ)
    else:  # pytz
        # pytz рекомендует использовать normalize для текущего времени
        return MOSCOW_TZ.normalize(datetime.now(MOSCOW_TZ))
