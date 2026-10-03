# Meicut API 示例

[English](README.md)

**[Meicut](https://meicut.com) 开发者平台**的可运行示例 —— 通过简洁的 REST API 处理视频/音频，另有托管的 **MCP（Model Context Protocol）服务器**，让 AI 助手（Claude、Cursor 等）直接调用 25 个媒体工具。

所有示例**零依赖**（Python 标准库 / Node 18+ 内置模块），开箱即可对线上 API 运行，同时也可作为平台的端到端验证套件。

- API 文档：<https://meicut.com/zh/developer-docs>
- 示例与教程：<https://meicut.com/zh/examples>
- 获取 API Key：在 <https://meicut.com> 注册后进入开发者控制台

## 5 分钟上手

```bash
# 1. 在 https://meicut.com 开发者控制台拿到 API Key，然后：
export MEICUT_API_KEY=mv_你的key             # Windows cmd: set MEICUT_API_KEY=mv_...

# 2. 跑 quickstart —— 上传内置样片、裁剪、下载结果
python examples/rest_quickstart.py

# 3. 验证全部接口（上传、所有工具、合并、转换、压缩、错误处理）
python examples/rest_full_suite.py

# 4. 体验 MCP 服务器（initialize -> tools/list -> cut_video -> 查状态）
python examples/mcp_client.py

# 习惯 Node.js？同样的流程：
node examples/rest_quickstart.mjs
```

脚本读取两个环境变量：

| 变量 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `MEICUT_API_KEY` | 是 | — | 你的 API Key（`mv_...`） |
| `MEICUT_BASE_URL` | 否 | `https://meicut.com` | 自建/测试环境覆盖 |

把第一个参数换成你自己的媒体文件（默认用内置 `assets/sample.mp4`）：

```bash
python examples/rest_quickstart.py /path/to/video.mp4
```

## 目录内容

| 文件 | 演示内容 |
|---|---|
| `examples/rest_quickstart.py` | 最简 REST 流程：上传 → 裁剪 → 轮询 → 下载 |
| `examples/rest_full_suite.py` | 全部 8 个 REST 端点 + 错误处理，pass/fail 报告 |
| `examples/mcp_client.py` | MCP Streamable HTTP 传输：initialize、tools/list、tools/call |
| `examples/rest_quickstart.mjs` | Node.js 版同样的 REST 流程（fetch + FormData） |
| `mcp/mcp.json` | Claude Desktop / Cursor 配置（Streamable HTTP） |
| `mcp/mcp-sse-legacy.json` | 旧版 SSE 传输配置 |
| `assets/sample.mp4` | 演示小片（3 秒，640×360，带音轨） |

## REST API 概览

Base URL：`https://meicut.com/api`，所有请求带 `X-API-Key` 头。

| 端点 | 用途 |
|---|---|
| `POST /api/v1/upload` | 上传媒体文件，获得 `stored_name` |
| `POST /api/v1/video-tool` | 视频工具（14 个：裁剪、缩放、裁帧、旋转、翻转、变速、倒放、循环、静音、加音频、加字幕、加文字、滤镜） |
| `POST /api/v1/video-tool/merge` | 合并 2+ 个视频 |
| `POST /api/v1/audio-tool` | 音频工具（裁剪、变速、音量、转换） |
| `POST /api/v1/audio-tool/merge` | 合并 2+ 个音频 |
| `POST /api/v1/convert-tool` | 视频（mp4/avi/mov/mkv/webm/gif）或图片（jpg/png/webp/gif/bmp/svg）格式转换 |
| `POST /api/v1/compress` | 视频压缩（质量 + 分辨率预设） |
| `GET /api/v1/job/{job_id}/status` | 轮询进度；完成后返回带预签名的 `download_url` |

所有处理均为异步：提交 → 获得 `job_id` → 轮询至 `completed` → 从预签名 URL 下载。

## MCP 服务器

Meicut 托管远程 MCP 服务器，提供 **25 个工具**。推荐 Streamable HTTP 传输：

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

旧客户端可用 SSE 传输：`https://meicut.com/mcp/sse?api_key=mv_your_api_key`。

把配置放进 Claude Desktop / Cursor 后，直接说"把我视频前 10 秒剪出来""把这个文件压成 720p"即可。自建客户端可参考 `examples/mcp_client.py` 的原始 JSON-RPC 流程。

## 错误码

| HTTP | 含义 |
|---|---|
| 400 | 参数错误（如未知工具、合并少于 2 个文件） |
| 401 | 缺少或无效 API Key |
| 402 | 额度用尽，请升级套餐 |
| 403 | 套餐不含该功能 |
| 404 | 文件或任务不存在 |
| 413 | 文件过大 |
| 429 | 并发/频率超限，请等待进行中的任务完成 |

## 许可

MIT —— 见 [LICENSE](LICENSE)。Meicut API 为托管服务，示例代码可随意复制到你自己的项目。
