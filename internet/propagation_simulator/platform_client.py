import requests
from pathlib import Path


class PlatformClient:

    def __init__(self, name, base_url):
        self.name = name
        self.base_url = base_url.rstrip("/")


    def create_user(self, username):

        response = requests.post(
            f"{self.base_url}/api/users",
            json={
                "username": username
            }
        )

        response.raise_for_status()

        return response.json()


    def create_post(
        self,
        user_id,
        text="",
        media_path=None,
        field_name="media"
    ):

        data = {
            "user_id": str(user_id)
        }

        # Different platforms use different text fields

        if self.name == "FaceMock":
            data["caption"] = text
        else:
            data["text"] = text


        files = None

        if media_path:

            media_path = Path(media_path)

            files = {
                field_name: (
                    media_path.name,
                    open(
                        media_path,
                        "rb"
                    ),
                    self._get_content_type(
                        media_path
                    )
                )
            }


        try:

            response = requests.post(
                f"{self.base_url}/api/posts",
                data=data,
                files=files
            )

            response.raise_for_status()

            return response.json()

        finally:

            if files:
                files[field_name][1].close()


    def _get_content_type(self, path):

        extension = path.suffix.lower()

        content_types = {

            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",

            ".mp4": "video/mp4",
            ".mov": "video/quicktime"
        }

        return content_types.get(
            extension,
            "application/octet-stream"
        )