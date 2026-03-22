#!/usr/bin/env python3
"""
auto_pipeline.py — Clippr.ai batch automation

Reads keywords from watchlist.txt, searches YouTube for the top 5 videos
per keyword, sends each URL to the local Clippr.ai backend, and saves
completed clips to exports/queue/.

Usage (from project root, with backend venv active):
    python auto_pipeline.py

Requirements:
    - Backend venv active: source backend/venv/bin/activate
    - Backend running:     cd backend && uvicorn main:app --port 8000
    - watchlist.txt exists at project root (auto-created on first run)

watchlist.txt syntax:
    - One search keyword per line
    - Lines starting with # are comments and are ignored
    - A line containing only PAUSED (case-insensitive) pauses all processing
    - Blank lines are ignored
"""

import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.request

import yt_dlp

BACKEND = "http://localhost:8000"
WATCHLIST = "watchlist.txt"
QUEUE_DIR = "exports/queue"
MAX_RESULTS = 5
POLL_INTERVAL = 5  # seconds between status polls


# ── HTTP helpers (stdlib only — no requests dependency) ───────────────────────

def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read())


def _post(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


# ── Watchlist ─────────────────────────────────────────────────────────────────

def load_keywords() -> list[str]:
    """Read keywords from watchlist.txt.

    - Auto-creates the file with examples if it doesn't exist.
    - A bare 'PAUSED' line (case-insensitive) pauses the pipeline immediately.
    - Lines starting with # or blank lines are ignored.
    """
    if not os.path.exists(WATCHLIST):
        with open(WATCHLIST, "w") as f:
            f.write("# Clippr.ai Watchlist — one keyword per line\n")
            f.write("# Lines starting with # are ignored\n")
            f.write("# Add a line containing only PAUSED to pause all processing\n")
            f.write("#\n")
            f.write("funny moments\n")
            f.write("fails compilation\n")
        print(f"[+] Created {WATCHLIST} with example keywords.")
        print(f"    Edit it and re-run.\n")
        sys.exit(0)

    keywords = []
    with open(WATCHLIST) as f:
        for line in f:
            stripped = line.strip()
            if stripped.lower() == "paused":
                print("[–] Pipeline is PAUSED.")
                print(f"    Remove or comment out the PAUSED line in {WATCHLIST} to resume.\n")
                sys.exit(0)
            if stripped and not stripped.startswith("#"):
                keywords.append(stripped)
    return keywords


# ── YouTube search ────────────────────────────────────────────────────────────

def search_youtube(keyword: str) -> list[dict]:
    """Return up to MAX_RESULTS videos from YouTube search as {url, title} dicts."""
    opts = {"quiet": True, "no_warnings": True, "extract_flat": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch{MAX_RESULTS}:{keyword}", download=False)

    results = []
    for entry in info.get("entries") or []:
        vid_id = entry.get("id")
        if vid_id:
            results.append({
                "url": f"https://www.youtube.com/watch?v={vid_id}",
                "title": entry.get("title") or "Untitled",
            })
    return results


# ── Backend interaction ───────────────────────────────────────────────────────

def check_backend() -> bool:
    """Return True if the Clippr.ai backend is reachable."""
    try:
        _get(f"{BACKEND}/openapi.json")
        return True
    except Exception:
        return False


def submit(url: str) -> str:
    """POST a URL to /api/process and return the job_id."""
    return _post(f"{BACKEND}/api/process", {"url": url})["job_id"]


def wait_for_job(job_id: str) -> dict | None:
    """Poll /api/status/{job_id} until done or error.

    Prints a dot every POLL_INTERVAL seconds.
    Returns the completed job dict on success, or None on error.
    """
    print("    Polling ", end="", flush=True)
    while True:
        job = _get(f"{BACKEND}/api/status/{job_id}")
        if job["status"] == "done":
            print(" done")
            return job
        if job["status"] == "error":
            print(f" ERROR: {job.get('error', 'unknown error')}")
            return None
        print(".", end="", flush=True)
        time.sleep(POLL_INTERVAL)


# ── Queue management ──────────────────────────────────────────────────────────

def slugify(text: str, maxlen: int = 40) -> str:
    """Convert text to a safe, lowercase filename slug."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "_", text).strip("_")
    return text[:maxlen]


def save_to_queue(job: dict, keyword: str, video_title: str) -> str:
    """Copy the finished clip from exports/ into exports/queue/.

    Output filename: {keyword_slug}__{title_slug}.mp4
    Returns the full destination path.
    """
    os.makedirs(QUEUE_DIR, exist_ok=True)
    # result_url is "/api/download/{job_id}_final.mp4"
    src_filename = job["result_url"].split("/")[-1]
    src = os.path.join("exports", src_filename)
    dest_name = f"{slugify(keyword, 30)}__{slugify(video_title, 40)}.mp4"
    dest = os.path.join(QUEUE_DIR, dest_name)
    shutil.copy2(src, dest)
    return dest


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("Clippr.ai Auto-Pipeline")
    print("=" * 44)

    if not check_backend():
        print(f"\n[!] Backend not reachable at {BACKEND}")
        print("    Start it: cd backend && uvicorn main:app --port 8000\n")
        sys.exit(1)
    print(f"[✓] Backend ready at {BACKEND}\n")

    keywords = load_keywords()
    if not keywords:
        print(f"[!] No keywords found in {WATCHLIST}. Add some and re-run.")
        sys.exit(0)

    print(f"[•] {len(keywords)} keyword(s): {', '.join(keywords)}\n")
    os.makedirs(QUEUE_DIR, exist_ok=True)

    done_count = 0
    fail_count = 0

    for keyword in keywords:
        print(f"── '{keyword}' " + "─" * max(0, 38 - len(keyword)))

        try:
            videos = search_youtube(keyword)
        except Exception as e:
            print(f"  [!] Search failed: {e}\n")
            continue

        if not videos:
            print("  [!] No results found\n")
            continue

        print(f"  {len(videos)} video(s) found\n")

        for i, video in enumerate(videos, 1):
            print(f"  [{i}/{len(videos)}] {video['title'][:70]}")
            print(f"        {video['url']}")

            try:
                job_id = submit(video["url"])
                job = wait_for_job(job_id)

                if job:
                    dest = save_to_queue(job, keyword, video["title"])
                    print(f"    → {dest}")
                    if job.get("title"):
                        print(f"    AI title: {job['title']}")
                    done_count += 1
                else:
                    fail_count += 1

            except Exception as e:
                print(f"    [!] {e}")
                fail_count += 1

            print()

    print("=" * 44)
    print(f"Finished: {done_count} clip(s) saved to {QUEUE_DIR}/")
    if fail_count:
        print(f"          {fail_count} clip(s) failed (see output above)")


if __name__ == "__main__":
    main()
