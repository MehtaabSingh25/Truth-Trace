from pydantic import BaseModel


class UserCreate(BaseModel):
    username: str


class PostResponse(BaseModel):
    id: int
    username: str
    caption: str
    media_url: str | None
    media_type: str | None
    created_at: str