#!/usr/bin/env python3
"""Meicut REST API quickstart — the smallest useful end-to-end flow.

    1. Upload a video            POST /api/v1/upload
    2. Submit a cut job          POST /api/v1/video-tool
    3. Poll until done           GET  /api/v1/job/{job_id}/status
    4. Download the result       (presigned URL from the job status)

Zero dependencies: Python 3.8+ standard library only.

Usage:
    set MEICUT_API_KEY=mv_your_api_key          # Windows cmd
    export MEICUT_API_KEY=mv_your_api_key       # macOS / Linux
    python rest_quickstart.py [path/to/video.mp4]

Get an API key: https://meicut.com (sign in -> developer console)
Full API reference: https://meicut.com/developer-docs
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

# Default demo asset shipped with this repo; pass your own file as argv[1].
MEDIA_FILE = sys.argv[1] if len(sys.argv) > 1 else str(
    Path(__file__).resolve().parent.parent / "assets" / "sample.mp4"
)
OUTPUT_FILE = "quickstart_result.mp4"

POLL_INTERVAL = 3      # seconds between status checks
POLL_TIMEOUT = 300     # give up after 5 minutes


def request(method, url, body=None, headers=None, raw=None):
    """Minimal HTTP helper. Returns (status_code, parsed_json_or_text)."""
    data = raw
    hdrs = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode()
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            text = resp.read().decode("utf-8", "replace")
            return resp.status, _maybe_json(text)
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", "replace")
        raise SystemExit(f"HTTP {e.code} from {url}: {text}")


def _maybe_json(text):
    try:
        return json.loads(text)
    except ValueError:
        return text


def upload_file(path):
    """POST /api/v1/upload — multipart/form-data, returns stored_name."""
    boundary = "----meicut-demo-boundary"
    filename = os.path.basename(path)
    with open(path, "rb") as f:
        content = f.read()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()

    status, resp = request(
        "POST", f"{API}/v1/upload", raw=body,
        headers={
            "X-API-Key": API_KEY,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    print(f"[1/4] Uploaded {filename} ({len(content)} bytes) -> stored_name: {resp['stored_name']}")
    mi = resp.get("media_info") or {}
    if mi.get("duration"):
        dims = f" {mi['width']}x{mi['height']}" if mi.get("width") else ""
        print(f"      duration={mi['duration']}s{dims}")
    return resp["stored_name"]


def submit_cut(stored_name):
    """POST /api/v1/video-tool — cut the first 2 seconds, returns job_id."""
    status, resp = request(
        "POST", f"{API}/v1/video-tool",
        body={
            "stored_name": stored_name,
            "tool": "cut-video",
            "params": {"start_time": 0, "duration": 2},
        },
        headers={"X-API-Key": API_KEY},
    )
    print(f"[2/4] Cut job submitted -> job_id: {resp['job_id']}")
    return resp["job_id"]


def wait_for_job(job_id):
    """GET /api/v1/job/{job_id}/status — poll until completed/failed."""
    print("[3/4] Waiting for the job", end="", flush=True)
    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        status, resp = request(
            "GET", f"{API}/v1/job/{job_id}/status",
            headers={"X-API-Key": API_KEY},
        )
        state = resp.get("status")
        if state == "completed":
            print(f" completed (progress={resp.get('progress')}%)")
            return resp
        if state == "failed":
            raise SystemExit(f"\nJob failed: {resp.get('error')}")
        print(".", end="", flush=True)
        time.sleep(POLL_INTERVAL)
    raise SystemExit("\nTimed out waiting for the job")


def download(url, dest):
    """Job status contains a presigned download_url — no auth needed."""
    urllib.request.urlretrieve(url, dest)
    size = os.path.getsize(dest)
    print(f"[4/4] Downloaded -> {dest} ({size} bytes)")


def main():
    if not API_KEY:
        raise SystemExit("Set MEICUT_API_KEY first (get one at https://meicut.com)")
    if not os.path.exists(MEDIA_FILE):
        raise SystemExit(f"Media file not found: {MEDIA_FILE}")

    stored_name = upload_file(MEDIA_FILE)
    job_id = submit_cut(stored_name)
    result = wait_for_job(job_id)
    download(result["download_url"], OUTPUT_FILE)
    print("Done! The same pattern works for all 8 REST endpoints --")
    print("see rest_full_suite.py for every tool, and mcp_client.py for MCP.")


if __name__ == "__main__":
    main()
