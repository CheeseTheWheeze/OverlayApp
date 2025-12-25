from __future__ import annotations

from typing import Iterable, List, Dict, Any

from core.smoothing import smooth_tracks
from core.tracking import assign_tracks
from core.predict import predict_occlusions


def run_inference(frames: Iterable[Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """Run mock inference pipeline on frames.

    Args:
        frames: Iterable of frames (unused for mock output but can drive frame count).
        config: Configuration options.

    Returns:
        pose_tracks dictionary matching schema.
    """
    frame_list = list(frames)
    frame_count = len(frame_list)

    raw_tracks = _mock_inference(frame_count, config)
    tracked = assign_tracks(raw_tracks)
    smoothed = smooth_tracks(tracked)
    predicted = predict_occlusions(smoothed, max_missing=3)

    return {
        "video": config.get("video", {}),
        "frames": predicted,
    }


def _mock_inference(frame_count: int, config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate mock pose outputs for two stick figures."""
    keypoint_names = [
        "head",
        "left_hand",
        "right_hand",
        "left_foot",
        "right_foot",
    ]
    frames = []
    for frame_index in range(frame_count):
        people = []
        for person_id in range(2):
            keypoints = []
            base_x = 100 + person_id * 150 + frame_index * 2
            base_y = 120 + person_id * 40
            for idx, name in enumerate(keypoint_names):
                keypoints.append(
                    {
                        "name": name,
                        "x": float(base_x + idx * 10),
                        "y": float(base_y + idx * 12),
                        "conf": 0.9,
                    }
                )
            people.append({"person_id": person_id, "keypoints": keypoints})
        frames.append({"frame_index": frame_index, "people": people})
    return frames
