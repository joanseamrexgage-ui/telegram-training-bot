#!/usr/bin/env python3
"""
Скрипт для диагностики SQL ошибки с admin_logs
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text, select
from database.models import AdminLog
from config import Config

async def test_admin_logs_query():
    """Тест генерации SQL для admin_logs"""
    print("🧪 Тестирование SQL генерации для admin_logs...")
    
    try:
        # Тестируем разные типы запросов
        print("\n1. Простой запрос с admin_id:")
        query1 = select(AdminLog).where(AdminLog.admin_id == 1)
        print(f"   SQL: {query1}")
        
        print("\n2. Запрос с действием:")
        query2 = select(AdminLog).where(AdminLog.action == "test")
        print(f"   SQL: {query2}")
        
        print("\n3. Сложный запрос:")
        from datetime import datetime, timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        query3 = (select(AdminLog)
                 .where(AdminLog.timestamp >= cutoff_date)
                 .where(AdminLog.admin_id == 1)
                 .where(AdminLog.action == "test"))
        print(f"   SQL: {query3}")
        
        print("\n4. Тест raw SQL:")
        raw_query = "SELECT * FROM admin_logs WHERE admin_id = ?"
        print(f"   Raw SQL: {raw_query}")
        
        print("\n5. Тест SQLAlchemy text() с параметрами:")
        # Попробуем симулировать ошибку
        from sqlalchemy import text
        test_query = text("SELECT * FROM admin_logs WHERE admin_id = ?")
        print(f"   Text query: {test_query}")
        
        print("\n✅ Все тесты пройдены успешно!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_admin_logs_query())
