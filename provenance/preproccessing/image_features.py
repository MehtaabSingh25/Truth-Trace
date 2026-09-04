
from pathlib import Path
from PIL import Image
import hashlib


# ============================================================
# HASH
# ============================================================

def calculate_sha256(file_path):
    sha256 = hashlib.sha256()

    with open(file_path, "rb") as file:

        while chunk := file.read(8192):
            sha256.update(chunk)

    return sha256.hexdigest()


# ============================================================
# BASIC FILE INFORMATION
# ============================================================

def get_file_info(file_path):

    path = Path(file_path)

    return {
        "filename": path.name,
        "extension": path.suffix.lower(),
        "size_bytes": path.stat().st_size,
        "sha256": calculate_sha256(path)
    }


# ============================================================
# IMAGE INFORMATION
# ============================================================

def get_image_info(file_path):

    with Image.open(file_path) as image:

        width, height = image.size

        aspect_ratio = (
            round(width / height, 6)
            if height
            else None
        )

        return {
            "format": image.format,
            "mode": image.mode,
            "width": width,
            "height": height,
            "aspect_ratio": aspect_ratio,
            "has_transparency": (
                "transparency" in image.info
                or image.mode in ("RGBA", "LA")
            )
        }


# ============================================================
# EXIF
# ============================================================

def get_exif_data(file_path):

    try:

        with Image.open(file_path) as image:

            exif = image.getexif()

            if not exif:
                return {}

            exif_data = {}

            for key, value in exif.items():

                try:
                    exif_data[str(key)] = str(value)

                except Exception:
                    exif_data[str(key)] = "<unreadable>"

            return exif_data

    except Exception:

        return {}


# ============================================================
# COMPLETE IMAGE ANALYSIS
# ============================================================

def analyze_image(file_path):

    path = Path(file_path)

    result = {
        "file": str(path),
        "file_info": {},
        "image_info": {},
        "exif": {}
    }

    # --------------------------------------------------------
    # FILE INFORMATION
    # --------------------------------------------------------

    result["file_info"] = get_file_info(path)

    # --------------------------------------------------------
    # IMAGE INFORMATION
    # --------------------------------------------------------

    try:

        result["image_info"] = get_image_info(path)

    except Exception as error:

        result["image_info"] = {
            "error": str(error)
        }

    # --------------------------------------------------------
    # EXIF
    # --------------------------------------------------------

    result["exif"] = get_exif_data(path)

    return result

