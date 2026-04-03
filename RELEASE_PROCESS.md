# Релизы desktop-приложения

## Где хранится версия
- Текущая версия приложения задается в файле `Q:\CODEX\VERSION`.
- Перед релизом нужно поднять версию в этом файле, например `0.1.1`.

## Как собрать exe
```powershell
powershell -ExecutionPolicy Bypass -File Q:\CODEX\release\build_desktop.ps1 -PythonExe C:\Users\easya\AppData\Local\Python\pythoncore-3.14-64\python.exe
```

## Что нужно для установщика
- Установленный PyInstaller
- Inno Setup (`ISCC.exe`) для сборки `Setup.exe`

## GitHub Releases
1. Заполнить `Q:\CODEX\release_config.json`:
   - `github_owner`
   - `github_repo`
2. Залить код в GitHub
3. Создать тег версии `vX.Y.Z`
4. GitHub Actions соберет exe и установщик и приложит их к релизу

## Автообновление в приложении
- При старте приложение сравнивает локальную версию с последним GitHub Release.
- Если новая версия есть, приложение предлагает скачать установщик новой версии.

