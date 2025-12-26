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
    get_models_dir,
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

    models_dir = get_models_dir()
    models_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("ULTRALYTICS_CACHE_DIR", str(models_dir))

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

    logger.info("Loading YOLOv8 pose model on CPU (cache: %s)", models_dir)
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
    import json
    import subprocess
    import importlib.util
    import tkinter as tk
    from tkinter import filedialog, messagebox
    from tkinter import ttk

    root = tk.Tk()
    root.title(f"GrapplingOverlay v{__version__}")
    root.geometry("640x640")
    root.minsize(600, 600)

    status_var = tk.StringVar(value="Ready")
    progress_var = tk.DoubleVar(value=0.0)

    def append_log(message: str) -> None:
        log_text.configure(state="normal")
        log_text.insert("end", message + "\n")
        log_text.see("end")
        lines = int(log_text.index("end-1c").split(".")[0])
        if lines > 200:
            log_text.delete("1.0", "3.0")
        log_text.configure(state="disabled")

    def set_buttons_state(enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for button in action_buttons:
            button.config(state=state)
        btn_cancel.config(state="normal" if not enabled else "disabled")

    def on_cancel():
        status_var.set("Cancelled")
        progress_var.set(0.0)
        append_log("Cancelled current action.")

    def on_check_updates():
        launcher = _find_launcher(crashguard.get_base_dir())
        if not launcher:
            messagebox.showerror(
                "Update Error",
                "Launcher not found. Please reinstall GrapplingOverlayLauncher.",
            )
            return
        logger.info("Launching update check: %s", launcher)
        subprocess.Popen([str(launcher), "--check"], close_fds=True)
        root.destroy()

    def on_update_now():
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
            set_buttons_state(False)
            status_var.set("Running synthetic test...")
            progress_var.set(20.0)
            root.update_idletasks()
            _run_test_mode(60, output_dir, logger, show_dialog=True)
            append_log("Synthetic test completed.")
            progress_var.set(100.0)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Test mode failed: %s", exc)
            append_log(f"Test mode failed: {exc}")
            messagebox.showerror(
                "Test Mode Error",
                f"Test mode failed:\n{exc}\n\nSee logs for details.",
            )
        finally:
            status_var.set("Ready")
            progress_var.set(0.0)
            set_buttons_state(True)

    def on_validate_output():
        output_file = filedialog.askopenfilename(
            title="Validate Output JSON",
            filetypes=[
                ("JSON Files", "*.json"),
                ("All Files", "*.*"),
            ],
        )
        if not output_file:
            return
        try:
            payload = json.loads(Path(output_file).read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Output JSON must be an object.")
            if "frames" not in payload:
                raise ValueError("Output JSON missing required 'frames' key.")
            if not isinstance(payload["frames"], list):
                raise ValueError("Output JSON 'frames' must be a list.")
            messagebox.showinfo(
                "Output JSON Valid",
                f"Output JSON looks valid:\n{output_file}",
            )
            append_log(f"Validated output JSON: {output_file}")
            logger.info("Validated output JSON: %s", output_file)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Output JSON validation failed: %s", exc)
            append_log(f"Output JSON validation failed: {exc}")
            messagebox.showerror(
                "Output JSON Invalid",
                f"Output JSON validation failed:\n{exc}",
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
            status_var.set("Model missing")
            append_log("Model missing: ultralytics not installed.")
            messagebox.showwarning(
                "Model Not Installed",
                "Video overlay model not installed in this build yet. "
                "Update to the latest version to install the pose model package.",
            )
            return
        try:
            set_buttons_state(False)
            status_var.set("Processing video...")
            progress_var.set(15.0)
            root.update_idletasks()
            output_path = _run_video_mode(Path(video), output_dir, logger)
            append_log(f"Video overlay complete: {output_path}")
            messagebox.showinfo(
                "Overlay Preview Complete",
                f"Preview finished.\n\nOutputs written to:\n{output_path}",
            )
            progress_var.set(100.0)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Video processing failed: %s", exc)
            append_log(f"Video processing failed: {exc}")
            messagebox.showerror(
                "Video Error",
                f"Unable to process video:\n{exc}\n\nSee logs for details.",
            )
        finally:
            status_var.set("Ready")
            progress_var.set(0.0)
            set_buttons_state(True)

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

    top_frame = tk.Frame(root)
    top_frame.pack(fill="x", padx=12, pady=8)

    buttons_frame = tk.Frame(top_frame)
    buttons_frame.pack(fill="x")

    btn_test = tk.Button(buttons_frame, text="Synthetic Test", command=on_test_mode)
    btn_video = tk.Button(buttons_frame, text="Open Video", command=on_open_video)
    btn_validate = tk.Button(buttons_frame, text="Validate JSON", command=on_validate_output)
    btn_check_updates = tk.Button(
        buttons_frame, text="Check Updates", command=on_check_updates
    )
    btn_update_now = tk.Button(buttons_frame, text="Update Now", command=on_update_now)
    btn_cancel = tk.Button(buttons_frame, text="Cancel", command=on_cancel)

    for idx, button in enumerate(
        (
            btn_test,
            btn_video,
            btn_validate,
            btn_check_updates,
            btn_update_now,
            btn_cancel,
        )
    ):
        button.grid(row=0, column=idx, padx=4, pady=4, sticky="ew")
        buttons_frame.columnconfigure(idx, weight=1)

    log_frame = tk.Frame(root)
    log_frame.pack(fill="both", expand=True, padx=12, pady=(0, 8))

    log_text = tk.Text(log_frame, height=14, state="disabled", wrap="word")
    log_scroll = tk.Scrollbar(log_frame, command=log_text.yview)
    log_text.configure(yscrollcommand=log_scroll.set)
    log_text.pack(side="left", fill="both", expand=True)
    log_scroll.pack(side="right", fill="y")

    for line in (
        f"GrapplingOverlay v{__version__}",
        "Ready.",
    ):
        append_log(line)

    bottom_frame = tk.Frame(root)
    bottom_frame.pack(fill="x", padx=12, pady=(0, 12))

    status_label = tk.Label(bottom_frame, textvariable=status_var, font=("Segoe UI", 10))
    status_label.pack(anchor="w")

    progress = ttk.Progressbar(
        bottom_frame,
        orient="horizontal",
        mode="determinate",
        maximum=100.0,
        variable=progress_var,
    )
    progress.pack(fill="x", pady=6)

    folder_frame = tk.Frame(bottom_frame)
    folder_frame.pack(fill="x")

    btn_logs = tk.Button(folder_frame, text="Open Logs Folder", command=on_open_logs)
    btn_outputs = tk.Button(
        folder_frame, text="Open Outputs Folder", command=on_open_outputs
    )
    btn_data = tk.Button(folder_frame, text="Open Data Folder", command=on_open_data)

    btn_logs.grid(row=0, column=0, padx=4, pady=4, sticky="ew")
    btn_outputs.grid(row=0, column=1, padx=4, pady=4, sticky="ew")
    btn_data.grid(row=0, column=2, padx=4, pady=4, sticky="ew")
    for idx in range(3):
        folder_frame.columnconfigure(idx, weight=1)

    action_buttons = [
        btn_test,
        btn_video,
        btn_validate,
        btn_check_updates,
        btn_update_now,
        btn_logs,
        btn_outputs,
        btn_data,
    ]

    set_buttons_state(True)

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
