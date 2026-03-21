import re
import subprocess
import whisper

model = whisper.load_model("small")


def _format_timestamp(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def transcribe(video_path: str, srt_path: str) -> str:
    result = model.transcribe(video_path, verbose=False)
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(result["segments"], 1):
            f.write(f"{i}\n")
            f.write(f"{_format_timestamp(seg['start'])} --> {_format_timestamp(seg['end'])}\n")
            f.write(f"{seg['text'].strip()}\n\n")
    return result["text"].strip()


def generate_title(transcript_text: str) -> str:
    text = transcript_text.strip()
    if not text:
        return "Watch This Clip"

    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if len(s.strip()) > 10]
    if not sentences:
        snippet = text[:60]
        return (snippet.rsplit(" ", 1)[0] + "...") if " " in snippet else snippet

    power_words = {
        "never", "always", "best", "worst", "only", "first", "last",
        "secret", "truth", "real", "actually", "impossible", "incredible",
        "amazing", "shocking", "crazy", "insane", "huge", "massive", "win",
        "lose", "fail", "prove", "change", "game",
    }

    def score(s: str) -> float:
        words = s.lower().split()
        length_score = 1.0 if 5 <= len(words) <= 12 else 0.5
        power_score = sum(0.3 for w in words if w in power_words)
        number_score = 0.2 if any(c.isdigit() for c in s) else 0.0
        return length_score + power_score + number_score

    best = max(sentences, key=score).strip().capitalize()
    if len(best) > 70:
        best = best[:67].rsplit(" ", 1)[0] + "..."
    return best


def burn_captions(video_path: str, srt_path: str, output_path: str) -> None:
    style = (
        "FontName=Impact,FontSize=14,Bold=1,"
        "PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,"
        "BackColour=&H80000000,"
        "Outline=2,Shadow=2,"
        "Alignment=2,MarginV=480"
    )
    vf = f"subtitles={srt_path}:force_style='{style}'"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", vf,
            "-c:v", "libx264",
            "-crf", "23",
            "-preset", "fast",
            "-c:a", "copy",
            output_path,
        ],
        check=True,
        capture_output=True,
    )
