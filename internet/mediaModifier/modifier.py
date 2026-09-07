from pathlib import Path
import hashlib
import uuid
import json
import argparse

from image_modifier import (
    resize_image,
    compress_jpeg,
    crop_image,
    convert_format
)
from video_modifier import (
    compress_video,
    convert_video,
    crop_video,
    resize_video,
)


BASE_DIR = Path(__file__).resolve().parent

INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
MANIFEST_DIR = BASE_DIR / "manifests"
SCENARIO_DIR = BASE_DIR / "scenarios"

INPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
SCENARIO_DIR.mkdir(parents=True, exist_ok=True)


def calculate_hash(file_path):

    sha256 = hashlib.sha256()

    with open(file_path, "rb") as file:

        while chunk := file.read(8192):
            sha256.update(chunk)

    return sha256.hexdigest()


def load_scenario(scenario_file):

    scenario_path = Path(scenario_file)

    if not scenario_path.exists():
        raise FileNotFoundError(
            f"Scenario not found: {scenario_path}"
        )

    with open(scenario_path, "r") as file:
        scenario = json.load(file)

    if "operations" not in scenario:
        raise ValueError(
            "Scenario must contain an 'operations' field."
        )

    return scenario


def save_manifest(manifest, media_id):

    manifest_path = (
        MANIFEST_DIR /
        f"{media_id}.json"
    )

    with open(manifest_path, "w") as file:

        json.dump(
            manifest,
            file,
            indent=4
        )

    return manifest_path


def transform_media(input_file, operations):

    """
    Transform an input media file using the supplied
    operation sequence.

    Returns information required by the propagation simulator.
    """

    input_path = Path(input_file)

    if not input_path.exists():

        raise FileNotFoundError(
            f"File not found: {input_path}"
        )

    transformation_id = str(
        uuid.uuid4()
    )

    input_hash = calculate_hash(
        input_path
    )

    current_file = input_path
    is_video = input_path.suffix.lower() in {
        ".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"
    }

    operation_history = []

    for index, operation in enumerate(
        operations,
        start=1
    ):

        operation_type = operation["type"]

        operation_id = str(
            uuid.uuid4()
        )

        # -----------------------------
        # RESIZE
        # -----------------------------

        if operation_type == "resize":

            output_file = (
                OUTPUT_DIR /
                f"{transformation_id}_step{index}"
                f"{'.mp4' if is_video else '.jpg'}"
            )

            if is_video:
                result = resize_video(current_file, output_file, operation["width"])
            else:
                result = resize_image(current_file, output_file, operation["width"])

        # -----------------------------
        # COMPRESSION
        # -----------------------------

        elif operation_type == "compress":

            output_file = (
                OUTPUT_DIR /
                f"{transformation_id}_step{index}"
                f"{'.mp4' if is_video else '.jpg'}"
            )

            if is_video:
                result = compress_video(
                    current_file,
                    output_file,
                    operation.get("quality", 70),
                )
            else:
                result = compress_jpeg(
                    current_file,
                    output_file,
                    operation.get("quality", 70),
                )

        # -----------------------------
        # CROP
        # -----------------------------

        elif operation_type == "crop":

            output_file = (
                OUTPUT_DIR /
                f"{transformation_id}_step{index}"
                f"{'.mp4' if is_video else '.jpg'}"
            )

            if is_video:
                result = crop_video(
                    current_file,
                    output_file,
                    operation["left"],
                    operation["top"],
                    operation["right"],
                    operation["bottom"],
                )
            else:
                result = crop_image(
                    current_file,
                    output_file,
                    operation["left"],
                    operation["top"],
                    operation["right"],
                    operation["bottom"],
                )

        # -----------------------------
        # FORMAT CONVERSION
        # -----------------------------

        elif operation_type == "convert":

            requested_format = operation["format"].lower()
            extension = (
                "mp4"
                if is_video and requested_format in {"jpg", "jpeg", "png", "webp"}
                else requested_format
            )

            output_file = OUTPUT_DIR / f"{transformation_id}_step{index}.{extension}"

            if is_video:
                result = convert_video(current_file, output_file, extension)
            else:
                result = convert_format(current_file, output_file, operation["format"])

        else:

            raise ValueError(
                f"Unknown operation: {operation_type}"
            )

        output_hash = calculate_hash(
            output_file
        )

        operation_record = {

            "step": index,

            "operation_id":
                operation_id,

            "type":
                operation_type,

            "parameters":
                operation,

            "input_file":
                str(current_file),

            "output_file":
                str(output_file),

            "input_sha256":
                calculate_hash(current_file),

            "output_sha256":
                output_hash,

            "details":
                result
        }

        operation_history.append(
            operation_record
        )

        current_file = output_file
        is_video = current_file.suffix.lower() in {
            ".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"
        }

    final_hash = calculate_hash(
        current_file
    )

    manifest = {

        "transformation_id":
            transformation_id,

        "input": {

            "file":
                str(input_path),

            "sha256":
                input_hash
        },

        "final": {

            "file":
                str(current_file),

            "sha256":
                final_hash
        },

        "operations":
            operation_history
    }

    manifest_path = save_manifest(
        manifest,
        transformation_id
    )

    return {

        "transformation_id":
            transformation_id,

        "input_file":
            str(input_path),

        "input_hash":
            input_hash,

        "output_file":
            str(current_file),

        "output_hash":
            final_hash,

        "operations":
            operation_history,

        "manifest_file":
            str(manifest_path)
    }


def modify_media(
    input_file,
    operations
):

    """
    Backwards-compatible wrapper.
    """

    return transform_media(
        input_file,
        operations
    )


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Transform an image or video using the configured media scenario."
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        type=Path,
        help="Path to the input image or video (defaults to the first supported file in input/).",
    )
    args = parser.parse_args()

    scenario_file = (
        SCENARIO_DIR /
        "social_media.json"
    )

    scenario = load_scenario(
        scenario_file
    )

    input_file = args.input_file

    if input_file is None:
        supported_extensions = {
            ".jpg", ".jpeg", ".jpe", ".png", ".webp",
            ".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv",
        }
        input_files = sorted(
            file_path
            for file_path in INPUT_DIR.iterdir()
            if file_path.is_file()
            and file_path.suffix.lower() in supported_extensions
        )

        if not input_files:
            raise FileNotFoundError(
                f"No supported media found in {INPUT_DIR}. "
                "Pass an input image or video path as an argument."
            )

        input_file = input_files[0]

    operations = scenario.get("operations", [])
    if input_file.suffix.lower() in {
        ".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"
    }:
        operations = scenario.get("video_operations", operations)

    result = transform_media(
        input_file,
        operations
    )

    print()
    print("=" * 50)
    print("       MEDIA MODIFIER")
    print("=" * 50)

    print(
        "\nTransformation ID:",
        result["transformation_id"]
    )

    print(
        "\nInput:",
        result["input_file"]
    )

    print(
        "Input SHA-256:",
        result["input_hash"]
    )

    print("\nOperations:")

    for operation in result["operations"]:

        print(
            f"  Step {operation['step']}: "
            f"{operation['type']}"
        )

    print(
        "\nOutput:",
        result["output_file"]
    )

    print(
        "Output SHA-256:",
        result["output_hash"]
    )

    print(
        "\nManifest:",
        result["manifest_file"]
    )

    print("\n" + "=" * 50)