"""Cheap STAMP_CONFIG vs stamp-config.default.json alignment check."""

from __future__ import annotations

import json
import re
import unittest

from support import REPO_ROOT


def _js_object_to_dict(blob: str) -> dict:
    quoted = re.sub(r"([{\[,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', blob)
    quoted = re.sub(r",(\s*[}\]])", r"\1", quoted)
    return json.loads(quoted)


def _stamp_config_from_viewer() -> dict:
    js = (REPO_ROOT / "app" / "static" / "viewer.js").read_text(encoding="utf-8")
    token = "const STAMP_CONFIG = "
    start = js.index(token) + len(token)
    depth = 0
    end = None
    for i, ch in enumerate(js[start:]):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = start + i + 1
                break
    if end is None:
        raise AssertionError("STAMP_CONFIG object not closed")
    return _js_object_to_dict(js[start:end])


class StampDriftTests(unittest.TestCase):
    def test_stamp_config_matches_default_json_overlap(self) -> None:
        default = json.loads((REPO_ROOT / "app" / "stamp-config.default.json").read_text(encoding="utf-8"))
        live = _stamp_config_from_viewer()
        for key in ("globalScale", "stampOffsetX", "stampOffsetY", "n4", "n2", "n1", "tick"):
            self.assertEqual(live[key], default[key], key)


if __name__ == "__main__":
    unittest.main()
