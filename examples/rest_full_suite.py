#!/usr/bin/env python3
"""Meicut REST API full validation suite.

Exercises every public endpoint end-to-end and prints a pass/fail report —
use it to verify your integration, your plan's limits, or the API itself:

    * POST /api/v1/upload              (video + audio)
    * POST /api/v1/video-tool          (cut-video)
    * POST /api/v1/video-tool/merge
    * POST /api/v1/audio-tool          (cut-audio)
    * POST /api/v1/audio-tool/merge
    * POST /api/v1/convert-tool        (video -> webm)
    * POST /api/v1/compress
    * GET  /api/v1/job/{job_id}/status (+ result download check)
    * error handling: 401 / 400 / 404

Zero dependencies: Python 3.8+ standard library only.
Note: free plans allow 2 concurrent developer jobs, so jobs run serially here.

Usage:
    set MEICUT_API_KEY=mv_your_api_key
    python rest_full_suite.py [path/to/video.mp4] [path/to/audio.mp3]
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API_KEY = os.environ.get("MEICUT_API_KEY", "")
BASE_URL = os.environ.get("MEICUT_BASE_URL", "https://meicut.com").rstrip("/")
API = f"{BASE_URL}/api"

ASSETS = Path(__file__).resolve().parent.parent / "assets"
VIDEO_FILE = sys.argv[1] if len(sys.argv) > 1 else str(ASSETS / "sample.mp4")
AUDIO_FILE = sys.argv[2] if len(sys.argv) > 2 else str(ASSETS / "sample.mp4")  # mp4 works as audio source too

POLL_INTERVAL = 3
POLL_TIMEOUT = 300

results = []


def report(name, ok, detail=""):
    results.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""), flush=True)


def request(method, url, body=None, headers=None, raw=None, auth=True):
    data = raw
    hdrs = dict(headers or {})
    if auth:
        hdrs["X-API-Key"] = API_KEY
    if body is not None:
        data = json.dumps(body).encode()
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def upload(path):
    boundary = "----meicut-suite-boundary"
    filename = os.path.basename(path)
    with open(path, "rb") as f:
        content = f.read()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
    status, text = request("POST", f"{API}/v1/upload", raw=body,
                           headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    if status == 200:
        return json.loads(text)["stored_name"]
    report(f"upload {filename}", False, f"HTTP {status}: {text[:150]}")
    return None


def run_job(name, url, payload):
    """Submit a job and poll to completion. Records PASS only if the result downloads."""
    status, text = request("POST", f"{API}{url}", body=payload)
    if status != 200:
        report(name, False, f"submit HTTP {status}: {text[:150]}")
        return
    job_id = json.loads(text)["job_id"]
    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        status, text = request("GET", f"{API}/v1/job/{job_id}/status")
        job = json.loads(text)
        if job.get("status") == "completed":
            # Verify the presigned download_url actually serves the file.
            dl = job.get("download_url", "")
            dl_status, _ = request("GET", dl, auth=False) if dl.startswith("http") else (0, "")
            ok = dl_status == 200
            report(name, ok, f"completed, download_url HTTP {dl_status}")
            return
        if job.get("status") == "failed":
            report(name, False, f"job failed: {job.get('error')}")
            return
        time.sleep(POLL_INTERVAL)
    report(name, False, "timeout waiting for job")


def main():
    if not API_KEY:
        raise SystemExit("Set MEICUT_API_KEY first (get one at https://meicut.com)")
    print(f"Base URL: {BASE_URL}\nVideo: {VIDEO_FILE}\nAudio: {AUDIO_FILE}\n")

    # ── Auth and validation errors ──
    status, _ = request("POST", f"{API}/v1/video-tool",
                        body={"stored_name": "x.mp4", "tool": "cut-video"}, auth=False)
    report("missing API key -> 401", status == 401, f"HTTP {status}")

    status, text = request("POST", f"{API}/v1/video-tool",
                           body={"stored_name": "x.mp4", "tool": "cut-video"},
                           headers={"X-API-Key": "mv_invalid"}, auth=False)
    report("invalid API key -> 401", status == 401, f"HTTP {status}")

    # ── Uploads ──
    video_sn = upload(VIDEO_FILE)
    report("upload video", bool(video_sn), video_sn or "")
    audio_sn = upload(AUDIO_FILE)
    report("upload audio", bool(audio_sn), audio_sn or "")
    if not (video_sn and audio_sn):
        print("ABORT: uploads failed")
        sys.exit(1)

    # ── Every tool endpoint, serially (free plan: 2 concurrent jobs) ──
    run_job("video-tool cut-video", "/v1/video-tool",
            {"stored_name": video_sn, "tool": "cut-video", "params": {"start_time": 0, "duration": 2}})
    run_job("video-tool/merge", "/v1/video-tool/merge",
            {"stored_names": [video_sn, video_sn], "params": {"resolution_mode": "auto"}})
    run_job("audio-tool cut-audio", "/v1/audio-tool",
            {"stored_name": audio_sn, "tool": "cut-audio", "params": {"start_time": 0, "duration": 2}})
    run_job("audio-tool/merge", "/v1/audio-tool/merge",
            {"stored_names": [audio_sn, audio_sn]})
    run_job("convert-tool video->webm", "/v1/convert-tool",
            {"stored_name": video_sn, "tool": "video-converter", "params": {"format": "webm"}})
    run_job("compress 480p", "/v1/compress",
            {"stored_name": video_sn, "quality": "medium", "resolution": "480p", "remove_audio": False})

    # ── Validation errors ──
    status, _ = request("POST", f"{API}/v1/video-tool/merge", body={"stored_names": [video_sn]})
    report("merge with <2 files -> 400", status == 400, f"HTTP {status}")

    status, text = request("POST", f"{API}/v1/video-tool",
                           body={"stored_name": video_sn, "tool": "no-such-tool"})
    report("unknown tool -> 400", status == 400, f"HTTP {status}")

    status, _ = request("GET", f"{API}/v1/job/00000000-0000-0000-0000-000000000000/status")
    report("unknown job_id -> 404", status == 404, f"HTTP {status}")

    # ── Summary ──
    passed = sum(1 for _, ok in results if ok)
    print(f"\n===== {passed}/{len(results)} passed =====")
    failed = [name for name, ok in results if not ok]
    if failed:
        print("Failed: " + ", ".join(failed))
        sys.exit(1)
    print("All endpoints are working. Docs: https://meicut.com/developer-docs")


if __name__ == "__main__":
    main()
