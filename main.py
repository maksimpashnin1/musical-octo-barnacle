from fastapi import FastAPI, File, UploadFile, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import pytesseract
from PIL import Image, ImageEnhance, ImageOps
import io
import os
from typing import List
import numpy as np
import re

try:
    import easyocr
except ImportError:
    easyocr = None

# --- ВЫДЕЛЕНИЕ ФАМИЛИЙ ИЗ ТЕКСТА ---
def extract_player_names(raw_text: str) -> List[str]:
    """
    Принимает raw-текст (результат OCR), возвращает список фамилий игроков.
    Логика:
    - Используем только EasyOCR или Tesseract (один движок).
    - Разрешаем фамилии с дефисами, длина от 3 символов.
    - Только первая буква заглавная, только буквы и дефисы.
    - Исключаем клубы (regex) и позиции (blacklist).
    """
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    names = []
    blacklist = set([
        'MIDFIELDER', 'DEFENDER', 'FORWARD', 'GOALKEEPER',
        '–', '-', '•', '(', ')', '/', '|', 'vs', 'V', 'v',
    ])
    club_regex = re.compile(r'^[A-Z]{3,}$')
    name_regex = re.compile(r'^[A-Z][a-zA-Z-]{2,}$')
    # Сбор всех фамилий (без дефисов)
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

from main_utils import clear_uploaded_folder, get_uploaded_images

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploaded", StaticFiles(directory="uploaded"), name="uploaded")

UPLOAD_DIR = "uploaded"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    images = get_uploaded_images(UPLOAD_DIR)
    return templates.TemplateResponse("index.html", {"request": request, "extracted_text": None, "images": images})

@app.api_route("/reset", methods=["GET", "POST"])
def reset(request: Request):
    clear_uploaded_folder(UPLOAD_DIR)
    return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("index.html", {"request": request, "extracted_text": None})

@app.post("/upload", response_class=HTMLResponse)
def upload_images(request: Request, files: List[UploadFile] = File(...)):
    summary_blocks = []
    # --- Новый блок: Подсчёт фамилий по всем скринам ---
    from collections import Counter
    # --- Сохраняем новые файлы, как раньше ---
    already_uploaded = set(get_uploaded_images(UPLOAD_DIR))
    for file in files:
        contents = file.file.read()
        image = Image.open(io.BytesIO(contents))
        image = image.convert("RGB")
        min_width = 600
        if image.width < min_width:
            ratio = min_width / image.width
            new_size = (min_width, int(image.height * ratio))
            image = image.resize(new_size, Image.BICUBIC)
        fname = file.filename
        orig_fname = fname
        counter_suffix = 1
        while fname in already_uploaded:
            fname = f"{os.path.splitext(orig_fname)[0]}_{counter_suffix}{os.path.splitext(orig_fname)[1]}"
            counter_suffix += 1
        save_path = os.path.join(UPLOAD_DIR, fname)
        image.save(save_path)
        already_uploaded.add(fname)
        print(f"[UPLOAD] Сохраняю файл: {fname}")

    # --- Теперь bar chart по всем картинкам в uploaded ---
    from collections import Counter
    all_found_names = []
    images_for_chart = get_uploaded_images(UPLOAD_DIR)
    for fname in images_for_chart:
        img_path = os.path.join(UPLOAD_DIR, fname)
        try:
            image = Image.open(img_path)
            image = image.convert("RGB")
            easy_txt = []
            if easyocr is not None:
                try:
                    reader = easyocr.Reader(['en'], gpu=False)
                    easy_txt = reader.readtext(np.array(image), detail=0, paragraph=True)
                    del reader
                    import gc; gc.collect()
                except Exception as e:
                    print(f"[ERROR] EasyOCR: {e}")
            all_names = extract_player_names("\n".join(easy_txt))
            all_found_names.extend(all_names)
        except Exception as e:
            print(f"[ERROR] Не удалось обработать {fname}: {e}")
    counter = Counter(all_found_names)
    if counter:
        max_count = max(counter.values())
        width_px = 600
        bar_height = 28
        bar_gap = 6
        svg_bars = []
        for idx, (name, cnt) in enumerate(counter.most_common()):
            bar_len = int((cnt / max_count) * (width_px - 180))
            y = idx * (bar_height + bar_gap)
            text_x = 120 + bar_len + 16  # всегда справа от бара
            svg_bars.append(f"""
                <rect x='120' y='{y+4}' width='{bar_len}' height='{bar_height-8}' fill='#4B9CD3' rx='3'/>
                <text x='8' y='{y+bar_height//2+4}' font-size='15' font-family='monospace' fill='#222'>{name}</text>
                <text x='{text_x}' y='{y+bar_height//2+4}' font-size='15' font-family='monospace' fill='#222'>{cnt}</text>
            """)
        svg_height = len(counter) * (bar_height + bar_gap)
        chart_html = f"""
        <svg width='{width_px}' height='{svg_height}' style='background:#f8f8f8;border-radius:8px;margin-bottom:1em;'>
            {''.join(svg_bars)}
        </svg>
        """
    else:
        chart_html = "<div style='color:#888'>Нет фамилий для подсчёта</div>"
    total_players = len(counter)
    total_players_sum = sum(counter.values())
    images = get_uploaded_images(UPLOAD_DIR)
    # --- Анализ парных сочетаний игроков ---
    from itertools import combinations
    from collections import Counter, defaultdict
    squads = []
    for fname in images_for_chart:
        img_path = os.path.join(UPLOAD_DIR, fname)
        try:
            image = Image.open(img_path)
            image = image.convert("RGB")
            easy_txt = []
            if easyocr is not None:
                try:
                    reader = easyocr.Reader(['en'], gpu=False)
                    easy_txt = reader.readtext(np.array(image), detail=0, paragraph=True)
                    del reader
                    import gc; gc.collect()
                except Exception as e:
                    print(f"[ERROR] EasyOCR: {e}")
            all_names = extract_player_names("\n".join(easy_txt))
            squads.append(list(set(all_names)))
        except Exception as e:
            pass
    player_counts = Counter()
    squad_sets = []
    for squad in squads:
        squad_set = set(squad)
        squad_sets.append(squad_set)
        for name in squad_set:
            player_counts[name] += 1
    pair_counter = Counter()
    for squad in squads:
        for a, b in combinations(sorted(squad), 2):
            pair_counter[(a, b)] += 1
    pair_stats = []
    for (a, b), together in pair_counter.items():
        count_a = player_counts[a]
        count_b = player_counts[b]
        percent = together / min(count_a, count_b)
        pair_stats.append((a, b, count_a, count_b, together, percent))
    pair_stats.sort(key=lambda x: (-x[5], -x[4], x[0], x[1]))
    pairs_table_html = """
    <h3 style='margin-top:2.2em;font-size:1.04em;color:#2a2d34;'>Связанные пары игроков (по убыванию процента совместного появления)</h3>
    <table style='width:100%;margin-bottom:1.5em;border-collapse:collapse;font-size:1.06em;'>
        <tr style='background:#f2f6fa;'>
            <th style='padding:6px 12px;text-align:left;'>Игрок 1</th>
            <th style='padding:6px 12px;text-align:left;'>Игрок 2</th>
            <th style='padding:6px 12px;text-align:left;'>Всего у 1</th>
            <th style='padding:6px 12px;text-align:left;'>Всего у 2</th>
            <th style='padding:6px 12px;text-align:left;'>Вместе</th>
            <th style='padding:6px 12px;text-align:left;'>% совместно (от min)</th>
        </tr>
    """
    top_n = 5
    cutoff = None
    if pair_stats:
        if len(pair_stats) > top_n:
            cutoff = pair_stats[top_n-1][5], pair_stats[top_n-1][4]
    filtered_pairs = []
    for a, b, count_a, count_b, together, percent in pair_stats:
        if together > 1 and (cutoff is None or (percent, together) >= cutoff):
            filtered_pairs.append((a, b, count_a, count_b, together, percent))
    for a, b, count_a, count_b, together, percent in filtered_pairs:
        pairs_table_html += f"<tr><td style='padding:6px 12px;'>{a}</td><td style='padding:6px 12px;'>{b}</td><td style='padding:6px 12px;'>{count_a}</td><td style='padding:6px 12px;'>{count_b}</td><td style='padding:6px 12px;'>{together}</td><td style='padding:6px 12px;'>{percent:.2f}</td></tr>"
    if not filtered_pairs:
        pairs_table_html += "<tr><td colspan='6' style='padding:8px 12px;color:#888;'>Нет пар для анализа</td></tr>"
    pairs_table_html += "</table>"
    separated_pairs = []
    player_names = sorted(player_counts.keys())
    for i in range(len(player_names)):
        for j in range(i+1, len(player_names)):
            a, b = player_names[i], player_names[j]
            if player_counts[a] < 2 or player_counts[b] < 2:
                continue
            if pair_counter.get((a, b), 0) == 0:
                separated_pairs.append((a, b, player_counts[a], player_counts[b]))
    separated_table_html = """
    <h3 style='margin-top:2.2em;font-size:1.04em;color:#2a2d34;'>Игроки, которые ни разу не были выбраны вместе (оба появлялись минимум 2 раза)</h3>
    <table style='width:100%;margin-bottom:1.5em;border-collapse:collapse;font-size:1.06em;'>
        <tr style='background:#f2f6fa;'>
            <th style='padding:6px 12px;text-align:left;'>Игрок 1</th>
            <th style='padding:6px 12px;text-align:left;'>Всего у 1</th>
            <th style='padding:6px 12px;text-align:left;'>Игрок 2</th>
            <th style='padding:6px 12px;text-align:left;'>Всего у 2</th>
        </tr>
    """
    for a, b, count_a, count_b in separated_pairs:
        separated_table_html += f"<tr><td style='padding:6px 12px;'>{a}</td><td style='padding:6px 12px;'>{count_a}</td><td style='padding:6px 12px;'>{b}</td><td style='padding:6px 12px;'>{count_b}</td></tr>"
    if not separated_pairs:
        separated_table_html += "<tr><td colspan='4' style='padding:8px 12px;color:#888;'>Нет таких пар</td></tr>"
    separated_table_html += "</table>"
    output = chart_html + pairs_table_html + separated_table_html
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "extracted_text": output, "images": images, "total_players": total_players, "total_players_sum": total_players_sum}
    )
