import os
import subprocess
import numpy as np
import librosa


def detect_highlight(video_path: str, min_dur: int = 30, max_dur: int = 60) -> tuple[float, float]:
    wav_path = video_path.replace(".mp4", "_audio.wav")
    subprocess.run(
        ["ffmpeg", "-y", "-i", video_path, "-ac", "1", "-ar", "22050", wav_path],
        check=True,
        capture_output=True,
    )

    try:
        y, sr = librosa.load(wav_path, sr=22050, mono=True)
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)

    hop_length = sr  # 1-second steps
    frame_length = sr * 2  # 2-second analysis window
    rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]

    total_seconds = len(rms)
    window_size = min(max_dur, max(min_dur, int(total_seconds * 0.4)))
    window_size = min(window_size, total_seconds)  # can't be longer than the audio

    if window_size <= 0:
        return 0.0, float(total_seconds)

    scores = np.convolve(rms, np.ones(window_size), mode="valid")
    best_start = int(np.argmax(scores))

    return float(best_start), float(best_start + window_size)


def cut_clip(input_path: str, output_path: str, start: float, end: float) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-to", str(end),
            "-i", input_path,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-avoid_negative_ts", "make_zero",
            output_path,
        ],
        check=True,
        capture_output=True,
    )


def detect_hook(video_path: str, min_dur: float = 3.0, max_dur: float = 5.0) -> tuple[float, float]:
    """Find the most energetic 3–5 second window inside the clip for use as a hook."""
    wav_path = video_path.replace(".mp4", "_hook_audio.wav")
    subprocess.run(
        ["ffmpeg", "-y", "-i", video_path, "-ac", "1", "-ar", "22050", wav_path],
        check=True,
        capture_output=True,
    )

    try:
        y, sr = librosa.load(wav_path, sr=22050, mono=True)
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)

    hop_length = sr // 2          # 0.5-second steps — finer resolution than detect_highlight
    frame_length = sr              # 1-second analysis window
    rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]

    total_duration = len(y) / sr
    target = max(min_dur, min(max_dur, 4.0))   # default 4 seconds
    window_frames = max(1, int(target / 0.5))  # each frame = 0.5s
    window_frames = min(window_frames, len(rms))

    scores = np.convolve(rms, np.ones(window_frames), mode="valid")
    best_frame = int(np.argmax(scores))

    start = best_frame * 0.5
    end = min(start + target, total_duration)
    return float(start), float(end)


def concat_clips(first_path: str, second_path: str, output_path: str) -> None:
    """Concatenate two same-format clips using ffmpeg's concat demuxer (no re-encode)."""
    concat_txt = output_path.replace(".mp4", "_concat.txt")
    with open(concat_txt, "w") as f:
        f.write(f"file '{os.path.abspath(first_path)}'\n")
        f.write(f"file '{os.path.abspath(second_path)}'\n")
    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_txt,
                "-c", "copy",
                output_path,
            ],
            check=True,
            capture_output=True,
        )
    finally:
        if os.path.exists(concat_txt):
            os.remove(concat_txt)


def reformat_vertical(input_path: str, output_path: str) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vf", "crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920",
            "-c:v", "libx264",
            "-crf", "23",
            "-preset", "fast",
            "-c:a", "aac",
            "-b:a", "128k",
            output_path,
        ],
        check=True,
        capture_output=True,
    )
