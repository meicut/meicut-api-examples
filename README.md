# Meicut API Examples

[中文文档](README.zh-CN.md)

Runnable examples for the **[Meicut](https://meicut.com) developer platform** — video/audio processing over a simple REST API, plus a hosted **MCP (Model Context Protocol) server** that lets AI assistants (Claude, Cursor, ...) call 25 media tools directly.

Every script here is **zero-dependency** (Python standard library / Node 18+ built-ins) and runs out of the box against the live API. They double as an end-to-end validation suite for the platform.

- API reference: <https://meicut.com/developer-docs>
- Examples & guides: <https://meicut.com/examples>
- Get an API key: sign up at <https://meicut.com>, then open the developer console

## Quick start (5 minutes)

```bash
# 1. Get your API key from https://meicut.com (developer console), then:
export MEICUT_API_KEY=mv_your_api_key        # Windows cmd: set MEICUT_API_KEY=mv_...

# 2. Run the quickstart — upload the bundled sample, cut it, download the result
python examples/rest_quickstart.py

# 3. Validate every endpoint (upload, all tools, merge, convert, compress, errors)
python examples/rest_full_suite.py

# 4. Talk to the MCP server (initialize -> tools/list -> cut_video -> status)
python examples/mcp_client.py

# Node.js instead of Python? Same flow:
node examples/rest_quickstart.mjs
```

Scripts read two environment variables:

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `MEICUT_API_KEY` | yes | — | Your API key (`mv_...`) |
| `MEICUT_BASE_URL` | no | `https://meicut.com` | Override for self-hosted/staging |

Pass your own media file as the first argument instead of the bundled `assets/sample.mp4`:

```bash
python examples/rest_quickstart.py /path/to/video.mp4
```

## What's in the box

| File | What it demonstrates |
|---|---|
| `examples/rest_quickstart.py` | The minimal REST flow: upload → cut → poll → download |
| `examples/rest_full_suite.py` | All 8 REST endpoints + error handling, with a pass/fail report |
| `examples/mcp_client.py` | MCP over Streamable HTTP: initialize, tools/list, tools/call |
| `examples/rest_quickstart.mjs` | The same REST flow in Node.js (fetch + FormData) |
| `mcp/mcp.json` | Claude Desktop / Cursor config (Streamable HTTP) |
| `mcp/mcp-sse-legacy.json` | Same, for clients that only support legacy SSE |
| `assets/sample.mp4` | Tiny demo clip (3 s, 640×360, with audio) |

## REST API overview

Base URL: `https://meicut.com/api` — authenticate every request with the `X-API-Key` header.

```
X-API-Key: mv_your_api_key
```

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/upload` | Upload a media file, get a `stored_name` |
| `POST /api/v1/video-tool` | Run a video tool (14 tools: cut, resize, crop, rotate, flip, speed, reverse, loop, mute, add-audio, add-subtitles, add-text, filter) |
| `POST /api/v1/video-tool/merge` | Merge 2+ videos |
| `POST /api/v1/audio-tool` | Run an audio tool (cut, speed, volume, convert) |
| `POST /api/v1/audio-tool/merge` | Merge 2+ audio files |
| `POST /api/v1/convert-tool` | Convert video (mp4/avi/mov/mkv/webm/gif) or image (jpg/png/webp/gif/bmp/svg) |
| `POST /api/v1/compress` | Compress a video (quality + resolution presets) |
| `GET /api/v1/job/{job_id}/status` | Poll progress; completed jobs include a presigned `download_url` |

All processing is asynchronous: submit → get a `job_id` → poll until `status` is `completed` → download from the presigned URL.

## MCP server

Meicut hosts a remote MCP server with **25 tools** (`cut_video`, `merge_video`, `resize_video`, `crop_video`, `rotate_video`, `flip_video`, `speed_video`, `reverse_video`, `loop_video`, `mute_video`, `add_audio`, `add_subtitles`, `add_text`, `filter_video`, `cut_audio`, `merge_audio`, `convert_audio`, `convert_video`, `convert_image`, `compress_video`, `speed_audio`, `volume_audio`, `upload_file`, `upload_from_url`, `get_job_status`).

**Streamable HTTP transport (recommended):**

```json
{
  "mcpServers": {
    "meicut": {
      "url": "https://meicut.com/mcp",
      "headers": { "Authorization": "Bearer mv_your_api_key" }
    }
  }
}
```

**Legacy SSE transport** (older clients):

```json
{
  "mcpServers": {
    "meicut": {
      "url": "https://meicut.com/mcp/sse?api_key=mv_your_api_key"
    }
  }
}
```

Drop the config into Claude Desktop / Cursor, then ask things like *"cut the first 10 seconds of my video"* or *"compress this file to 720p"*. `examples/mcp_client.py` shows the raw JSON-RPC flow if you're building your own client.

## Errors

| HTTP | Meaning |
|---|---|
| 400 | Bad parameters (e.g. unknown tool, merge with fewer than 2 files) |
| 401 | Missing or invalid API key |
| 402 | Quota exhausted — upgrade your plan |
| 403 | Feature not included in your plan |
| 404 | File or job not found |
| 413 | File too large |
| 429 | Concurrency/rate limit — wait for running jobs to finish |

## License

MIT — see [LICENSE](LICENSE). The Meicut API itself is a hosted service; these examples are yours to copy into your own projects.
