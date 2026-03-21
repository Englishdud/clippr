import os
import re
import uuid
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from downloader import download_video
from clipper import cut_clip, detect_highlight, reformat_vertical
from captions import burn_captions, generate_title, transcribe

os.makedirs("exports", exist_ok=True)
os.makedirs("temp", exist_ok=True)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

jobs: dict[str, dict] = {}


class ProcessRequest(BaseModel):
    url: str


def _update(job_id: str, status: str, message: str) -> None:
    jobs[job_id]["status"] = status
    jobs[job_id]["message"] = message


def run_pipeline(job_id: str, url: str) -> None:
    raw = f"temp/{job_id}_raw.mp4"
    clip = f"temp/{job_id}_clip.mp4"
    vert = f"temp/{job_id}_vertical.mp4"
    srt = f"temp/{job_id}.srt"
    final = f"exports/{job_id}_final.mp4"

    try:
        _update(job_id, "downloading", "Downloading video...")
        download_video(url, raw)

        _update(job_id, "analyzing", "Detecting highlight...")
        start, end = detect_highlight(raw)

        _update(job_id, "clipping", f"Cutting clip ({int(end - start)}s)...")
        cut_clip(raw, clip, start, end)

        _update(job_id, "reformatting", "Reformatting to 9:16...")
        reformat_vertical(clip, vert)

        _update(job_id, "transcribing", "Generating captions...")
        transcript = transcribe(vert, srt)

        _update(job_id, "burning", "Burning captions...")
        burn_captions(vert, srt, final)

        for path in [raw, clip, vert, srt]:
            if os.path.exists(path):
                os.remove(path)

        jobs[job_id]["status"] = "done"
        jobs[job_id]["message"] = "Ready to download!"
        jobs[job_id]["result_url"] = f"/api/download/{job_id}_final.mp4"
        jobs[job_id]["title"] = generate_title(transcript)

    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["message"] = f"Error: {str(e)}"


@app.post("/api/process")
async def process_video(request: ProcessRequest, background_tasks: BackgroundTasks) -> dict:
    job_id = uuid.uuid4().hex[:16]
    jobs[job_id] = {
        "status": "starting",
        "message": "Starting...",
        "result_url": None,
        "title": None,
        "error": None,
    }
    background_tasks.add_task(run_pipeline, job_id, request.url)
    return {"job_id": job_id}


@app.get("/api/status/{job_id}")
async def get_status(job_id: str) -> dict:
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]


@app.get("/api/download/{filename}")
async def download_file(filename: str) -> FileResponse:
    if not re.match(r"^[a-zA-Z0-9_-]+\.mp4$", filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    file_path = os.path.join("exports", filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type="video/mp4", filename=filename)
