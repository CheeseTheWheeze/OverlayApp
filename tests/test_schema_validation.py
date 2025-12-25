from __future__ import annotations

import json
from pathlib import Path

import jsonschema


def test_pose_tracks_schema():
    schema_path = Path("docs/pose_tracks.schema.json")
    output_path = Path("outputs/pose_tracks.json")

    assert schema_path.exists(), "Schema file is missing"
    assert output_path.exists(), "Output JSON is missing; run the app first"

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    data = json.loads(output_path.read_text(encoding="utf-8"))

    jsonschema.validate(instance=data, schema=schema)
