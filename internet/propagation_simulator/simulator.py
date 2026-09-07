
from pathlib import Path
import hashlib
import time
import uuid
import random
import argparse

from platform_client import PlatformClient
from scenario_engine import ScenarioEngine
from manifest_tracker import ManifestTracker

# Import Media Modifier
import sys

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent

MEDIA_MODIFIER = PROJECT_ROOT / "internet" / "mediaModifier"

# Allow Python to import modifier.py
sys.path.append(str(MEDIA_MODIFIER))

from modifier import transform_media
from video_modifier import ffmpeg_available


# ============================================================
# DIRECTORIES
# ============================================================

INPUT_DIR = MEDIA_MODIFIER / "input"

SCENARIO_DIR = BASE_DIR / "scenarios"
LOG_DIR = BASE_DIR / "logs"
PROPAGATION_OUTPUT_DIR = BASE_DIR / "outputs"

LOG_DIR.mkdir(parents=True, exist_ok=True)
PROPAGATION_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# PLATFORM CONFIGURATION
# ============================================================

PLATFORMS = {
    "InstaMock": PlatformClient(
        "InstaMock",
        "http://127.0.0.1:8000"
    ),

    "XMock": PlatformClient(
        "XMock",
        "http://127.0.0.1:8001"
    ),

    "FaceMock": PlatformClient(
        "FaceMock",
        "http://127.0.0.1:8002"
    )
}


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def calculate_hash(file_path):
    sha256 = hashlib.sha256()

    with open(file_path, "rb") as file:
        while chunk := file.read(8192):
            sha256.update(chunk)

    return sha256.hexdigest()


def generate_username(platform_name):
    """
    Generate a unique dummy username.

    UUID prevents collisions when the simulator
    is executed multiple times.
    """

    suffix = uuid.uuid4().hex[:8]

    return f"dummy_{platform_name.lower()}_{suffix}"


def choose_user(users):
    """
    Randomly select one user from the platform's
    dummy-user pool.
    """

    return random.choice(users)


# ============================================================
# MEDIA TRANSFORMATION
# ============================================================

def transform_current_media(current_file, operations):
    """
    Run the Media Modifier.

    If there are no operations, return the current
    file unchanged.
    """

    if not operations:
        return {
            "transformation_id": None,
            "input_file": str(current_file),
            "input_hash": calculate_hash(current_file),
            "output_file": str(current_file),
            "output_hash": calculate_hash(current_file),
            "operations": [],
            "manifest_file": None
        }

    result = transform_media(
        input_file=current_file,
        operations=operations
    )

    return result


# ============================================================
# MAIN SIMULATION
# ============================================================

def run(media_path=None, caption="DummyUser propagation test"):

    print()
    print("=" * 60)
    print("              DUMMY USER / PROPAGATION SIMULATOR")
    print("=" * 60)

    # --------------------------------------------------------
    # LOAD SCENARIO
    # --------------------------------------------------------

    scenario_path = SCENARIO_DIR / "demo_scenario.json"

    engine = ScenarioEngine(scenario_path)

    scenario_name = engine.get_scenario_name()

    print(f"\nScenario: {scenario_name}")

    # --------------------------------------------------------
    # FIND ORIGINAL MEDIA
    # --------------------------------------------------------

    supported_extensions = {
        ".jpg", ".jpeg", ".jpe", ".png", ".webp",
        ".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv",
    }

    if media_path:
        original_file = Path(media_path).expanduser().resolve()
        if not original_file.is_file():
            raise FileNotFoundError(f"Media file not found: {original_file}")
    else:
        input_files = sorted(
            file for file in INPUT_DIR.iterdir()
            if file.is_file()
            and file.suffix.lower() in supported_extensions
        )

        if not input_files:
            raise FileNotFoundError(
                f"No supported media found in {INPUT_DIR}"
            )

        video_files = [
            file for file in input_files
            if file.suffix.lower() in {
                ".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"
            }
        ]
        original_file = video_files[0] if video_files else input_files[0]

    original_hash = calculate_hash(original_file)

    media_id = str(uuid.uuid4())

    print(f"Original media: {original_file.name}")
    print(f"Original SHA-256: {original_hash}")
    print(f"Media ID: {media_id}")

    # --------------------------------------------------------
    # PLATFORM ORDER
    # --------------------------------------------------------

    platform_order = engine.get_platform_sequence()

    print("\nPlatform propagation order:")

    for index, platform in enumerate(platform_order, start=1):
        print(f"  {index}. {platform}")

    # --------------------------------------------------------
    # CREATE MANIFEST TRACKER
    # --------------------------------------------------------

    tracker = ManifestTracker(
        PROPAGATION_OUTPUT_DIR
    )

    record = tracker.create_record(
        media_id=media_id,
        original_file=original_file,
        original_hash=original_hash,
        scenario_name=scenario_name,
        platform_order=platform_order
    )

    # --------------------------------------------------------
    # CREATE USERS
    # --------------------------------------------------------

    users = {}

    user_count = engine.get_user_count()

    print()
    print("=" * 60)
    print("CREATING DUMMY USERS")
    print("=" * 60)

    for platform_name in platform_order:

        platform = PLATFORMS[platform_name]

        users[platform_name] = []

        print(f"\n{platform_name}:")

        for _ in range(user_count):

            username = generate_username(
                platform_name
            )

            user = platform.create_user(
                username
            )

            users[platform_name].append(user)

            print(
                f"  Created user "
                f"{user['id']} -> {username}"
            )

        tracker.add_users(
            record,
            platform_name,
            users[platform_name]
        )

    # --------------------------------------------------------
    # PROPAGATION STATE
    # --------------------------------------------------------

    current_file = original_file

    current_hash = original_hash

    previous_event_id = None

    previous_platform = None

    previous_post_id = None

    # --------------------------------------------------------
    # PROPAGATE THROUGH PLATFORMS
    # --------------------------------------------------------

    for platform_index, platform_name in enumerate(
        platform_order,
        start=1
    ):

        platform = PLATFORMS[platform_name]

        print()
        print("=" * 60)
        print(
            f"PROPAGATION {platform_index}/"
            f"{len(platform_order)}"
        )
        print("=" * 60)

        print(f"Platform: {platform_name}")

        print(
            f"Input media: "
            f"{Path(current_file).name}"
        )

        # ----------------------------------------------------
        # GENERATE RANDOM OPERATIONS
        # ----------------------------------------------------

        media_type = (
            "video/" + current_file.suffix.lower().lstrip(".")
            if current_file.suffix.lower() in {
                ".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"
            }
            else "image/" + current_file.suffix.lower().lstrip(".")
        )
        operations = engine.generate_operations(
            media_type=media_type,
            allow_video_transformations=ffmpeg_available(),
        )

        print("\nOperations:")

        if operations:
            for index, operation in enumerate(
                operations,
                start=1
            ):
                print(
                    f"  {index}. "
                    f"{operation['type']} "
                    f"{operation}"
                )
        else:
            print("  No transformation")

        # ----------------------------------------------------
        # TRANSFORM MEDIA
        # ----------------------------------------------------

        transformation = transform_current_media(
            current_file,
            operations
        )

        transformed_file = Path(
            transformation["output_file"]
        )

        transformed_hash = (
            transformation["output_hash"]
        )

        transformation_id = (
            transformation["transformation_id"]
        )

        if transformation_id:

            print(
                f"\nTransformation ID: "
                f"{transformation_id}"
            )

            print(
                f"Transformed media: "
                f"{transformed_file.name}"
            )

            print(
                f"Output SHA-256: "
                f"{transformed_hash}"
            )

        else:

            print(
                "\nMedia unchanged."
            )

        # ----------------------------------------------------
        # DELAY BEFORE UPLOAD
        # ----------------------------------------------------

        delay = engine.get_delay()

        if delay > 0:

            print(
                f"\nWaiting "
                f"{delay:.2f} seconds..."
            )

            time.sleep(delay)

        # ----------------------------------------------------
        # SELECT RANDOM USER
        # ----------------------------------------------------

        user = choose_user(
            users[platform_name]
        )

        user_id = user["id"]

        print(
            f"\nUploading as user "
            f"{user['username']} "
            f"(ID {user_id})"
        )

        # ----------------------------------------------------
        # UPLOAD
        # ----------------------------------------------------

        post = platform.create_post(
            user_id=user_id,
            text=caption,
            media_path=transformed_file
        )

        post_id = post["id"]

        print(
            f"Post created: {post_id}"
        )

        # ----------------------------------------------------
        # RECORD UPLOAD EVENT
        # ----------------------------------------------------

        event_id = tracker.add_event(
            record=record,

            event_type="upload",

            platform=platform_name,

            user_id=user_id,

            post_id=post_id,

            input_file=current_file,

            input_hash=current_hash,

            output_file=transformed_file,

            output_hash=transformed_hash,

            transformation_id=transformation_id,

            operations=operations,

            parent_event_id=previous_event_id,

            source_platform=previous_platform,

            source_post_id=previous_post_id,

            delay_from_previous_event=delay
        )

        # ----------------------------------------------------
        # DUPLICATE UPLOAD
        # ----------------------------------------------------

        if engine.should_duplicate():

            print()
            print("DUPLICATE UPLOAD TRIGGERED")

            duplicate_user = choose_user(
                users[platform_name]
            )

            duplicate_post = platform.create_post(
                user_id=duplicate_user["id"],
                text=f"{caption} (duplicate)",
                media_path=transformed_file
            )

            duplicate_post_id = duplicate_post["id"]

            print(
                f"Duplicate post created: "
                f"{duplicate_post_id}"
            )

            duplicate_event_id = tracker.add_event(
                record=record,

                event_type="duplicate_upload",

                platform=platform_name,

                user_id=duplicate_user["id"],

                post_id=duplicate_post_id,

                input_file=transformed_file,

                input_hash=transformed_hash,

                output_file=transformed_file,

                output_hash=transformed_hash,

                transformation_id=None,

                operations=[],

                parent_event_id=event_id,

                source_platform=platform_name,

                source_post_id=post_id,

                delay_from_previous_event=0.0
            )

            # The duplicate becomes the latest event
            # in the propagation chain.
            previous_event_id = duplicate_event_id

            previous_platform = platform_name

            previous_post_id = duplicate_post_id

        else:

            previous_event_id = event_id

            previous_platform = platform_name

            previous_post_id = post_id

        # ----------------------------------------------------
        # CURRENT MEDIA BECOMES SOURCE FOR NEXT PLATFORM
        # ----------------------------------------------------

        current_file = transformed_file

        current_hash = transformed_hash

    # --------------------------------------------------------
    # SAVE GROUND TRUTH
    # --------------------------------------------------------

    manifest_path = tracker.save(record)

    # --------------------------------------------------------
    # COMPLETE
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("              PROPAGATION COMPLETE")
    print("=" * 60)

    print(
        f"\nTotal events: "
        f"{len(record['events'])}"
    )

    print(
        "\nGround-truth propagation manifest:"
    )

    print(manifest_path)

    print()
    print("=" * 60)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Propagate image or video media through all mock platforms."
    )
    parser.add_argument(
        "--media",
        type=Path,
        help="Image/video path. Defaults to a video, then the first supported file in mediaModifier/input.",
    )
    args = parser.parse_args()
    run(args.media)
