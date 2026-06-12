"""
Transcribe Russian audio files using faster-whisper + RTX 4090

Setup (once):
    pip install faster-whisper
    # ffmpeg is required for m4a: https://ffmpeg.org/download.html
    # or: winget install ffmpeg

Usage:
    python transcribe.py audio.m4a
    python transcribe.py audio.m4a --model large-v3
    python transcribe.py audio.m4a --output result.txt
"""

import sys
import argparse
from pathlib import Path


def transcribe(audio_path: str, model_name: str = "large-v3", output_path: str = None):
    from faster_whisper import WhisperModel

    audio_path = Path(audio_path)
    if not audio_path.exists():
        print(f"File not found: {audio_path}")
        sys.exit(1)

    if output_path is None:
        output_path = audio_path.with_suffix(".txt")
    else:
        output_path = Path(output_path)

    print(f"Loading model {model_name} on GPU...")
    model = WhisperModel(model_name, device="cuda", compute_type="float16")

    print(f"Transcribing: {audio_path.name}")
    segments, info = model.transcribe(
        str(audio_path),
        language="ru",
        beam_size=5,
        vad_filter=True,          # removes silence, speeds up processing
        vad_parameters=dict(min_silence_duration_ms=500),
    )

    print(f"Language: {info.language} (confidence {info.language_probability:.0%})")
    print(f"Duration: {info.duration / 60:.1f} min\n")

    lines = []
    for segment in segments:
        timestamp = f"[{_fmt(segment.start)} --> {_fmt(segment.end)}]"
        line = f"{timestamp} {segment.text.strip()}"
        print(line)
        lines.append(line)

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nDone! Saved to: {output_path}")


def _fmt(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transcribe Russian audio")
    parser.add_argument("audio", help="Path to audio file (.m4a, .mp3, .wav, ...)")
    parser.add_argument(
        "--model",
        default="large-v3",
        choices=["tiny", "base", "small", "medium", "large-v2", "large-v3"],
        help="Whisper model (default: large-v3)",
    )
    parser.add_argument("--output", help="Path to output .txt file (optional)")
    args = parser.parse_args()

    transcribe(args.audio, args.model, args.output)