#!/usr/bin/env python3
"""Meicut MCP client — talks to the hosted MCP server over Streamable HTTP.

The Meicut MCP server exposes 25 media-processing tools (cut, merge, resize,
convert, compress, ...) via the Model Context Protocol. This example uses the
modern Streamable HTTP transport:

    POST /mcp      JSON-RPC in, JSON out. Auth: Authorization: Bearer <api_key>
                   The server returns a Mcp-Session-Id header on initialize —
                   send it back on subsequent requests.

(A legacy SSE transport also exists at GET /mcp/sse?api_key=... for older
clients; it exchanges the same JSON-RPC messages over an event stream.)

Flow demonstrated:
    initialize -> tools/list -> upload_file -> cut_video -> get_job_status

Zero dependencies: Python 3.8+ standard library only.

Usage:
    set MEICUT_API_KEY=mv_your_api_key
    python mcp_client.py [path/to/video.mp4]
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
MCP_URL = f"{BASE_URL}/mcp"

ASSETS = Path(__file__).resolve().parent.parent / "assets"
MEDIA_FILE = sys.argv[1] if len(sys.argv) > 1 else str(ASSETS / "sample.mp4")

PROTOCOL_VERSION = "2025-03-26"
POLL_INTERVAL = 3
POLL_TIMEOUT = 300


class McpClient:
    """Minimal MCP client for the Streamable HTTP transport."""

    def __init__(self, url, api_key):
        self.url = url
        self.api_key = api_key
        self.session_id = None
        self._next_id = 0

    def call(self, method, params=None):
        self._next_id += 1
        body = {"jsonrpc": "2.0", "id": self._next_id, "method": method}
        if params is not None:
            body["params"] = params
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        req = urllib.request.Request(self.url, data=json.dumps(body).encode(),
                                     headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                # initialize issues a session id — keep it for later calls.
                sid = resp.headers.get("Mcp-Session-Id")
                if sid:
                    self.session_id = sid
                if resp.status == 202:  # notification accepted, no body
                    return None
                return json.loads(resp.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            raise SystemExit(f"HTTP {e.code} from {self.url}: {e.read().decode('utf-8', 'replace')}")

    def notify(self, method):
        body = {"jsonrpc": "2.0", "method": method}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        req = urllib.request.Request(self.url, data=json.dumps(body).encode(),
                                     headers=headers, method="POST")
        urllib.request.urlopen(req, timeout=30).close()

    def call_tool(self, name, arguments):
        resp = self.call("tools/call", {"name": name, "arguments": arguments})
        result = resp.get("result", {})
        if result.get("isError"):
            raise SystemExit(f"Tool {name} failed: {result['content'][0]['text']}")
        # Tool results are JSON-encoded text content.
        return json.loads(result["content"][0]["text"])


def upload_via_rest(path):
    """MCP tools reference files by stored_name; upload over REST first.

    (Inside a real MCP client the LLM would call the upload_file tool with a
    path on the server's uploads dir, or upload_from_url with a public URL.
    From outside the server, REST upload is the way to get a stored_name.)
    """
    boundary = "----meicut-mcp-demo"
    filename = os.path.basename(path)
    with open(path, "rb") as f:
        content = f.read()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"{BASE_URL}/api/v1/upload", data=body, method="POST",
        headers={"X-API-Key": API_KEY,
                 "Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        stored_name = json.loads(resp.read().decode())["stored_name"]
    print(f"[upload] {filename} -> stored_name: {stored_name}")
    return stored_name


def main():
    if not API_KEY:
        raise SystemExit("Set MEICUT_API_KEY first (get one at https://meicut.com)")

    client = McpClient(MCP_URL, API_KEY)

    # ── 1. initialize (negotiates protocol version, issues session id) ──
    resp = client.call("initialize", {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {},
        "clientInfo": {"name": "meicut-python-example", "version": "1.0.0"},
    })
    server = resp["result"]["serverInfo"]
    print(f"[initialize] {server['name']} v{server['version']}, "
          f"protocol {resp['result']['protocolVersion']}, session {client.session_id}")
    client.notify("notifications/initialized")

    # ── 2. tools/list — 25 tools your MCP client can offer the model ──
    resp = client.call("tools/list")
    tools = resp["result"]["tools"]
    print(f"[tools/list] {len(tools)} tools: " + ", ".join(t["name"] for t in tools[:8]) + ", ...")

    # ── 3. upload a file, then cut it ──
    stored_name = upload_via_rest(MEDIA_FILE)
    job = client.call_tool("cut_video", {
        "stored_name": stored_name,
        "start_time": 0,
        "duration": 2,
    })
    job_id = job["job_id"]
    print(f"[cut_video] queued -> job_id: {job_id}")

    # ── 4. poll get_job_status until the result is ready ──
    print("[get_job_status] waiting", end="", flush=True)
    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        status = client.call_tool("get_job_status", {"job_id": job_id})
        if status.get("status") == "completed":
            print(f" completed\n  output: {status.get('output_file')}")
            print(f"  download_url: {status.get('download_url', '')[:100]}...")
            print("\nDone! Point Claude Desktop / Cursor at the same server with mcp/mcp.json.")
            return
        if status.get("status") == "failed":
            raise SystemExit(f"\nJob failed: {status.get('error')}")
        print(".", end="", flush=True)
        time.sleep(POLL_INTERVAL)
    raise SystemExit("\nTimed out waiting for the job")


if __name__ == "__main__":
    main()
