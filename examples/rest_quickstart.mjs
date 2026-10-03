#!/usr/bin/env node
/**
 * Meicut REST API quickstart (Node.js) — the smallest useful end-to-end flow.
 *
 *   1. Upload a video            POST /api/v1/upload
 *   2. Submit a cut job          POST /api/v1/video-tool
 *   3. Poll until done           GET  /api/v1/job/{job_id}/status
 *   4. Download the result       (presigned URL from the job status)
 *
 * Zero dependencies: Node 18+ built-in fetch / FormData / Blob.
 *
 * Usage:
 *   set MEICUT_API_KEY=mv_your_api_key          :: Windows cmd
 *   export MEICUT_API_KEY=mv_your_api_key       #  macOS / Linux
 *   node rest_quickstart.mjs [path/to/video.mp4]
 *
 * Get an API key: https://meicut.com (sign in -> developer console)
 * Full API reference: https://meicut.com/developer-docs
 */
import { readFile, writeFile } from 'node:fs/promises'
import { basename, dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const API_KEY = process.env.MEICUT_API_KEY || ''
const BASE_URL = (process.env.MEICUT_BASE_URL || 'https://meicut.com').replace(/\/$/, '')
const API = `${BASE_URL}/api`

const here = dirname(fileURLToPath(import.meta.url))
const MEDIA_FILE = process.argv[2] || join(here, '..', 'assets', 'sample.mp4')
const OUTPUT_FILE = 'quickstart_result.mp4'

const POLL_INTERVAL = 3000
const POLL_TIMEOUT = 5 * 60 * 1000

async function api(method, path, { body, form } = {}) {
  const headers = { 'X-API-Key': API_KEY }
  let payload
  if (form) {
    payload = form // FormData sets its own multipart boundary
  } else if (body) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }
  const resp = await fetch(`${API}${path}`, { method, headers, body: payload })
  const text = await resp.text()
  if (!resp.ok) throw new Error(`HTTP ${resp.status} from ${path}: ${text}`)
  return JSON.parse(text)
}

async function uploadFile(path) {
  const content = await readFile(path)
  const form = new FormData()
  form.append('file', new Blob([content]), basename(path))
  const resp = await api('POST', '/v1/upload', { form })
  console.log(`[1/4] Uploaded ${basename(path)} (${content.length} bytes) -> stored_name: ${resp.stored_name}`)
  return resp.stored_name
}

async function submitCut(storedName) {
  const resp = await api('POST', '/v1/video-tool', {
    body: {
      stored_name: storedName,
      tool: 'cut-video',
      params: { start_time: 0, duration: 2 },
    },
  })
  console.log(`[2/4] Cut job submitted -> job_id: ${resp.job_id}`)
  return resp.job_id
}

async function waitForJob(jobId) {
  process.stdout.write('[3/4] Waiting for the job')
  const deadline = Date.now() + POLL_TIMEOUT
  while (Date.now() < deadline) {
    const job = await api('GET', `/v1/job/${jobId}/status`)
    if (job.status === 'completed') {
      console.log(` completed (progress=${job.progress}%)`)
      return job
    }
    if (job.status === 'failed') throw new Error(`Job failed: ${job.error}`)
    process.stdout.write('.')
    await new Promise((r) => setTimeout(r, POLL_INTERVAL))
  }
  throw new Error('Timed out waiting for the job')
}

async function download(url, dest) {
  const resp = await fetch(url) // presigned URL — no auth needed
  if (!resp.ok) throw new Error(`Download failed: HTTP ${resp.status}`)
  const buf = Buffer.from(await resp.arrayBuffer())
  await writeFile(dest, buf)
  console.log(`[4/4] Downloaded -> ${dest} (${buf.length} bytes)`)
}

if (!API_KEY) {
  console.error('Set MEICUT_API_KEY first (get one at https://meicut.com)')
  process.exit(1)
}

const storedName = await uploadFile(MEDIA_FILE)
const jobId = await submitCut(storedName)
const result = await waitForJob(jobId)
await download(result.download_url, OUTPUT_FILE)
console.log('Done! See https://meicut.com/developer-docs for all 8 endpoints and MCP.')
