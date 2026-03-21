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
