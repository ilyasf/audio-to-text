# Audio to Text — Russian Transcription Pipeline

Local speech-to-text for Russian audio files using [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (OpenAI Whisper) + optional [Ollama](https://ollama.com) post-processing to produce a formatted Word document.

**Pipeline:**
```
audio file (.m4a / .mp3 / .wav)
        ↓  transcribe.py  (faster-whisper + GPU)
   transcript.txt  (with timestamps)
        ↓  format-file.py  (Ollama LLM)
   formatted.docx  (headings, paragraphs, clean text)
```

---

## Requirements

| Component | Version | Notes |
|-----------|---------|-------|
| Python | 3.10+ | |
| NVIDIA GPU | any CUDA-capable | RTX 4090 recommended for large-v3 |
| CUDA Toolkit | **12.x** | Required — see installation below |
| ffmpeg | any | Required for .m4a / .mp3 input |
| Ollama | any | Only needed for `format-file.py` |

### Minimum hardware

`transcribe.py` runs Whisper on the GPU (`device="cuda"`), so an **NVIDIA GPU is required** — there is no CPU fallback in the current code. Ollama (the optional `format-file.py` step) can run on either GPU or CPU.

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| GPU | NVIDIA CUDA-capable, ~2 GB VRAM (`--model small`/`medium`) | RTX 4090 / 24 GB VRAM (`large-v3` + large Ollama models) |
| GPU VRAM for `large-v3` | ~6 GB | 8 GB+ |
| CPU | 4-core x86-64 | 8+ cores (faster Ollama on CPU, faster ffmpeg decode) |
| System RAM | 8 GB | 16 GB+ |
| Disk | ~5 GB free (model cache) | 30 GB+ if using large Ollama models |

> On GPUs with less than ~6 GB VRAM, use `--model small` or `--model medium`. Running Ollama formatting on CPU works but is significantly slower than on GPU.

---

## Installation

### 1. CUDA Toolkit 12

faster-whisper requires `cublas64_12.dll` which ships with CUDA 12.

Download and install CUDA 12.6:
👉 https://developer.nvidia.com/cuda-12-6-0-download-archive

Select: **Windows → x86_64 → 11 → exe (network)**

After installation, verify that this path exists:
```
C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin\cublas64_12.dll
```

Then add it to your system PATH:
1. Press `Win+R` → run `sysdm.cpl`
2. Advanced → Environment Variables
3. Under **System variables**, find `Path` → Edit → New
4. Add: `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin`
5. Click OK → restart your terminal

### 2. ffmpeg

Required to decode .m4a, .mp3, and other compressed formats.

```bash
winget install ffmpeg
```

Or download manually: https://ffmpeg.org/download.html

### 3. Python dependencies

```bash
pip install faster-whisper
pip install python-docx requests   # only needed for format-file.py
```

### 4. Ollama (optional, for .docx output)

Ollama runs local LLMs that structure the raw transcript into a readable document.

Install Ollama: https://ollama.com/download

Then pull a model that handles Russian well (pick one based on your VRAM):

```bash
ollama pull qwen2.5:7b    # ~5 GB  — fast, good quality
ollama pull qwen2.5:14b   # ~9 GB  — better quality
ollama pull qwen2.5:32b   # ~20 GB — best quality, fits on RTX 4090
```

Start Ollama before running `format-file.py`:
```bash
ollama serve
```

---

## Usage

### Step 1 — Transcribe audio to text

```bash
python transcribe.py recording.m4a
```

Output: `recording.txt` with timestamped segments (transcribed text is in the source language, e.g. Russian):
```
[00:00:01 --> 00:00:05] <transcribed speech for this segment>
[00:00:05 --> 00:00:12] ...
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--model` | `large-v3` | Whisper model size (see table below) |
| `--output` | same name as input | Custom output path |

```bash
python transcribe.py recording.m4a --model medium
python transcribe.py recording.m4a --output my_transcript.txt
```

**Whisper model comparison (on RTX 4090):**

| Model | VRAM | Speed on 2h file | Quality |
|-------|------|-----------------|---------|
| `large-v3` | ~6 GB | ~10 min | ⭐⭐⭐⭐⭐ |
| `medium` | ~2.5 GB | ~4 min | ⭐⭐⭐⭐ |
| `small` | ~1 GB | ~2 min | ⭐⭐⭐ |

> The model is downloaded automatically on first run (~3 GB for large-v3) and cached locally.

---

### Step 2 — Format transcript to .docx (optional)

```bash
python format-file.py recording.txt --model qwen2.5:7b
```

Output: `recording.docx` with:
- Headings when the topic changes
- Clean paragraphs (filler words removed)
- Timestamps as section markers
- Proper punctuation and capitalization

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--model` | `qwen2.5:7b` | Ollama model name |
| `--chunk-minutes` | `15` | Minutes per LLM chunk (tune for context size) |
| `--output` | same name as input | Custom output path |

```bash
python format-file.py recording.txt --model qwen2.5:32b --chunk-minutes 20
```

> Long files are automatically split into chunks to stay within LLM context limits. Each chunk is processed independently and merged into a single document.

---

## How it works

**transcribe.py** uses [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — a reimplementation of OpenAI's Whisper model using CTranslate2. It runs on GPU via CUDA and is ~4× faster than the original Whisper with the same accuracy. VAD (Voice Activity Detection) filtering is enabled to skip silence, which further speeds up processing.

**format-file.py** splits the transcript into time-based chunks and sends each to a locally running Ollama LLM with a prompt that instructs it to add paragraph breaks, detect topic headings, and remove speech artifacts. The structured output is then assembled into a .docx file using python-docx.

All processing happens **100% locally** — no data is sent to any external service.

---

## Troubleshooting

**`cublas64_12.dll is not found`**
You have CUDA 13 installed but faster-whisper requires CUDA 12. Install CUDA 12.6 alongside it and add the bin folder to PATH (see Installation → CUDA Toolkit 12).

**`Ollama is not available on localhost:11434`**
Start Ollama with `ollama serve` in WSL or a Windows terminal before running format-file.py.

**Model not found in Ollama**
Run `ollama list` to see installed models, then pass the exact name with `--model`.