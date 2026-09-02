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
    caption: str
    media_filename: str
    media_type: str
    created_at: str