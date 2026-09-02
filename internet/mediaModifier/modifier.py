
from pathlib import Path
import hashlib
import uuid
import json

from image_modifier import (
    resize_image,
    compress_jpeg,
    crop_image,
    convert_format
)


# --------------------------------------------------
# DIRECTORIES
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
MANIFEST_DIR = BASE_DIR / "manifests"
SCENARIO_DIR = BASE_DIR / "scenarios"
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}

# Create directories if they don't exist

INPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
SCENARIO_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# DEFAULT INPUT
# --------------------------------------------------

def get_default_input_file():
    """
    Select the CLI input image.

    Prefer the documented test.jpg filename, then fall back to an image
    already present in the input directory.
    """

    default_file = INPUT_DIR / "test.jpg"

    if default_file.is_file():
        return default_file

    image_files = sorted(
        file for file in INPUT_DIR.iterdir()
        if file.is_file() and file.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
    )

    if len(image_files) == 1:
        return image_files[0]

    if not image_files:
        raise FileNotFoundError(
            f"No input image found in {INPUT_DIR}. "
            "Place an image there, for example input\\test.jpg."
        )

    raise FileNotFoundError(
        f"Multiple input images found in {INPUT_DIR}. "
        "Use input\\test.jpg or call modify_media() with an explicit file."
    )


# --------------------------------------------------
# SHA-256 HASH
# --------------------------------------------------

def calculate_hash(file_path):
    """
    Calculate SHA-256 hash of a file.
    """

    sha256 = hashlib.sha256()

    with open(file_path, "rb") as file:

        while chunk := file.read(8192):
            sha256.update(chunk)

    return sha256.hexdigest()


# --------------------------------------------------
# LOAD SCENARIO
# --------------------------------------------------

def load_scenario(scenario_file):
    """
    Load a modification scenario from a JSON file.
    """

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


# --------------------------------------------------
# SAVE MANIFEST
# --------------------------------------------------

def save_manifest(manifest, media_id):
    """
    Save modification history as a JSON manifest.
    """

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


# --------------------------------------------------
# MODIFY MEDIA
# --------------------------------------------------

def modify_media(input_file, operations):
    """
    Apply a sequence of modifications to an image.

    Returns information about the complete
    transformation chain.
    """

    input_path = Path(input_file)

    if not input_path.is_file():
        raise FileNotFoundError(
            f"File not found: {input_path}"
        )

    # --------------------------------------------------
    # Generate unique media ID
    # --------------------------------------------------

    media_id = str(uuid.uuid4())

    # --------------------------------------------------
    # Original hash
    # --------------------------------------------------

    original_hash = calculate_hash(input_path)

    current_file = input_path

    operation_history = []

    # --------------------------------------------------
    # Apply operations sequentially
    # --------------------------------------------------

    for index, operation in enumerate(operations, start=1):

        operation_type = operation["type"]

        operation_id = str(uuid.uuid4())

        # ----------------------------------------------
        # RESIZE
        # ----------------------------------------------

        if operation_type == "resize":

            output_file = (
                OUTPUT_DIR /
                f"{media_id}_step{index}.jpg"
            )

            result = resize_image(
                current_file,
                output_file,
                operation["width"]
            )

        # ----------------------------------------------
        # JPEG COMPRESSION
        # ----------------------------------------------

        elif operation_type == "compress":

            output_file = (
                OUTPUT_DIR /
                f"{media_id}_step{index}.jpg"
            )

            result = compress_jpeg(
                current_file,
                output_file,
                operation.get("quality", 70)
            )

        # ----------------------------------------------
        # CROP
        # ----------------------------------------------

        elif operation_type == "crop":

            output_file = (
                OUTPUT_DIR /
                f"{media_id}_step{index}.jpg"
            )

            result = crop_image(
                current_file,
                output_file,
                operation["left"],
                operation["top"],
                operation["right"],
                operation["bottom"]
            )

        # ----------------------------------------------
        # FORMAT CONVERSION
        # ----------------------------------------------

        elif operation_type == "convert":

            extension = operation["format"].lower()

            output_file = (
                OUTPUT_DIR /
                f"{media_id}_step{index}.{extension}"
            )

            result = convert_format(
                current_file,
                output_file,
                operation["format"]
            )

        # ----------------------------------------------
        # UNKNOWN OPERATION
        # ----------------------------------------------

        else:

            raise ValueError(
                f"Unknown operation: {operation_type}"
            )

        # ----------------------------------------------
        # Hash after operation
        # ----------------------------------------------

        step_hash = calculate_hash(output_file)

        # Add operation information

        operation_record = {
            "step": index,
            "operation_id": operation_id,
            "type": operation_type,
            "parameters": operation,
            "output_file": str(output_file),
            "sha256": step_hash,
            "details": result
        }

        operation_history.append(
            operation_record
        )

        # Next operation receives this file

        current_file = output_file

    # --------------------------------------------------
    # Final hash
    # --------------------------------------------------

    final_hash = calculate_hash(current_file)

    # --------------------------------------------------
    # Create manifest
    # --------------------------------------------------

    manifest = {

        "media_id": media_id,

        "original": {
            "file": str(input_path),
            "sha256": original_hash
        },

        "final": {
            "file": str(current_file),
            "sha256": final_hash
        },

        "operations": operation_history
    }

    # --------------------------------------------------
    # Save manifest
    # --------------------------------------------------

    manifest_path = save_manifest(
        manifest,
        media_id
    )

    manifest["manifest_file"] = str(
        manifest_path
    )

    return manifest


# --------------------------------------------------
# MAIN PROGRAM
# --------------------------------------------------

if __name__ == "__main__":

    # ----------------------------------------------
    # Select scenario
    # ----------------------------------------------

    scenario_file = (
        SCENARIO_DIR /
        "social_media.json"
    )

    scenario = load_scenario(
        scenario_file
    )

    print("\n===================================")
    print("       MEDIA MODIFIER")
    print("===================================")

    print(
        f"\nScenario: {scenario['name']}"
    )

    # ----------------------------------------------
    # Input media
    # ----------------------------------------------

    input_file = get_default_input_file()

    # ----------------------------------------------
    # Modify media
    # ----------------------------------------------

    result = modify_media(
        input_file,
        scenario["operations"]
    )

    # ----------------------------------------------
    # Display result
    # ----------------------------------------------

    print("\n-----------------------------------")
    print("MEDIA ID")
    print("-----------------------------------")

    print(result["media_id"])

    print("\n-----------------------------------")
    print("ORIGINAL")
    print("-----------------------------------")

    print(
        "File:",
        result["original"]["file"]
    )

    print(
        "SHA-256:",
        result["original"]["sha256"]
    )

    print("\n-----------------------------------")
    print("OPERATIONS")
    print("-----------------------------------")

    for operation in result["operations"]:

        print(
            f"\nStep {operation['step']}"
        )

        print(
            "Type:",
            operation["type"]
        )

        print(
            "Parameters:",
            operation["parameters"]
        )

        print(
            "Output:",
            operation["output_file"]
        )

        print(
            "SHA-256:",
            operation["sha256"]
        )

    print("\n-----------------------------------")
    print("FINAL")
    print("-----------------------------------")

    print(
        "File:",
        result["final"]["file"]
    )

    print(
        "SHA-256:",
        result["final"]["sha256"]
    )

    print("\n-----------------------------------")
    print("MANIFEST")
    print("-----------------------------------")

    print(
        result["manifest_file"]
    )

    print("\n===================================")
    print("       MODIFICATION COMPLETE")
    print("===================================\n")
