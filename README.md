# ROMI Lab

ROMI Lab — desktop и web-инструмент для маркетинговой аналитики, ROMI-анализа, объединения рекламных и CRM-данных, настройки планов и многопользовательского доступа.

## Что уже есть
- desktop-приложение на PyQt6
- web-кабинет проекта
- импорт рекламных и CRM-данных
- KPI, таблицы, графики и планы
- роли и доступы пользователей
- проверка обновлений desktop-приложения
- сборка Windows `.exe` и `Setup.exe`

## Версия
Текущая версия хранится в файле `VERSION`.

## Сборка desktop
```powershell
powershell -ExecutionPolicy Bypass -File Q:\CODEX\release\build_desktop.ps1 -PythonExe C:\Users\easya\AppData\Local\Python\pythoncore-3.14-64\python.exe
```

## Релизы
- changelog: `CHANGELOG.md`
- release process: `RELEASE_PROCESS.md`
- GitHub Actions workflow: `.github/workflows/release.yml`

## Автообновление
Desktop-приложение проверяет новые версии через GitHub Releases при запуске.
Для этого нужно настроить `github_owner` и `github_repo` в `release_config.json`.

## Цикл обновлений
- правки в коде
- push на GitHub
- новый тег и релиз
- приложение получает обновление через проверку при старте или через Справка -> Проверить обновления`r

