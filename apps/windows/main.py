from __future__ import annotations

import sys
from pathlib import Path

from apps.windows import crashguard


def _load_frames_for_preview(video_path: Path):
    from adapters.video_source import VideoSource

    source = VideoSource(video_path)
    return list(source.frames())


def _draw_overlay(frame, people):
    import cv2

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


def _write_pose_tracks(pose_tracks: dict, output_dir: Path) -> Path:
    import json

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "pose_tracks.json"
    output_path.write_text(json.dumps(pose_tracks, indent=2), encoding="utf-8")
    return output_path


def _run_pipeline(frame_count: int, frames: list, video_label: str, output_dir: Path):
    from core.inference import run_inference

    config = {"video": {"path": video_label}}
    pose_tracks = run_inference(frames[:frame_count], config)
    output_path = _write_pose_tracks(pose_tracks, output_dir)
    return pose_tracks, output_path


def _run_test_mode(max_frames: int, output_dir: Path, logger, show_dialog: bool) -> int:
    frames = [None] * max_frames
    _, output_path = _run_pipeline(max_frames, frames, "synthetic", output_dir)
    logger.info("Test mode completed. Output: %s", output_path)
    if show_dialog:
        from tkinter import messagebox

        messagebox.showinfo(
            "GrapplingOverlay Test Mode",
            f"PASS\n\nWrote outputs to:\n{output_path}",
        )
    return 0


def _run_video_mode(video_path: Path, output_dir: Path, logger) -> None:
    import cv2

    frames = _load_frames_for_preview(video_path)
    logger.info("Loaded %s frames from %s", len(frames), video_path)
    pose_tracks, output_path = _run_pipeline(len(frames), frames, str(video_path), output_dir)
    logger.info("Wrote pose tracks to %s", output_path)

    for frame_data in pose_tracks["frames"]:
        if frame_data["frame_index"] >= len(frames):
            break
        frame = frames[frame_data["frame_index"]].copy()
        _draw_overlay(frame, frame_data["people"])
        cv2.imshow("GrapplingOverlay Preview", frame)
        if cv2.waitKey(30) & 0xFF == ord("q"):
            break
    cv2.destroyAllWindows()


def _open_logs_folder(log_dir: Path, logger) -> None:
    import os
    import subprocess

    logger.info("Opening logs folder: %s", log_dir)
    if os.name == "nt":
        os.startfile(log_dir)  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.run(["open", str(log_dir)], check=False)
    else:
        subprocess.run(["xdg-open", str(log_dir)], check=False)


def _build_gui(log_dir: Path, output_dir: Path, logger) -> None:
    import tkinter as tk
    from tkinter import filedialog, messagebox

    root = tk.Tk()
    root.title("GrapplingOverlay")
    root.geometry("420x240")

    label = tk.Label(root, text="GrapplingOverlay", font=("Segoe UI", 14, "bold"))
    label.pack(pady=12)

    def on_test_mode():
        try:
            _run_test_mode(60, output_dir, logger, show_dialog=True)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Test mode failed: %s", exc)
            messagebox.showerror(
                "Test Mode Error",
                f"Test mode failed:\n{exc}\n\nSee logs for details.",
            )

    def on_open_video():
        video = filedialog.askopenfilename(
            title="Open Video File",
            filetypes=[
                ("Video Files", "*.mp4 *.avi *.mov *.mkv"),
                ("All Files", "*.*"),
            ],
        )
        if not video:
            return
        try:
            _run_video_mode(Path(video), output_dir, logger)
            messagebox.showinfo(
                "Overlay Preview Complete",
                "Preview finished.\n\nOutputs written to outputs/pose_tracks.json",
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Video processing failed: %s", exc)
            messagebox.showerror(
                "Video Error",
                f"Unable to process video:\n{exc}\n\nSee logs for details.",
            )

    def on_open_logs():
        try:
            _open_logs_folder(log_dir, logger)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to open logs folder: %s", exc)
            messagebox.showerror(
                "Open Logs Error",
                f"Unable to open logs folder:\n{exc}",
            )

    btn_test = tk.Button(root, text="Run Test Mode (synthetic)", width=30, command=on_test_mode)
    btn_test.pack(pady=6)

    btn_video = tk.Button(root, text="Open Video File...", width=30, command=on_open_video)
    btn_video.pack(pady=6)

    btn_logs = tk.Button(root, text="Open Logs Folder", width=30, command=on_open_logs)
    btn_logs.pack(pady=6)

    root.mainloop()


def _parse_args(argv: list[str]):
    import argparse

    parser = argparse.ArgumentParser(description="GrapplingOverlay")
    parser.add_argument("--test-mode", action="store_true", help="Run in test mode")
    parser.add_argument("--max-frames", type=int, default=60, help="Max frames to process")
    return parser.parse_args(argv[1:])


def real_main(argv: list[str]) -> int:
    import logging

    base_dir = crashguard.get_base_dir()
    log_dir, appdata_log_dir = crashguard.get_log_dirs()
    output_dir = base_dir / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    for path in (log_dir, appdata_log_dir):
        path.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("grappling_overlay")
    logger.info("Starting GrapplingOverlay")

    args = _parse_args(argv)
    if args.test_mode:
        return _run_test_mode(args.max_frames, output_dir, logger, show_dialog=False)

    _build_gui(log_dir, output_dir, logger)
    return 0


if __name__ == "__main__":
    sys.exit(crashguard.guarded_main(real_main, sys.argv))
