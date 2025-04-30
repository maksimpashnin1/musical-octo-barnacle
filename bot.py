import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
from aiogram.utils.markdown import hbold
import asyncio
import re
from collections import Counter
import os
from io import BytesIO
from PIL import Image
import numpy as np

API_TOKEN = os.getenv("BOT_TOKEN")

# --- EasyOCR ---
try:
    import easyocr
    easyocr_reader = easyocr.Reader(['en'], gpu=False)
except Exception as e:
    easyocr_reader = None

# --- ФУНКЦИЯ ВЫДЕЛЕНИЯ ФАМИЛИЙ ИЗ ТЕКСТА ---
def extract_player_names(raw_text: str):
    clean_text = raw_text.replace('-', ' ').replace('–', ' ')
    lines = [line.strip() for line in clean_text.splitlines() if line.strip()]
    blacklist = set([
        'MIDFIELDER', 'DEFENDER', 'FORWARD', 'GOALKEEPER',
        '–', '-', '•', '(', ')', '/', '|', 'vs', 'V', 'v',
    ])
    club_regex = re.compile(r'^[A-Z]{3,}$')
    name_regex = re.compile(r'^[A-Z][a-zA-Z-]{2,}$')
    flat_names = []
    for line in lines:
        if any(bad == line for bad in blacklist) or club_regex.match(line):
            continue
        words = re.split(r'[ ,.;:]', line)
        for word in words:
            word = word.strip()
            if not word:
                continue
            if word.upper() in blacklist:
                continue
            if club_regex.match(word):
                continue
            word = re.sub(r'^[^a-zA-Z-]+|[^a-zA-Z-]+$', '', word)
            if name_regex.match(word):
                flat_names.append(word)
    # Склейка подряд идущих фамилий с заглавной буквы, если их форма с дефисом есть в raw_text
    i = 0
    result = []
    while i < len(flat_names):
        if (
            i < len(flat_names) - 1
            and flat_names[i][0].isupper()
            and flat_names[i+1][0].isupper()
            and '-' not in flat_names[i]
            and '-' not in flat_names[i+1]
        ):
            combined = f"{flat_names[i]}-{flat_names[i+1]}"
            if combined in raw_text:
                result.append(combined)
                i += 2
                continue
        result.append(flat_names[i])
        i += 1
    return list(dict.fromkeys(result))

# --- НАСТРОЙКА ЛОГГИРОВАНИЯ ---
logging.basicConfig(level=logging.INFO)

# --- СОЗДАНИЕ БОТА И ДИСПЕТЧЕРА ---
bot = Bot(token=API_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# --- СТЕЙТ (в памяти, для одного пользователя) ---
user_texts = {}
user_images = {}

# --- КОМАНДА /start ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer("Отправьте сюда текст из OCR (или скопируйте из картинки), и я выделю фамилии игроков и посчитаю статистику по ним.\n\n<b>Пример:</b>\nSmith\nJones\nBrown\nSmith\n\n<b>Команды:</b>\n/reset — сброс данных\n/stats — показать статистику\n/names — показать список фамилий")

# --- КОМАНДА /reset ---
@dp.message(Command("reset"))
async def cmd_reset(message: types.Message):
    user_texts[message.from_user.id] = []
    await message.answer("Данные сброшены. Отправьте новый текст.")

# --- КОМАНДА /stats ---
@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    texts = user_texts.get(message.from_user.id, [])
    if not texts:
        await message.answer("Нет данных. Сначала отправьте текст.")
        return
    all_text = "\n".join(texts)
    names = extract_player_names(all_text)
    counter = Counter(names)
    if not counter:
        await message.answer("Не найдено фамилий.")
        return
    lines = [f"{hbold(name)} — {cnt}" for name, cnt in counter.most_common()]
    await message.answer("\n".join(lines))

# --- КОМАНДА /names ---
@dp.message(Command("names"))
async def cmd_names(message: types.Message):
    texts = user_texts.get(message.from_user.id, [])
    if not texts:
        await message.answer("Нет данных. Сначала отправьте текст.")
        return
    all_text = "\n".join(texts)
    names = extract_player_names(all_text)
    if not names:
        await message.answer("Не найдено фамилий.")
        return
    await message.answer("\n".join(names))

# --- ОБРАБОТКА ЛЮБОГО ТЕКСТА ---
@dp.message(F.text)
async def handle_text(message: types.Message):
    uid = message.from_user.id
    user_texts.setdefault(uid, []).append(message.text)
    names = extract_player_names(message.text)
    if not names:
        await message.answer("Фамилии не найдены. Попробуйте другой текст.")
        return
    counter = Counter(names)
    lines = [f"{hbold(name)} — {cnt}" for name, cnt in counter.most_common()]
    await message.answer("Фамилии в этом тексте:\n" + "\n".join(lines))

# --- ОБРАБОТКА ФОТО/СКРИНШОТОВ ---
@dp.message(F.photo | (F.document & (F.document.mime_type == 'image/jpeg' or F.document.mime_type == 'image/png')))
async def handle_image(message: types.Message):
    uid = message.from_user.id
    if message.photo:
        file_id = message.photo[-1].file_id  # самое большое по размеру
    else:
        file_id = message.document.file_id
    file = await bot.get_file(file_id)
    file_bytes = await bot.download_file(file.file_path)
    image = Image.open(BytesIO(file_bytes.read())).convert("RGB")
    # OCR через EasyOCR
    if easyocr_reader is None:
        await message.answer("EasyOCR не установлен на сервере. Невозможно обработать изображение.")
        return
    try:
        result = easyocr_reader.readtext(np.array(image), detail=0, paragraph=True)
        ocr_text = "\n".join(result)
        user_texts.setdefault(uid, []).append(ocr_text)
        names = extract_player_names(ocr_text)
        if not names:
            await message.answer("Фамилии не найдены на изображении.")
            return
        counter = Counter(names)
        lines = [f"{hbold(name)} — {cnt}" for name, cnt in counter.most_common()]
        await message.answer("Фамилии на этом изображении:\n" + "\n".join(lines))
    except Exception as e:
        await message.answer(f"Ошибка обработки изображения: {e}")

# --- ЗАПУСК БОТА ---
if __name__ == "__main__":
    import asyncio
    asyncio.run(dp.start_polling(bot))
