from fastapi import (
    FastAPI,
    UploadFile,
    File,
    Form,
    HTTPException
)

from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import shutil
import uuid

from database import (
    get_connection,
    initialize_database
)

from schemas import (
    UserCreate,
    PostResponse
)


BASE_DIR = Path(__file__).resolve().parent.parent

MEDIA_DIR = BASE_DIR / "media"

MEDIA_DIR.mkdir(
    parents=True,
    exist_ok=True
)


app = FastAPI(
    title="FaceMock API",
    description="Independent mock Facebook platform",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


initialize_database()


# ---------------------------------------
# MEDIA
# ---------------------------------------

app.mount(
    "/media",
    StaticFiles(directory=MEDIA_DIR),
    name="media"
)


# ---------------------------------------
# ROOT
# ---------------------------------------

@app.get("/")
def root():

    return {
        "platform": "FaceMock",
        "status": "online"
    }


# ---------------------------------------
# CREATE USER
# ---------------------------------------

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


# ---------------------------------------
# GET USERS
# ---------------------------------------

@app.get("/api/users")
def get_users():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            username,
            created_at
        FROM users
        ORDER BY id DESC
    """)

    users = [
        dict(row)
        for row in cursor.fetchall()
    ]

    connection.close()

    return users


# ---------------------------------------
# CREATE POST
# ---------------------------------------

@app.post("/api/posts")
def create_post(
    user_id: int = Form(...),
    caption: str = Form(""),
    media: UploadFile | None = File(None)
):

    connection = get_connection()
    cursor = connection.cursor()


    # Check user

    cursor.execute(
        """
        SELECT id
        FROM users
        WHERE id = ?
        """,
        (user_id,)
    )

    user = cursor.fetchone()


    if user is None:

        connection.close()

        raise HTTPException(
            status_code=404,
            detail="User not found"
        )


    media_filename = None
    media_type = None


    # Save media

    if media:

        extension = Path(
            media.filename
        ).suffix

        media_filename = (
            f"{uuid.uuid4()}{extension}"
        )

        media_type = media.content_type

        file_path = (
            MEDIA_DIR /
            media_filename
        )

        with open(
            file_path,
            "wb"
        ) as buffer:

            shutil.copyfileobj(
                media.file,
                buffer
            )


    # Insert post

    cursor.execute(
        """
        INSERT INTO posts
        (
            user_id,
            caption,
            media_filename,
            media_type
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            user_id,
            caption,
            media_filename,
            media_type
        )
    )

    connection.commit()

    post_id = cursor.lastrowid

    connection.close()


    return {

        "id": post_id,

        "message":
            "Post created successfully",

        "media_filename":
            media_filename
    }


# ---------------------------------------
# GET FEED
# ---------------------------------------

@app.get(
    "/api/posts",
    response_model=list[PostResponse]
)
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

        media_url = None


        if row["media_filename"]:

            media_url = (
                f"/media/"
                f"{row['media_filename']}"
            )


        posts.append(

            PostResponse(

                id=row["id"],

                username=row["username"],

                caption=row["caption"],

                media_url=media_url,

                media_type=row["media_type"],

                created_at=row["created_at"]
            )
        )


    return posts