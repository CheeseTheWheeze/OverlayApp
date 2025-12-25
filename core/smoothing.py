from __future__ import annotations

from typing import List, Dict, Any


def smooth_tracks(frames: List[Dict[str, Any]], alpha: float = 0.6) -> List[Dict[str, Any]]:
    """Apply a simple EMA smoothing over keypoints per person."""
    last_positions: Dict[int, Dict[str, Dict[str, float]]] = {}

    for frame in frames:
        for person in frame["people"]:
            pid = person["person_id"]
            if pid not in last_positions:
                last_positions[pid] = {}
            for keypoint in person["keypoints"]:
                name = keypoint["name"]
                prev = last_positions[pid].get(name)
                if prev:
                    keypoint["x"] = prev["x"] * (1 - alpha) + keypoint["x"] * alpha
                    keypoint["y"] = prev["y"] * (1 - alpha) + keypoint["y"] * alpha
                last_positions[pid][name] = {
                    "x": keypoint["x"],
                    "y": keypoint["y"],
                }
    return frames
