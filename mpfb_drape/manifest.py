"""Aggregate per-design drape results into one wardrobe manifest."""
from __future__ import annotations
import json
from pathlib import Path


def build(body_name, results):
    passed = sum(1 for r in results if r["verdict"]["passed"])
    return {
        "body": body_name,
        "designs": results,
        "summary": {"total": len(results), "passed": passed,
                    "failed": len(results) - passed},
    }


def write(man, path):
    path = Path(path)
    path.write_text(json.dumps(man, indent=2))
    return path
