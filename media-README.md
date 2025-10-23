# 📁 Структура директорий content/media/

Эта директория предназначена для хранения медиа-файлов бота.

## 📂 videos/
Директория для хранения обучающих видео:
- Инструкции по работе с оборудованием
- Обучающие материалы для сотрудников
- Видеоинструкции по безопасности

**Формат файлов:** .mp4, .avi, .mov
**Максимальный размер:** 50 MB (ограничение Telegram)

### Рекомендуемая структура:
```
videos/
├── sales/
│   ├── cash_register_tutorial.mp4
│   ├── opening_park.mp4
│   └── closing_park.mp4
├── sport/
│   ├── trampoline_safety.mp4
│   ├── climbing_wall_instructions.mp4
│   └── rope_park_guide.mp4
└── general/
    ├── emergency_procedures.mp4
    └── company_intro.mp4
```

## 📂 documents/
Директория для хранения документов:
- PDF инструкции
- Приказы парка
- Регламенты и правила

**Формат файлов:** .pdf, .docx, .doc
**Максимальный размер:** 50 MB (ограничение Telegram)

### Рекомендуемая структура:
```
documents/
├── orders/
│   ├── order_01_internal_rules.pdf
│   ├── order_02_customer_service.pdf
│   └── order_03_safety_procedures.pdf
├── instructions/
│   ├── equipment_maintenance.pdf
│   └── first_aid_guide.pdf
└── regulations/
    ├── work_schedule.pdf
    └── dress_code.pdf
```

## 🔧 Как использовать

### Добавление видео в код:
```python
from aiogram.types import FSInputFile
from pathlib import Path

video_path = Path("content/media/videos/sales/cash_register_tutorial.mp4")
video = FSInputFile(video_path)
await message.answer_video(video, caption="Инструкция по работе с кассой")
```

### Добавление документа в код:
```python
from aiogram.types import FSInputFile
from pathlib import Path

doc_path = Path("content/media/documents/orders/order_01_internal_rules.pdf")
document = FSInputFile(doc_path)
await message.answer_document(document, caption="Приказ №1 - Внутренний распорядок")
```

## ⚠️ Важные замечания

1. **Размер файлов:** Telegram ограничивает размер файлов до 50 MB для ботов
2. **Кодировка имен:** Используйте только латинские символы и цифры в именах файлов
3. **Резервное копирование:** Храните копии всех медиа-файлов в отдельном месте
4. **Git:** Добавьте эти директории в .gitignore для больших файлов

## 📝 .gitignore рекомендация

```gitignore
# Медиа файлы (если они большие)
content/media/videos/*.mp4
content/media/videos/*.avi
content/media/documents/*.pdf

# Но оставляйте README
!content/media/videos/README.md
!content/media/documents/README.md
```

## 🎬 Пример контента

### Видео для раздела "Отдел продаж":
- `opening_park.mp4` - Открытие парка (checklist)
- `closing_park.mp4` - Закрытие парка (checklist)
- `cash_operations.mp4` - Кассовые операции
- `amocrm_tutorial.mp4` - Работа с amoCRM

### Видео для раздела "Спортивный отдел":
- `trampoline_instructions.mp4` - Инструктаж на батутах
- `climbing_wall_safety.mp4` - Безопасность на скалодроме
- `rope_park_guide.mp4` - Веревочный парк
- `labyrinth_monitoring.mp4` - Контроль в лабиринте

### Документы:
- `order_01_internal_rules.pdf` - Приказ №1: Внутренний распорядок
- `order_02_customer_service.pdf` - Приказ №2: Обслуживание гостей
- `order_03_safety.pdf` - Приказ №3: Техника безопасности
- `order_04_appearance.pdf` - Приказ №4: Внешний вид
- `order_05_ethics.pdf` - Приказ №5: Корпоративная этика

## 📊 Статус директорий

- [x] Директория videos/ создана
- [x] Директория documents/ создана
- [ ] Видео загружены
- [ ] Документы загружены

---

**Дата создания:** 23 октября 2025  
**Автор:** AI Assistant  
**Версия:** 1.0