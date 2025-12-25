from __future__ import annotations

from typing import List, Dict, Any


def predict_occlusions(frames: List[Dict[str, Any]], max_missing: int = 3) -> List[Dict[str, Any]]:
    """Carry-forward last known keypoints for a fixed number of frames."""
    last_seen: Dict[int, Dict[str, Dict[str, float]]] = {}
    missing_counts: Dict[int, int] = {}

    for frame in frames:
        for person in frame["people"]:
            pid = person["person_id"]
            missing_counts[pid] = 0
            if pid not in last_seen:
                last_seen[pid] = {}
            for keypoint in person["keypoints"]:
                last_seen[pid][keypoint["name"]] = {
                    "x": keypoint["x"],
                    "y": keypoint["y"],
                    "conf": keypoint.get("conf", 0.0),
                }

        present_ids = {p["person_id"] for p in frame["people"]}
        for pid, last_points in list(last_seen.items()):
            if pid in present_ids:
                continue
            missing_counts[pid] = missing_counts.get(pid, 0) + 1
            if missing_counts[pid] <= max_missing:
                frame["people"].append(
                    {
                        "person_id": pid,
                        "keypoints": [
                            {
                                "name": name,
                                "x": values["x"],
                                "y": values["y"],
                                "conf": values.get("conf", 0.1),
                            }
                            for name, values in last_points.items()
                        ],
                    }
                )
    return frames
