# Web Migration Workspace

Это рабочая структура для перевода текущего desktop-приложения в web-сервис.

## Принцип

Веб-версия должна сохранить текущий пользовательский опыт:

- те же KPI-карточки;
- те же вкладки и фильтры;
- ту же логику работы с проектами;
- тот же экран планирования.

## Каталоги

- `backend` — серверная часть на Python / FastAPI
- `frontend` — web UI на Next.js
- `shared` — переносимое аналитическое ядро, общее для desktop и web

## Что уже готово

- auth и users/projects/project_members
- dashboard проекта из backend
- server-side хранение рекламных и CRM строк
- shared merge/KPI ядро
- web-импорт данных проекта

## Локальный запуск MVP

### Backend

```powershell
cd Q:\CODEX\web\backend
& 'C:\Users\easya\AppData\Local\Python\bin\python.exe' -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

По умолчанию backend использует локальный SQLite:

```text
Q:\CODEX\web\backend\analytics_web.db
```

### Frontend

```powershell
cd Q:\CODEX\web\frontend
npm install
npm run dev
```

## Ближайший практический шаг

Установить Node.js LTS и поднять frontend локально, чтобы проверить сценарий:

1. логин
2. создание проекта
3. импорт JSON
4. пересчет dashboard
