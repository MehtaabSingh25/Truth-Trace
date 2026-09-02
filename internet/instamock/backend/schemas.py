from pydantic import BaseModel


class UserCreate(BaseModel):
    username: str


class PostResponse(BaseModel):
    id: int
    username: str
    caption: str
    media_url: str
    media_type: str
    created_at: str