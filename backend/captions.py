import subprocess
import whisper

model = whisper.load_model("base")


def _format_timestamp(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def transcribe(video_path: str, srt_path: str) -> None:
    result = model.transcribe(video_path, verbose=False)
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(result["segments"], 1):
            f.write(f"{i}\n")
            f.write(f"{_format_timestamp(seg['start'])} --> {_format_timestamp(seg['end'])}\n")
            f.write(f"{seg['text'].strip()}\n\n")


def burn_captions(video_path: str, srt_path: str, output_path: str) -> None:
    style = (
        "FontName=Arial,FontSize=18,Bold=1,"
        "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
        "Outline=2,Shadow=0,Alignment=2,MarginV=80"
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
