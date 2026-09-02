from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles

from pathlib import Path
import shutil
import uuid

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
            media.content_type
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