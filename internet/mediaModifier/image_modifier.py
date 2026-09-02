from PIL import Image
from pathlib import Path


def resize_image(input_path, output_path, width):
    """
    Resize image while maintaining aspect ratio.
    """

    image = Image.open(input_path)

    original_width, original_height = image.size

    ratio = width / original_width
    height = int(original_height * ratio)

    resized = image.resize(
        (width, height),
        Image.Resampling.LANCZOS
    )

    resized.save(output_path)

    return {
        "operation": "resize",
        "original_size": (
            original_width,
            original_height
        ),
        "new_size": (
            width,
            height
        )
    }


def compress_jpeg(input_path, output_path, quality=70):
    """
    Re-encode image as JPEG with specified quality.
    """

    image = Image.open(input_path)

    # JPEG doesn't support RGBA
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")

    image.save(
        output_path,
        "JPEG",
        quality=quality
    )

    return {
        "operation": "jpeg_compression",
        "quality": quality
    }


def crop_image(input_path, output_path, left, top, right, bottom):
    """
    Crop image using pixel coordinates.
    """

    image = Image.open(input_path)

    cropped = image.crop(
        (left, top, right, bottom)
    )

    cropped.save(output_path)

    return {
        "operation": "crop",
        "crop_box": (
            left,
            top,
            right,
            bottom
        )
    }


def convert_format(input_path, output_path, format):
    """
    Convert image into another format.
    """

    image = Image.open(input_path)

    if format.upper() == "JPEG":
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")

    image.save(
        output_path,
        format.upper()
    )

    return {
        "operation": "format_conversion",
        "format": format.upper()
    }