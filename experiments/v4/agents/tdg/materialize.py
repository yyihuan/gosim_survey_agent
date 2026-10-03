#!/usr/bin/env python3
"""Create a self-contained agent copy from the shared TDG source and exact config."""
import argparse
import json
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    for key in ("strict_slot", "science_exponent", "geometry_strength"):
        if key not in config:
            raise SystemExit("missing config key: " + key)
    # Never silently overwrite a frozen materialization or prior run.
    args.out.mkdir(parents=True, exist_ok=False)
    source = Path(__file__).parent / "source"
    for path in sorted(source.iterdir()):
        if path.is_file() and (path.suffix == ".py" or path.name == "observer.project.json"):
            shutil.copy2(path, args.out / path.name)
    shutil.copy2(args.config, args.out / "strategy_config.json")
    print(json.dumps({"config": str(args.config.resolve()), "agent_dir": str(args.out.resolve())}))


if __name__ == "__main__":
    main()
