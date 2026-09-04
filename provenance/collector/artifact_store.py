
from pathlib import Path
import json
import hashlib


class ArtifactStore:

    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(
            parents=True,
            exist_ok=True
        )

    def create_investigation(self, investigation_id):
        investigation_dir = (
            self.output_dir /
            investigation_id
        )

        investigation_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        return investigation_dir

    def create_platform_directory(
        self,
        investigation_dir,
        platform_name
    ):
        platform_dir = (
            investigation_dir /
            platform_name
        )

        media_dir = platform_dir / "media"

        media_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        return platform_dir

    def save_posts(
        self,
        platform_dir,
        posts
    ):
        output_file = platform_dir / "posts.json"

        with open(
            output_file,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                posts,
                file,
                indent=4
            )

        return output_file

    def save_media(
        self,
        media_dir,
        filename,
        content
    ):
        output_file = media_dir / filename

        with open(
            output_file,
            "wb"
        ) as file:

            file.write(content)

        return output_file

    @staticmethod
    def calculate_hash(file_path):

        sha256 = hashlib.sha256()

        with open(
            file_path,
            "rb"
        ) as file:

            while chunk := file.read(8192):
                sha256.update(chunk)

        return sha256.hexdigest()

