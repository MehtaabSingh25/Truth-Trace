
import requests
from urllib.parse import urljoin


class PlatformSource:

    def __init__(self, name, base_url):
        self.name = name
        self.base_url = base_url.rstrip("/")

    def get_posts(self):
        response = requests.get(
            f"{self.base_url}/api/posts",
            timeout=10
        )

        response.raise_for_status()

        return response.json()

    def download_media(self, media_url):
        media_url = urljoin(
            f"{self.base_url}/",
            media_url
        )

        response = requests.get(
            media_url,
            timeout=10
        )

        response.raise_for_status()

        return response.content
