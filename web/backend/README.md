# Backend

Стартовый backend для web-версии BI-сервиса.

## Что нужно для локального запуска

1. Python-пакеты из `requirements.txt`
2. По умолчанию backend использует локальный SQLite-файл:
   `web/backend/analytics_web.db`
3. Если позже понадобится PostgreSQL, можно переопределить переменную:
   `ANALYTICS_WEB_DATABASE_URL`

## Быстрый запуск

```powershell
cd Q:\CODEX\web\backend
& 'C:\Users\easya\AppData\Local\Python\bin\python.exe' -m pip install -r requirements.txt
& 'C:\Users\easya\AppData\Local\Python\bin\python.exe' -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Цель backend

- авторизация пользователей;
- управление проектами;
- ограничение доступа клиентов только к своим проектам;
- хранение подключений рекламы и CRM;
- расчет и отдача отчетов;
- фоновая загрузка данных.

## Ближайшие модули

- `app/main.py`
- `app/core`
- `app/api`
- `app/models`
- `app/services`
- `app/schemas`
