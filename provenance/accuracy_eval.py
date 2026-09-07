import argparse
import json
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "media_dna"))
from image_ai_assessment import assess_image_ai_likelihood


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate image AI labels from a JSON fixture manifest."
    )
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    cases = json.loads(args.manifest.read_text(encoding="utf-8"))
    results = []
    for case in cases:
        result = assess_image_ai_likelihood(case["file"])
        predicted = result["label"]
        expected = case["expected_label"]
        results.append({
            "file": str(case["file"]),
            "expected": expected,
            "predicted": predicted,
            "correct": predicted == expected,
            "confidence": result["confidence"],
        })
    correct = sum(item["correct"] for item in results)
    print(json.dumps({
        "cases": len(results),
        "correct": correct,
        "accuracy": round(correct / len(results), 6) if results else 0.0,
        "results": results,
    }, indent=2))


if __name__ == "__main__":
    main()
