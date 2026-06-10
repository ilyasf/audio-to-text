"""
Форматирование транскрипции через Ollama → .docx

Установка (один раз):
    pip install python-docx requests

Запуск:
    python format_docx.py transcript.txt
    python format_docx.py transcript.txt --model qwen2.5:32b
    python format_docx.py transcript.txt --chunk-minutes 10

Требования:
    - Ollama запущен (WSL или Windows), доступен на localhost:11434
    - Любая русскоязычная модель (qwen2.5, llama3.1, mistral и др.)

Как проверить доступные модели:
    ollama list
"""

import re
import sys
import argparse
import requests
from pathlib import Path


OLLAMA_URL = "http://localhost:11434/api/generate"

SYSTEM_PROMPT = """Ты редактор транскрипций. Твоя задача — привести фрагмент расшифровки речи в читаемый вид.

Правила:
1. Раздели текст на абзацы по смыслу (каждый абзац — одна законченная мысль)
2. Если начинается новая тема — добавь заголовок на отдельной строке, начиная с "## "
3. Убери слова-паразиты: ну, вот, типа, э-э, м-м, как бы, значит (если они не несут смысла)
4. Исправь пунктуацию и заглавные буквы
5. НЕ добавляй ничего от себя, не пиши пояснений, не сокращай содержание
6. Верни только структурированный текст"""


def list_ollama_models() -> list[str]:
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


def call_ollama(text: str, model: str) -> str:
    payload = {
        "model": model,
        "system": SYSTEM_PROMPT,
        "prompt": text,
        "stream": False,
    }
    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=300)
        r.raise_for_status()
        return r.json()["response"].strip()
    except requests.exceptions.ConnectionError:
        print("❌ Ollama недоступна на localhost:11434. Убедись что она запущена.")
        sys.exit(1)


def parse_transcript(txt_path: Path) -> list[dict]:
    """Парсит формат [HH:MM:SS --> HH:MM:SS] текст"""
    pattern = re.compile(r"\[(\d{2}:\d{2}:\d{2}) --> (\d{2}:\d{2}:\d{2})\] (.+)")
    segments = []
    for line in txt_path.read_text(encoding="utf-8").splitlines():
        m = pattern.match(line.strip())
        if m:
            segments.append({"start": m.group(1), "end": m.group(2), "text": m.group(3)})
        elif line.strip() and segments:
            # строка без таймстампа — просто текст
            segments.append({"start": "", "end": "", "text": line.strip()})
    return segments


def chunk_segments(segments: list[dict], chunk_minutes: int) -> list[tuple[str, list[dict]]]:
    """Разбивает на куски по N минут"""
    def to_seconds(ts: str) -> int:
        if not ts:
            return 0
        h, m, s = map(int, ts.split(":"))
        return h * 3600 + m * 60 + s

    chunks = []
    current_chunk = []
    chunk_start = None
    chunk_limit = chunk_minutes * 60

    for seg in segments:
        t = to_seconds(seg["start"])
        if chunk_start is None:
            chunk_start = t
        if t - chunk_start >= chunk_limit and current_chunk:
            label = f"{_fmt(chunk_start)} – {_fmt(t)}"
            chunks.append((label, current_chunk))
            current_chunk = []
            chunk_start = t
        current_chunk.append(seg)

    if current_chunk:
        t = to_seconds(current_chunk[-1]["end"] or current_chunk[-1]["start"])
        label = f"{_fmt(chunk_start)} – {_fmt(t)}"
        chunks.append((label, current_chunk))

    return chunks


def _fmt(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def build_docx(structured_chunks: list[tuple[str, str]], output_path: Path):
    from docx import Document
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()

    # Заголовок документа
    title = doc.add_heading("Транскрипция", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    for time_label, structured_text in structured_chunks:
        # Временная метка куска как подзаголовок
        if time_label:
            p = doc.add_paragraph()
            run = p.add_run(f"⏱ {time_label}")
            run.font.size = Pt(9)
            run.font.color.rgb = RGBColor(0x80, 0x80, 0x80)

        for line in structured_text.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("## "):
                doc.add_heading(line[3:], level=2)
            elif line.startswith("# "):
                doc.add_heading(line[2:], level=1)
            else:
                doc.add_paragraph(line)

        doc.add_paragraph("")  # отступ между кусками

    doc.save(str(output_path))


def format_transcript(txt_path: str, model: str, chunk_minutes: int, output_path: str = None):
    txt_path = Path(txt_path)
    if not txt_path.exists():
        print(f"Файл не найден: {txt_path}")
        sys.exit(1)

    if output_path is None:
        output_path = txt_path.with_suffix(".docx")
    else:
        output_path = Path(output_path)

    # Проверяем доступные модели
    models = list_ollama_models()
    if models:
        print(f"Доступные модели Ollama: {', '.join(models)}")
        if model not in models:
            print(f"⚠️  Модель '{model}' не найдена. Используй одну из: {', '.join(models)}")
            sys.exit(1)
    else:
        print("⚠️  Не удалось получить список моделей. Продолжаю с указанной моделью...")

    segments = parse_transcript(txt_path)
    if not segments:
        print("Не удалось распарсить файл. Убедись что это вывод transcribe.py")
        sys.exit(1)

    chunks = chunk_segments(segments, chunk_minutes)
    print(f"Разбито на {len(chunks)} кусков по {chunk_minutes} мин.\n")

    structured_chunks = []
    for i, (label, segs) in enumerate(chunks, 1):
        raw_text = " ".join(s["text"] for s in segs)
        print(f"[{i}/{len(chunks)}] Обрабатываю {label} ({len(raw_text)} символов)...")
        structured = call_ollama(raw_text, model)
        structured_chunks.append((label, structured))

    print(f"\nСоздаю {output_path.name}...")
    build_docx(structured_chunks, output_path)
    print(f"Готово! → {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Транскрипция txt → форматированный docx через Ollama")
    parser.add_argument("txt", help="Путь к .txt файлу от transcribe.py")
    parser.add_argument("--model", default="qwen2.5:7b", help="Модель Ollama (по умолчанию: qwen2.5:7b)")
    parser.add_argument("--chunk-minutes", type=int, default=15, help="Размер куска в минутах (по умолчанию: 15)")
    parser.add_argument("--output", help="Путь к выходному .docx файлу")
    args = parser.parse_args()

    format_transcript(args.txt, args.model, args.chunk_minutes, args.output)