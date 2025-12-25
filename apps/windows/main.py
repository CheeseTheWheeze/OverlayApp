from __future__ import annotations

import os
import sys
from pathlib import Path


def _bootstrap_paths() -> None:
    if getattr(sys, "frozen", False):
        repo_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        sys.path.insert(0, str(repo_root))
        os.chdir(Path(sys.executable).parent)
        return

    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root))


_bootstrap_paths()

from apps.windows import crashguard
from core.paths import (
    ensure_data_dirs,
    get_data_root,
    get_logs_dir,
    get_outputs_dir,
)
from core.version import __version__


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


def _run_video_mode(video_path: Path, output_dir: Path, logger, max_frames: int = 300) -> Path:
    import cv2
    from ultralytics import YOLO

    keypoint_names = [
        "nose",
        "left_eye",
        "right_eye",
        "left_ear",
        "right_ear",
        "left_shoulder",
        "right_shoulder",
        "left_elbow",
        "right_elbow",
        "left_wrist",
        "right_wrist",
        "left_hip",
        "right_hip",
        "left_knee",
        "right_knee",
        "left_ankle",
        "right_ankle",
    ]

    logger.info("Loading YOLOv8 pose model on CPU")
    model = YOLO("yolov8n-pose.pt")

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open video: {video_path}")

    pose_frames = []
    frame_index = 0
    try:
        while frame_index < max_frames:
            ret, frame = cap.read()
            if not ret:
                break
            results = model.predict(frame, device="cpu", verbose=False)
            result = results[0] if results else None
            people = []
            if result is not None and result.keypoints is not None:
                xy = result.keypoints.xy
                conf = result.keypoints.conf
                xy_values = xy.cpu().numpy() if hasattr(xy, "cpu") else xy
                conf_values = conf.cpu().numpy() if conf is not None and hasattr(conf, "cpu") else conf
                for person_id, person_xy in enumerate(xy_values):
                    keypoints = []
                    for idx, (x, y) in enumerate(person_xy):
                        name = keypoint_names[idx] if idx < len(keypoint_names) else f"kp_{idx}"
                        kp_conf = (
                            float(conf_values[person_id][idx])
                            if conf_values is not None
                            else 1.0
                        )
                        keypoints.append(
                            {
                                "name": name,
                                "x": float(x),
                                "y": float(y),
                                "conf": kp_conf,
                            }
                        )
                    people.append({"person_id": person_id, "keypoints": keypoints})

            pose_frames.append({"frame_index": frame_index, "people": people})

            if result is not None:
                preview_frame = result.plot()
            else:
                preview_frame = frame
            cv2.imshow("GrapplingOverlay Preview", preview_frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
            frame_index += 1
    finally:
        cap.release()
        cv2.destroyAllWindows()

    pose_tracks = {"video": {"path": str(video_path)}, "frames": pose_frames}
    output_path = _write_pose_tracks(pose_tracks, output_dir)
    logger.info("Wrote pose tracks to %s", output_path)
    cv2.destroyAllWindows()
    return output_path


def _open_folder(path: Path, logger, label: str) -> None:
    import subprocess

    logger.info("Opening %s folder: %s", label, path)
    if os.name == "nt":
        os.startfile(path)  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


def _find_launcher(base_dir: Path) -> Path | None:
    data_root = get_data_root()
    candidates = [
        data_root / "GrapplingOverlayLauncher.exe",
        base_dir / "GrapplingOverlayLauncher.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _build_gui(log_dir: Path, output_dir: Path, logger) -> None:
    import tkinter as tk
    from tkinter import filedialog, messagebox
    import importlib.util
    import subprocess

    root = tk.Tk()
    root.title(f"GrapplingOverlay v{__version__}")
    root.geometry("420x360")

    label = tk.Label(
        root,
        text=f"GrapplingOverlay v{__version__}",
        font=("Segoe UI", 14, "bold"),
    )
    label.pack(pady=12)

    def on_check_updates():
        launcher = _find_launcher(crashguard.get_base_dir())
        if not launcher:
            messagebox.showerror(
                "Update Error",
                "Launcher not found. Please reinstall GrapplingOverlayLauncher.",
            )
            return
        logger.info("Launching updater: %s", launcher)
        subprocess.Popen([str(launcher), "--update"], close_fds=True)
        root.destroy()

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
        if importlib.util.find_spec("ultralytics") is None:
            logger.error("Ultralytics is not installed; cannot run video overlay.")
            messagebox.showwarning(
                "Model Not Installed",
                "Video overlay model not installed in this build yet. "
                "Update to the latest version or enable the pose model package.",
            )
            return
        try:
            output_path = _run_video_mode(Path(video), output_dir, logger)
            messagebox.showinfo(
                "Overlay Preview Complete",
                f"Preview finished.\n\nOutputs written to:\n{output_path}",
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Video processing failed: %s", exc)
            messagebox.showerror(
                "Video Error",
                f"Unable to process video:\n{exc}\n\nSee logs for details.",
            )

    def on_open_logs():
        try:
            _open_folder(log_dir, logger, "logs")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to open logs folder: %s", exc)
            messagebox.showerror(
                "Open Logs Error",
                f"Unable to open logs folder:\n{exc}",
            )

    def on_open_outputs():
        try:
            _open_folder(output_dir, logger, "outputs")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to open outputs folder: %s", exc)
            messagebox.showerror(
                "Open Outputs Error",
                f"Unable to open outputs folder:\n{exc}",
            )

    def on_open_data():
        data_root = get_data_root()
        try:
            _open_folder(data_root, logger, "data")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to open data folder: %s", exc)
            messagebox.showerror(
                "Open Data Error",
                f"Unable to open data folder:\n{exc}",
            )

    menu = tk.Menu(root)
    help_menu = tk.Menu(menu, tearoff=0)
    help_menu.add_command(label="Check for Updates", command=on_check_updates)
    help_menu.add_command(label="Update Now", command=on_check_updates)
    menu.add_cascade(label="Help", menu=help_menu)
    root.config(menu=menu)

    btn_test = tk.Button(root, text="Run Test Mode (synthetic)", width=30, command=on_test_mode)
    btn_test.pack(pady=6)

    btn_video = tk.Button(
        root,
        text="Open Video File (Overlay)",
        width=36,
        height=2,
        font=("Segoe UI", 11, "bold"),
        command=on_open_video,
    )
    btn_video.pack(pady=10)

    btn_logs = tk.Button(root, text="Open Logs Folder", width=30, command=on_open_logs)
    btn_logs.pack(pady=6)

    btn_outputs = tk.Button(
        root,
        text="Open Outputs Folder",
        width=30,
        command=on_open_outputs,
    )
    btn_outputs.pack(pady=6)

    btn_data = tk.Button(root, text="Open Data Folder", width=30, command=on_open_data)
    btn_data.pack(pady=6)

    root.mainloop()


def _parse_args(argv: list[str]):
    import argparse

    parser = argparse.ArgumentParser(description="GrapplingOverlay")
    parser.add_argument("--test-mode", action="store_true", help="Run in test mode")
    parser.add_argument("--max-frames", type=int, default=60, help="Max frames to process")
    return parser.parse_args(argv[1:])


def real_main(argv: list[str]) -> int:
    import logging

    ensure_data_dirs()
    log_dir = get_logs_dir()
    output_dir = get_outputs_dir()

    logger = logging.getLogger("grappling_overlay")
    logger.info("Starting GrapplingOverlay")

    args = _parse_args(argv)
    if args.test_mode:
        return _run_test_mode(args.max_frames, output_dir, logger, show_dialog=False)

    _build_gui(log_dir, output_dir, logger)
    return 0


if __name__ == "__main__":
    sys.exit(crashguard.guarded_main(real_main, sys.argv))
