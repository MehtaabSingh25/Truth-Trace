from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles

from pathlib import Path
import shutil
import uuid
import mimetypes

from database import get_connection, initialize_database
from schemas import UserCreate, PostResponse


# --------------------------------------------------
# Paths
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

MEDIA_DIR = BASE_DIR / "media"
FRONTEND_DIR = BASE_DIR / "frontend"

MEDIA_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# FastAPI application
# --------------------------------------------------

app = FastAPI(
    title="InstaMock API",
    description="Independent mock social-media platform",
    version="1.0.0"
)
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1:8002",
        "http://localhost:8002",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# Initialize database
# --------------------------------------------------

initialize_database()


# --------------------------------------------------
# Static media
# --------------------------------------------------

app.mount(
    "/media",
    StaticFiles(directory=MEDIA_DIR),
    name="media"
)
app.mount(
    "/frontend",
    StaticFiles(directory=FRONTEND_DIR, html=True),
    name="frontend"
)


# --------------------------------------------------
# Root endpoint
# --------------------------------------------------

@app.get("/")
def root():
    return {
        "platform": "InstaMock",
        "status": "online"
    }


# --------------------------------------------------
# Create user
# --------------------------------------------------

@app.post("/api/users")
def create_user(user: UserCreate):

    connection = get_connection()
    cursor = connection.cursor()

    try:

        cursor.execute(
            """
            INSERT INTO users (username)
            VALUES (?)
            """,
            (user.username,)
        )

        connection.commit()

        user_id = cursor.lastrowid

    except Exception:
        connection.close()

        raise HTTPException(
            status_code=400,
            detail="Username already exists"
        )

    connection.close()

    return {
        "id": user_id,
        "username": user.username
    }


# --------------------------------------------------
# Get users
# --------------------------------------------------

@app.get("/api/users")
def get_users():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, username, created_at
        FROM users
        ORDER BY id DESC
    """)

    users = [dict(row) for row in cursor.fetchall()]

    connection.close()

    return users


# --------------------------------------------------
# Create post
# --------------------------------------------------

@app.post("/api/posts")
def create_post(
    user_id: int = Form(...),
    caption: str = Form(""),
    media: UploadFile = File(...)
):

    connection = get_connection()
    cursor = connection.cursor()

    # Check whether user exists

    cursor.execute(
        "SELECT id FROM users WHERE id = ?",
        (user_id,)
    )

    user = cursor.fetchone()

    if user is None:
        connection.close()

        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    # Generate unique filename

    media_type = media.content_type
    if not media_type or not (
        media_type.startswith("image/")
        or media_type.startswith("video/")
    ):
        media_type = mimetypes.guess_type(media.filename or "")[0]

    if not media_type or not (
        media_type.startswith("image/")
        or media_type.startswith("video/")
    ):
        connection.close()
        raise HTTPException(
            status_code=415,
            detail="Only image and video media are supported",
        )

    extension = Path(media.filename).suffix

    filename = f"{uuid.uuid4()}{extension}"

    file_path = MEDIA_DIR / filename

    # Save uploaded media

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(media.file, buffer)

    # Store post metadata

    cursor.execute(
        """
        INSERT INTO posts
        (user_id, caption, media_filename, media_type)
        VALUES (?, ?, ?, ?)
        """,
        (
            user_id,
            caption,
            filename,
            media_type
        )
    )

    connection.commit()

    post_id = cursor.lastrowid

    connection.close()

    return {
        "id": post_id,
        "message": "Post created successfully",
        "media_filename": filename
    }


# --------------------------------------------------
# Get feed
# --------------------------------------------------

@app.get("/api/posts", response_model=list[PostResponse])
def get_posts():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            posts.id,
            users.username,
            posts.caption,
            posts.media_filename,
            posts.media_type,
            posts.created_at

        FROM posts

        JOIN users
        ON posts.user_id = users.id

        ORDER BY posts.created_at DESC
    """)

    rows = cursor.fetchall()

    connection.close()

    posts = []

    for row in rows:

        posts.append(
            PostResponse(
                id=row["id"],
                username=row["username"],
                caption=row["caption"],
                media_url=f"/media/{row['media_filename']}",
                media_type=row["media_type"],
                created_at=row["created_at"]
            )
        )

    return posts


@app.delete("/api/posts/{post_id}")
def delete_post(post_id: int):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "SELECT media_filename FROM posts WHERE id = ?",
        (post_id,),
    )
    row = cursor.fetchone()
    if row is None:
        connection.close()
        raise HTTPException(status_code=404, detail="Post not found")

    filename = row["media_filename"]
    if filename:
        media_path = (MEDIA_DIR / filename).resolve()
        if MEDIA_DIR.resolve() not in media_path.parents:
            connection.close()
            raise HTTPException(status_code=500, detail="Invalid media path")
        if media_path.is_file():
            media_path.unlink()

    cursor.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    connection.commit()
    connection.close()
    return {"status": "deleted", "post_id": post_id}