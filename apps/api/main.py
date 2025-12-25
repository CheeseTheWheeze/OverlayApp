from __future__ import annotations

from fastapi import FastAPI

from core.inference import run_inference

app = FastAPI()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/infer")
def infer(payload: dict) -> dict:
    frames = payload.get("frames", [])
    config = payload.get("config", {})
    return run_inference(frames, config)
