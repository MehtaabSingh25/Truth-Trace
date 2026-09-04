
import json
from pathlib import Path
from datetime import datetime


class ManifestTracker:

    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def create_record(
        self,
        media_id,
        original_file,
        original_hash,
        scenario_name,
        platform_order
    ):
        return {
            "media_id": media_id,

            "original": {
                "file": str(original_file),
                "sha256": original_hash
            },

            "scenario": {
                "name": scenario_name,
                "platform_order": platform_order
            },

            "users": {},

            "events": [],

            "created_at": datetime.now().isoformat()
        }

    def add_users(self, record, platform, users):
        record["users"][platform] = [
            {
                "id": user["id"],
                "username": user.get("username")
            }
            for user in users
        ]

    def add_event(
        self,
        record,
        event_type,
        platform,
        user_id,
        post_id,
        input_file,
        input_hash,
        output_file,
        output_hash,
        transformation_id=None,
        operations=None,
        parent_event_id=None,
        source_platform=None,
        source_post_id=None,
        delay_from_previous_event=0.0
    ):
        event_id = f"event_{len(record['events']) + 1}"

        event = {
            "event_id": event_id,
            "event_type": event_type,

            "platform": platform,

            "user_id": user_id,
            "post_id": post_id,

            "parent_event_id": parent_event_id,

            "source": {
                "platform": source_platform,
                "post_id": source_post_id
            },

            "input": {
                "file": str(input_file),
                "sha256": input_hash
            },

            "output": {
                "file": str(output_file),
                "sha256": output_hash
            },

            "transformation_id": transformation_id,

            "operations": operations or [],

            "delay_from_previous_event": delay_from_previous_event,

            "timestamp": datetime.now().isoformat()
        }

        record["events"].append(event)

        return event_id

    def save(self, record):
        media_id = record["media_id"]

        output_file = (
            self.output_dir /
            f"{media_id}_propagation.json"
        )

        with open(output_file, "w") as file:
            json.dump(record, file, indent=4)

        return output_file

