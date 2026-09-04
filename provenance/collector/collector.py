
from pathlib import Path
from datetime import datetime
import uuid
import json

from platform_source import PlatformSource
from artifact_store import ArtifactStore


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

OUTPUT_DIR = BASE_DIR / "outputs"


# ============================================================
# PLATFORM SOURCES
# ============================================================

PLATFORMS = {
    "InstaMock": PlatformSource(
        "InstaMock",
        "http://127.0.0.1:8000"
    ),

    "XMock": PlatformSource(
        "XMock",
        "http://127.0.0.1:8001"
    ),

    "FaceMock": PlatformSource(
        "FaceMock",
        "http://127.0.0.1:8002"
    )
}


# ============================================================
# COLLECTOR
# ============================================================

class ProvenanceCollector:

    def __init__(self):

        self.store = ArtifactStore(
            OUTPUT_DIR
        )

    def collect_platform(
        self,
        platform_name,
        source,
        investigation_dir
    ):

        print()
        print("-" * 60)
        print(f"Collecting from {platform_name}")
        print("-" * 60)

        # ----------------------------------------------------
        # PLATFORM DIRECTORY
        # ----------------------------------------------------

        platform_dir = (
            self.store.create_platform_directory(
                investigation_dir,
                platform_name
            )
        )

        media_dir = platform_dir / "media"

        # ----------------------------------------------------
        # GET POSTS
        # ----------------------------------------------------

        posts = source.get_posts()

        print(
            f"Posts discovered: {len(posts)}"
        )

        # ----------------------------------------------------
        # SAVE RAW POSTS
        # ----------------------------------------------------

        posts_file = self.store.save_posts(
            platform_dir,
            posts
        )

        print(
            f"Posts saved: {posts_file}"
        )

        # ----------------------------------------------------
        # COLLECT MEDIA
        # ----------------------------------------------------

        collected_media = []

        for post in posts:

            media_url = post.get("media_url")

            if not media_url:
                continue

            try:

                content = source.download_media(
                    media_url
                )

                filename = Path(
                    media_url.split("?")[0]
                ).name

                if not filename:
                    filename = (
                        f"post_{post['id']}.bin"
                    )

                # Prevent filename collisions
                filename = (
                    f"post_{post['id']}_"
                    f"{filename}"
                )

                media_file = self.store.save_media(
                    media_dir,
                    filename,
                    content
                )

                media_hash = (
                    self.store.calculate_hash(
                        media_file
                    )
                )

                media_record = {
                    "post_id": post["id"],
                    "media_url": media_url,
                    "local_file": str(media_file),
                    "sha256": media_hash,
                    "size_bytes": len(content)
                }

                collected_media.append(
                    media_record
                )

                print(
                    f"  Post {post['id']} "
                    f"-> {filename}"
                )

            except Exception as error:

                print(
                    f"  Failed to collect media "
                    f"from post {post.get('id')}: "
                    f"{error}"
                )

        # ----------------------------------------------------
        # SAVE MEDIA INDEX
        # ----------------------------------------------------

        media_index = (
            platform_dir /
            "media_index.json"
        )

        with open(
            media_index,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                collected_media,
                file,
                indent=4
            )

        print(
            f"Media collected: "
            f"{len(collected_media)}"
        )

        return {
            "platform": platform_name,
            "posts_count": len(posts),
            "media_count": len(collected_media),
            "posts_file": str(posts_file),
            "media_index": str(media_index)
        }

    def run(self):

        print()
        print("=" * 60)
        print("              TRUTH TRACE COLLECTOR")
        print("=" * 60)

        # ----------------------------------------------------
        # INVESTIGATION ID
        # ----------------------------------------------------

        investigation_id = (
            f"investigation_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_"
            f"{uuid.uuid4().hex[:8]}"
        )

        investigation_dir = (
            self.store.create_investigation(
                investigation_id
            )
        )

        print(
            f"\nInvestigation ID: "
            f"{investigation_id}"
        )

        print(
            f"Output directory: "
            f"{investigation_dir}"
        )

        # ----------------------------------------------------
        # COLLECT ALL PLATFORMS
        # ----------------------------------------------------

        results = []

        for platform_name, source in PLATFORMS.items():

            try:

                result = self.collect_platform(
                    platform_name,
                    source,
                    investigation_dir
                )

                results.append(result)

            except Exception as error:

                print()
                print(
                    f"ERROR collecting "
                    f"{platform_name}: {error}"
                )

                results.append({
                    "platform": platform_name,
                    "error": str(error)
                })

        # ----------------------------------------------------
        # INVESTIGATION MANIFEST
        # ----------------------------------------------------

        manifest = {
            "investigation_id": investigation_id,

            "created_at":
                datetime.now().isoformat(),

            "collector": {
                "name": "Truth Trace Collector",
                "version": "1.0"
            },

            "platforms": results
        }

        manifest_file = (
            investigation_dir /
            "investigation.json"
        )

        with open(
            manifest_file,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                manifest,
                file,
                indent=4
            )

        # ----------------------------------------------------
        # COMPLETE
        # ----------------------------------------------------

        print()
        print("=" * 60)
        print("              COLLECTION COMPLETE")
        print("=" * 60)

        print(
            f"\nInvestigation manifest:"
        )

        print(manifest_file)

        print()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    collector = ProvenanceCollector()

    collector.run()
