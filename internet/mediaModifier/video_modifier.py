import shutil
import subprocess
import os
from pathlib import Path


def _ffmpeg_command():
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        package_root = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        matches = sorted(package_root.glob("Gyan.FFmpeg_*/*/bin/ffmpeg.exe"))
        if matches:
            return str(matches[-1])

    return None


def ffmpeg_available():
    return _ffmpeg_command() is not None


def _run_ffmpeg(input_path, output_path, filters=None, video_bitrate=None):
    if not ffmpeg_available():
        raise RuntimeError(
            "Video transformations require ffmpeg to be installed and available on PATH."
        )

    command = [
        _ffmpeg_command(),
        "-y",
        "-i",
        str(input_path),
        "-map",
        "0",
        "-c:a",
        "copy",
    ]

    if filters:
        command.extend(["-vf", ",".join(filters)])

    if video_bitrate:
        command.extend(["-b:v", video_bitrate])

    command.append(str(output_path))
    subprocess.run(command, check=True, capture_output=True, text=True)


def resize_video(input_path, output_path, width):
    _run_ffmpeg(input_path, output_path, [f"scale={width}:-2"])
    return {"operation": "resize", "width": width}


def crop_video(input_path, output_path, left, top, right, bottom):
    _run_ffmpeg(
        input_path,
        output_path,
        [f"crop={right - left}:{bottom - top}:{left}:{top}"],
    )
    return {
        "operation": "crop",
        "crop_box": (left, top, right, bottom),
    }


def compress_video(input_path, output_path, quality=70):
    crf = max(18, min(35, round(51 - (quality / 100) * 33)))
    if not ffmpeg_available():
        raise RuntimeError(
            "Video transformations require ffmpeg to be installed and available on PATH."
        )

    command = [
        _ffmpeg_command(),
        "-y",
        "-i",
        str(input_path),
        "-map",
        "0",
        "-c:v",
        "libx264",
        "-crf",
        str(crf),
        "-preset",
        "medium",
        "-c:a",
        "aac",
        str(output_path),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    return {"operation": "video_compression", "quality": quality, "crf": crf}


def convert_video(input_path, output_path, format):
    if format.lower() == "mp4":
        compress_video(input_path, output_path, quality=70)
    else:
        _run_ffmpeg(input_path, output_path)
    return {"operation": "format_conversion", "format": format.lower()}
