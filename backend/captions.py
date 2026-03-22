import os
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


def transcribe(video_path: str, srt_path: str) -> tuple[str, list]:
    result = model.transcribe(video_path, verbose=False)
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(result["segments"], 1):
            f.write(f"{i}\n")
            f.write(f"{_format_timestamp(seg['start'])} --> {_format_timestamp(seg['end'])}\n")
            f.write(f"{seg['text'].strip()}\n\n")
    return result["text"].strip(), result["segments"]


def pick_hook_text(segments: list) -> str:
    """Pick the most dramatic/surprising sentence from Whisper segments using rule-based scoring."""
    if not segments:
        return ""

    dramatic_words = {
        "never", "always", "best", "worst", "only", "first", "last",
        "secret", "truth", "real", "actually", "impossible", "incredible",
        "amazing", "shocking", "crazy", "insane", "huge", "massive",
        "win", "lose", "fail", "prove", "change", "game", "unbelievable",
        "literally", "seriously", "honestly", "wait", "stop", "breaking",
        "warning", "critical", "deadly", "killed", "million", "billion",
        "died", "destroyed", "banned", "exposed", "hidden", "discovered",
        "leaked", "revealed", "confirmed", "wrong", "mistake", "lied",
        "cheated", "caught", "fired", "arrested", "escaped", "survived",
    }

    def score(seg: dict) -> float:
        text = seg["text"].strip()
        words = text.lower().split()
        clean_words = [w.strip(".,!?\"'") for w in words]

        # Prefer punchy length (5-15 words)
        length_score = 1.0 if 5 <= len(words) <= 15 else 0.3

        # Dramatic punctuation is a strong signal
        punct_score = (text.count("!") * 0.5) + (text.count("?") * 0.4)

        # Dramatic/surprising word hits
        drama_score = sum(0.4 for w in clean_words if w in dramatic_words)

        # Numbers suggest specific, credible claims
        number_score = 0.2 if any(c.isdigit() for c in text) else 0.0

        # Slight preference for earlier segments (but not the very first 0.5s which may be filler)
        start = seg.get("start", 0)
        time_score = 0.3 if 0.5 <= start <= 20 else 0.0

        return length_score + punct_score + drama_score + number_score + time_score

    best = max(segments, key=score)
    text = best["text"].strip()

    # Truncate to 12 words so it fits cleanly on screen
    words = text.split()
    if len(words) > 12:
        text = " ".join(words[:12]) + "..."

    return text


def overlay_hook_text(video_path: str, text: str, output_path: str, duration: float = 3.0) -> None:
    """Burn large bold white text with black outline at top of video for the first `duration` seconds."""
    if not text:
        import shutil
        shutil.copy2(video_path, output_path)
        return

    # Escape characters special to ffmpeg drawtext: \, :, ', %
    escaped = (
        text
        .replace("\\", "\\\\")
        .replace("'",  "\u2019")   # replace straight apostrophe with curly to avoid shell quoting issues
        .replace(":",  "\\:")
        .replace("%",  "\\%")
    )

    drawtext = (
        f"drawtext=text='{escaped}'"
        f":fontname=Impact"
        f":fontsize=90"
        f":fontcolor=white"
        f":borderw=5"
        f":bordercolor=black"
        f":x=(w-text_w)/2"
        f":y=80"
        f":enable='between(t,0,{duration})'"
    )

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", drawtext,
            "-c:v", "libx264",
            "-crf", "23",
            "-preset", "fast",
            "-c:a", "copy",
            output_path,
        ],
        check=True,
        capture_output=True,
    )


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


def _srt_to_ass(srt_path: str, ass_path: str) -> None:
    """Convert SRT to ASS with explicit PlayRes=1080x1920 so all units are real pixels."""
    # Style fields (V4+): Name, Fontname, Fontsize, PrimaryColour, SecondaryColour,
    # OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY,
    # Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
    # Bold=-1 means true in ASS.
    # Alignment=2: bottom-center. MarginV=480: 480px from bottom of 1920px frame = 75% down.
    # FontSize=60: 60 real pixels tall — readable but not overwhelming.
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 1080\n"
        "PlayResY: 1920\n"
        "Collisions: Normal\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour,"
        " BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle,"
        " BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Default,Impact,60,"
        "&H00FFFFFF,&H000000FF,&H00000000,&H80000000,"
        "-1,0,0,0,100,100,0,0,1,4,2,2,10,10,480,1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    def _ts(srt_ts: str) -> str:
        """Convert 'HH:MM:SS,mmm' to ASS 'H:MM:SS.cc' (centiseconds)."""
        h, m, rest = srt_ts.strip().split(":")
        s, ms = rest.replace(",", ".").split(".")
        return f"{int(h)}:{m}:{s}.{int(ms) // 10:02d}"

    with open(srt_path, encoding="utf-8") as f:
        content = f.read()

    dialogues = []
    for block in content.strip().split("\n\n"):
        lines = [ln.strip() for ln in block.strip().splitlines() if ln.strip()]
        if not lines:
            continue
        # Skip optional index line
        i = 1 if lines[0].isdigit() else 0
        if i >= len(lines) or "-->" not in lines[i]:
            continue
        start_s, end_s = lines[i].split("-->")
        text_lines = lines[i + 1:]
        if not text_lines:
            continue
        text = r"\N".join(text_lines)
        dialogues.append(f"Dialogue: 0,{_ts(start_s)},{_ts(end_s)},Default,,0,0,0,,{text}")

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("\n".join(dialogues) + "\n")


def burn_captions(video_path: str, srt_path: str, output_path: str) -> None:
    ass_path = srt_path.replace(".srt", ".ass")
    _srt_to_ass(srt_path, ass_path)
    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", video_path,
                "-vf", f"subtitles={ass_path}",
                "-c:v", "libx264",
                "-crf", "23",
                "-preset", "fast",
                "-c:a", "copy",
                output_path,
            ],
            check=True,
            capture_output=True,
        )
    finally:
        if os.path.exists(ass_path):
            os.remove(ass_path)
