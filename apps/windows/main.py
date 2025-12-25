from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

import cv2

from adapters.video_source import VideoSource
from core.inference import run_inference
from apps.windows.app_utils import (
    get_base_dir,
    get_local_appdata_dir,
    setup_logging,
    verify_and_prepare_dirs,
    verify_required_dlls,
    show_error,
    serialize_json,
    synthetic_frames,
)


def draw_overlay(frame, people: List[Dict[str, Any]]):
    for person in people:
        keypoints = {kp["name"]: kp for kp in person["keypoints"]}
        for kp in keypoints.values():
            cv2.circle(frame, (int(kp["x"]), int(kp["y"])), 4, (0, 255, 255), -1)
        connections = [
            ("head", "left_hand"),
            ("head", "right_hand"),
            ("left_hand", "left_foot"),
            ("right_hand", "right_foot"),
        ]
        for a, b in connections:
            if a in keypoints and b in keypoints:
                pt_a = (int(keypoints[a]["x"]), int(keypoints[a]["y"]))
                pt_b = (int(keypoints[b]["x"]), int(keypoints[b]["y"]))
                cv2.line(frame, pt_a, pt_b, (255, 0, 0), 2)


def load_frames(args: argparse.Namespace, logger: logging.Logger):
    if args.video:
        source = VideoSource(Path(args.video))
        frames = list(source.frames())
        logger.info("Loaded %s frames from %s", len(frames), args.video)
        return frames

    frames = list(synthetic_frames(args.max_frames))
    logger.info("Generated %s synthetic frames", len(frames))
    return frames


def run_app(args: argparse.Namespace) -> int:
    base_dir = get_base_dir()
    log_dir = base_dir / "logs"
    output_dir = base_dir / "outputs"
    appdata_dir = get_local_appdata_dir() / "logs"

    logger = setup_logging(log_dir, appdata_dir)
    logger.info("Starting GrapplingOverlay")

    try:
        verify_and_prepare_dirs([log_dir, output_dir, appdata_dir], logger)
        verify_required_dlls(base_dir, logger)

        frames = load_frames(args, logger)
        if args.max_frames:
            frames = frames[: args.max_frames]

        config = {"video": {"path": args.video or "synthetic"}}
        pose_tracks = run_inference(frames, config)

        output_path = output_dir / "pose_tracks.json"
        serialize_json(pose_tracks, output_path)
        logger.info("Wrote pose tracks to %s", output_path)

        if not args.headless:
            for frame_data in pose_tracks["frames"]:
                if frame_data["frame_index"] >= len(frames):
                    break
                frame = frames[frame_data["frame_index"]].copy()
                draw_overlay(frame, frame_data["people"])
                cv2.imshow("GrapplingOverlay Preview", frame)
                if cv2.waitKey(30) & 0xFF == ord("q"):
                    break
            cv2.destroyAllWindows()

        logger.info("Run completed")
        return 0
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unhandled error: %s", exc)
        message = f"GrapplingOverlay failed: {exc}\n\nSee logs for details."
        show_error(message)
        if not args.headless:
            try:
                input("Press Enter to close...")
            except EOFError:
                pass
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GrapplingOverlay")
    parser.add_argument("--video", help="Path to video file")
    parser.add_argument("--test-mode", action="store_true", help="Run in test mode")
    parser.add_argument("--headless", action="store_true", help="Disable preview window")
    parser.add_argument("--max-frames", type=int, default=60, help="Max frames to process")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    exit_code = run_app(args)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
