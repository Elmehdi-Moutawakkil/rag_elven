"""Export runtime Knowledge Graph SQLite databases to reviewable JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.kg_tools import export_knowledge_graph


def export_universe(universe_id: str) -> Path:
    output_dir = PROJECT_ROOT / "kg" / universe_id
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "export.json"
    data = export_knowledge_graph(universe_id)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "universes",
        nargs="*",
        default=["tolkien", "terran_empire"],
        help="Universe ids to export. Defaults to tolkien and terran_empire.",
    )
    args = parser.parse_args()

    for universe_id in args.universes:
        path = export_universe(universe_id)
        print(path.relative_to(PROJECT_ROOT).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
