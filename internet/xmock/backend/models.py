from dataclasses import dataclass


@dataclass
class User:
    id: int
    username: str


@dataclass
class Post:
    id: int
    user_id: int
    username: str
    text: str
    media_filename: str | None
    media_type: str | None
    created_at: str