# Fantasy Squad Telegram Bot (Render-ready)

Минимальный Telegram-бот для анализа фамилий игроков по скриншотам и тексту. Работает на Render как отдельный Worker-сервис.

## Структура веток
- **main** — сайт и все остальные файлы
- **telegram-bot** — только бот (`bot.py`, `requirements.txt`, `Procfile`, `.gitignore`, `README.md`)

## Файлы
- `bot.py` — логика Telegram-бота (aiogram3 + EasyOCR)
- `requirements.txt` — зависимости
- `Procfile` — для Render (worker)
- `.gitignore` — исключения для git
- `README.md` — эта инструкция

## Быстрый старт (локально)
1. Получите токен у @BotFather и экспортируйте:
   ```bash
   export BOT_TOKEN=ваш_токен_бота
   ```
2. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```
3. Запустите:
   ```bash
   python bot.py
   ```

## Деплой на Render
1. Создайте ветку `telegram-bot` с этими файлами (без сайта и лишнего).
2. В настройках Render:
   - **Service Type**: Worker
   - **Start Command**: `python bot.py`
   - **Build Command**: `pip install -r requirements.txt`
   - **Env**: Python 3.10+, переменная окружения `BOT_TOKEN`
3. Дождитесь деплоя. Бот будет работать 24/7.

## Как пользоваться
- Отправляйте боту скриншоты (фото, документы jpg/png) или текст — получите список фамилий и их частоты.
- Команды:
  - `/start` — инструкция
  - `/reset` — сбросить данные
  - `/stats` — частоты фамилий по всем отправленным сообщениям/картинкам
  - `/names` — список фамилий

---

**Внимание:**
- Если деплоите через GitHub, используйте только ветку `telegram-bot` для Worker на Render.
- Для сайта используйте ветку `main`.


## Быстрый старт (macOS)

### 1. Установка Python и виртуального окружения

Откройте Терминал и выполните:

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Запуск приложения

```bash
uvicorn main:app --reload --port 8001
```

Откройте браузер и перейдите по адресу:

```
http://localhost:8001
```

---

### 3. Ярлык для запуска сервера и браузера (macOS)

#### Вариант 1: .command-файл на рабочем столе

1. Создайте файл `start_fantasy_ocr.command` на рабочем столе со следующим содержимым:

```bash
#!/bin/bash
cd "$(dirname "$0")/Downloads/Windsurf"
source venv/bin/activate
open -a "Google Chrome" http://localhost:8001
uvicorn main:app --port 8001
```

2. Сделайте файл исполняемым:

```bash
chmod +x ~/Desktop/start_fantasy_ocr.command
```

3. Двойной клик — сервер запустится и откроется в браузере.

---

#### Вариант 2: Автоматическое открытие браузера при запуске

Если хотите, чтобы сервер всегда открывался в браузере, добавьте строку:

```bash
open http://localhost:8001
```

после запуска uvicorn, либо используйте любую команду выше.

---

### 4. Остановка

Для остановки сервера нажмите `Ctrl+C` в терминале.

---

## Примечания
- Все скриншоты и статистика хранятся локально, ничего не отправляется в интернет.
- Для чистки используйте кнопку "Сбросить всё".
- Если нужен автозапуск при старте Mac — добавьте .command-файл в автозагрузку через "Системные настройки" → "Пользователи и группы" → "Объекты входа".

---

**Если возникнут вопросы или потребуется помощь — пишите!**
