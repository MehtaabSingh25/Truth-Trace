import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def run_stage(folder, script):
    subprocess.run(
        [sys.executable, script],
        cwd=ROOT / folder,
        check=True,
    )


def main():
    parser = argparse.ArgumentParser(description="Run the complete provenance pipeline.")
    parser.add_argument("--skip-collector", action="store_true")
    args = parser.parse_args()

    if not args.skip_collector:
        run_stage("collector", "collector.py")
    run_stage("preproccessing", "processor.py")
    run_stage("media_dna", "dna_extractor.py")
    run_stage("similarity", "similarity_engine.py")
    run_stage("lineage", "lineage_engine.py")
    run_stage("reporting", "report_generator.py")


if __name__ == "__main__":
    main()
