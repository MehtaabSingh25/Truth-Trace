import json
import random
from pathlib import Path


class ScenarioEngine:

    def __init__(self, scenario_path):

        self.scenario_path = Path(
            scenario_path
        )

        with open(
            self.scenario_path,
            "r"
        ) as file:

            self.scenario = json.load(file)

    # -----------------------------------------
    # SCENARIO
    # -----------------------------------------

    def get_scenario_name(self):

        return self.scenario.get(
            "name",
            "Unnamed Scenario"
        )

    # -----------------------------------------
    # PLATFORM ORDER
    # -----------------------------------------

    def get_platform_sequence(self):

        platforms = self.scenario.get(
            "platforms",
            []
        )

        if not platforms:

            raise ValueError(
                "Scenario contains no platforms."
            )

        sequence = platforms.copy()

        if self.scenario.get(
            "random_platform_order",
            False
        ):

            random.shuffle(sequence)

        return sequence

    # -----------------------------------------
    # RANDOM OPERATIONS
    # -----------------------------------------

    def generate_operations(self, media_type=None, allow_video_transformations=True):

        config = self.scenario.get(
            "random_operations",
            {}
        )

        operations = []
        is_video = bool(media_type and media_type.startswith("video"))

        if is_video and not allow_video_transformations:
            return operations

        # -----------------------------
        # RESIZE
        # -----------------------------

        if config.get(
            "resize",
            False
        ):

            if random.choice(
                [True, False]
            ):

                width = random.choice(
                    config.get(
                        "video_resize_widths" if is_video else "resize_widths",
                        [
                            360,
                            480,
                            720
                        ] if is_video else [
                            720,
                            900,
                            1080,
                            1200
                        ]
                    )
                )

                operations.append({

                    "type":
                        "resize",

                    "width":
                        width
                })

        # -----------------------------
        # CROP
        # -----------------------------

        if config.get("crop", False) and (
            not is_video or config.get("video_crop", False)
        ):

            if random.choice(
                [True, False]
            ):

                crop_size = random.choice(
                    config.get(
                        "crop_sizes",
                        [
                            600,
                            720,
                            800,
                            900
                        ]
                    )
                )

                operations.append({

                    "type":
                        "crop",

                    "left":
                        0,

                    "top":
                        0,

                    "right":
                        crop_size,

                    "bottom":
                        crop_size
                })

        # -----------------------------
        # COMPRESSION
        # -----------------------------

        if config.get(
            "compression",
            False
        ):

            if random.choice(
                [True, False]
            ):

                minimum = config.get(
                    "min_quality",
                    50
                )

                maximum = config.get(
                    "max_quality",
                    90
                )

                quality = random.randint(
                    minimum,
                    maximum
                )

                operations.append({

                    "type":
                        "compress",

                    "quality":
                        quality
                })

        # -----------------------------
        # FORMAT CONVERSION
        # -----------------------------

        if config.get(
            "format_conversion",
            False
        ):

            if random.choice(
                [True, False]
            ):

                formats = config.get(
                    "video_formats" if is_video else "formats",
                    ["mp4", "webm", "mov"] if is_video else ["jpg", "png", "webp"],
                )

                selected_format = random.choice(
                    formats
                )

                operations.append({

                    "type":
                        "convert",

                    "format":
                        selected_format
                })

        return operations

    # -----------------------------------------
    # DELAY
    # -----------------------------------------

    def get_delay(self):

        config = self.scenario.get(
            "delays",
            {}
        )

        if not config.get(
            "enabled",
            False
        ):

            return 0

        minimum = config.get(
            "min_seconds",
            1
        )

        maximum = config.get(
            "max_seconds",
            5
        )

        return random.uniform(
            minimum,
            maximum
        )

    # -----------------------------------------
    # DUPLICATE UPLOAD
    # -----------------------------------------

    def should_duplicate(self):

        config = self.scenario.get(
            "duplicates",
            {}
        )

        if not config.get(
            "enabled",
            False
        ):

            return False

        probability = config.get(
            "probability",
            0.2
        )

        return (
            random.random()
            < probability
        )

    # -----------------------------------------
    # USER COUNT
    # -----------------------------------------

    def get_user_count(self):

        return self.scenario.get(
            "users_per_platform",
            1
        )