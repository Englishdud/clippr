# Clippr.ai

A local-only AI video clipping web app. Paste a video URL, and Clippr.ai automatically:

1. Downloads the video (YouTube, Twitter/X, TikTok, Instagram)
2. Detects the most energetic highlight segment (30–60s)
3. Reformats to vertical 9:16 (1080×1920)
4. Generates and burns in captions using local Whisper
5. Exports a clean MP4 — no watermark, no external APIs

---

## System Prerequisites

- **Python 3.10+**
- **Node.js 18+**
- **ffmpeg** (must be on your PATH)

### Install ffmpeg

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg

# Windows (winget)
winget install ffmpeg
```

---

## Project Structure

```
clippr-ai/
├── frontend/          # React + Tailwind UI (Vite)
│   └── src/
│       ├── App.jsx    # Full UI — single component file
│       └── main.jsx
├── backend/           # FastAPI backend
│   ├── main.py        # API endpoints + pipeline orchestration
│   ├── downloader.py  # yt-dlp video download
│   ├── clipper.py     # librosa highlight detection + ffmpeg processing
│   ├── captions.py    # Whisper transcription + ffmpeg caption burn-in
│   └── requirements.txt
├── exports/           # Final MP4s (served for download)
├── temp/              # Intermediate files (auto-cleaned after export)
└── README.md
```

---

## Backend Setup

```bash
cd backend

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

> **Note:** On first run, Whisper will automatically download the `base` model (~150 MB) and cache it locally. Subsequent runs use the cached model.

---

## Frontend Setup

```bash
cd frontend
npm install
```

---

## Running the App

Open two terminals:

**Terminal 1 — Backend**
```bash
cd backend
source venv/bin/activate        # Windows: venv\Scripts\activate
uvicorn main:app --reload --port 8000
```

**Terminal 2 — Frontend**
```bash
cd frontend
npm run dev
```

Then open **http://localhost:5173** in your browser.

---

## Usage

1. Paste a video URL (YouTube, TikTok, Twitter/X, Instagram)
2. Click **Generate Clip**
3. Wait while the pipeline runs (progress shown on screen):
   - Downloading video
   - Detecting highlight
   - Cutting clip
   - Reformatting to 9:16
   - Generating captions
   - Burning captions
4. Click **Download Clip** when ready

---

## Supported Platforms

yt-dlp supports hundreds of sites. Tested with:
- YouTube (`youtube.com`, `youtu.be`)
- Twitter / X (`twitter.com`, `x.com`)
- TikTok (`tiktok.com`)
- Instagram (`instagram.com`)

---

## Notes

- All processing is local — no data leaves your machine
- Exported clips are saved to `exports/` and are yours to keep
- Intermediate files in `temp/` are automatically deleted after export
- The `base` Whisper model balances speed and accuracy; you can change it to `small` or `medium` in `backend/captions.py` for better quality at the cost of speed
