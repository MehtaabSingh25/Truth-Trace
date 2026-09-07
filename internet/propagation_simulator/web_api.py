import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from platform_client import PlatformClient
from simulator import INPUT_DIR, run


BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "frontend"
WEB_INPUT_DIR = INPUT_DIR / "web"
WEB_INPUT_DIR.mkdir(parents=True, exist_ok=True)

PLATFORMS = {
    "InstaMock": PlatformClient("InstaMock", "http://127.0.0.1:8000"),
    "XMock": PlatformClient("XMock", "http://127.0.0.1:8001"),
    "FaceMock": PlatformClient("FaceMock", "http://127.0.0.1:8002"),
}

app = FastAPI(
    title="Propagation Simulator Control API",
    description="Upload media and propagate it through all mock platforms.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/frontend", StaticFiles(directory=WEB_DIR, html=True), name="frontend")


@app.get("/")
def root():
    return {"platform": "Propagation Simulator", "status": "online"}


@app.post("/api/users")
def create_dummy_users(username: str = Form(...)):
    created = {}
    for platform_name, platform in PLATFORMS.items():
        user = platform.create_user(f"{username}_{platform_name.lower()}")
        created[platform_name] = user
    return {"users": created}


@app.post("/api/propagate")
def propagate_media(
    media: UploadFile = File(...),
    caption: str = Form("Propagation simulator upload"),
):
    suffix = Path(media.filename or "").suffix.lower()
    allowed = {
        ".jpg", ".jpeg", ".jpe", ".png", ".webp",
        ".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv",
    }
    if suffix not in allowed:
        raise HTTPException(
            status_code=415,
            detail="Unsupported image or video format",
        )

    input_file = WEB_INPUT_DIR / f"{uuid.uuid4()}{suffix}"
    with input_file.open("wb") as destination:
        shutil.copyfileobj(media.file, destination)

    run(input_file, caption=caption or "Propagation simulator upload")
    return {
        "status": "complete",
        "filename": media.filename,
        "caption": caption,
        "message": "Media propagated through InstaMock, XMock, and FaceMock.",
    }
