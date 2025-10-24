"""
Утилиты для работы с временными зонами.

Все даты в БД хранятся в UTC, но для пользователей отображаются в московском времени (МСК, UTC+3).
"""

from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo


# Временная зона для Москвы
MOSCOW_TZ = ZoneInfo("Europe/Moscow")


def utc_to_msk(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Конвертирует datetime из UTC в московское время (МСК, Europe/Moscow).

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
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))

    # Конвертируем в московское время
    return dt.astimezone(MOSCOW_TZ)


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

    Returns:
        datetime объект с текущим временем в timezone Europe/Moscow
    """
    return datetime.now(MOSCOW_TZ)
