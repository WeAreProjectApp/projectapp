#!/usr/bin/env node
/** Capture the authored GSAP timeline, reusing consecutive settled frames.
 * Hyperframes validates these compositions. Their first 4.8s per scene contain
 * motion; afterwards only the measured caption cues change until the exit.
 * Sampling stays at 30fps, including transitions. A hold never crosses a cue.
 */
import { createRequire } from 'node:module'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { spawnSync } from 'node:child_process'
import { FRONTEND_ROOT, parseArgs, requireVideo, videoDir } from './lib/paths.mjs'
import { readSchedule } from './lib/schedule.mjs'

const require = createRequire(resolve(FRONTEND_ROOT, 'package.json'))
const { chromium } = require('playwright')
const video = requireVideo(parseArgs(process.argv.slice(2)))
if (!video.startsWith('platform-')) throw new Error('This capture profile is only for platform tutorials.')
const directory = videoDir(video)
const framesDir = resolve(directory, 'renders', 'capture-frames')
mkdirSync(framesDir, { recursive: true })
const { scenes, totalDuration } = readSchedule(video)
const captions = JSON.parse(readFileSync(resolve(directory, 'captions.es.json'), 'utf8'))
const browser = await chromium.launch({
  ...(process.env.HYPERFRAMES_BROWSER_PATH ? { executablePath: process.env.HYPERFRAMES_BROWSER_PATH } : {}),
  headless: true,
})
const frames = []
try {
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 })
  await page.goto(pathToFileURL(resolve(directory, 'index.html')).href, { waitUntil: 'domcontentloaded' })
  await page.evaluate(async () => { await document.fonts.ready })
  let previousKey
  for (let frame = 0; frame < Math.round(totalDuration * 30); frame++) {
    const time = frame / 30
    const scene = scenes.find((item) => time >= item.start && time < item.end)
    const moving = time < scene.start + 4.8 || time >= scene.end - 0.3
    const cue = captions.findIndex((item) => time >= item.start && time < item.end)
    const key = moving ? `frame-${frame}` : `${scene.id}-caption-${cue}`
    if (key === previousKey) {
      frames.at(-1).count += 1
      continue
    }
    // Do not return the cyclic GSAP timeline through the browser protocol.
    await page.evaluate((at) => { window.BRAG_TIMELINE.seek(at) }, time)
    const file = resolve(framesDir, `frame-${String(frame).padStart(5, '0')}.jpg`)
    await page.screenshot({ path: file, type: 'jpeg', quality: 94 })
    frames.push({ file, count: 1 })
    previousKey = key
    if (frames.length % 120 === 0) console.log(`${video}: ${time.toFixed(1)}s / ${totalDuration}s`)
  }
} finally {
  await browser.close()
}
const list = resolve(framesDir, 'frames.ffconcat')
const quoted = (file) => file.replaceAll("'", "'\\''")
writeFileSync(list, frames.map(({ file, count }) => `file '${quoted(file)}'\nduration ${(count / 30).toFixed(9)}`).join('\n') + `\nfile '${quoted(frames.at(-1).file)}'\n`)
const output = resolve(directory, 'renders', `${video}-es.intermediate.mp4`)
const encoded = spawnSync('ffmpeg', [
  '-nostdin', '-y', '-hide_banner', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', list,
  '-vf', 'fps=30', '-t', String(totalDuration), '-an', '-c:v', 'libx264', '-preset', 'veryfast',
  '-crf', '18', '-threads', '2', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', output,
], { stdio: 'inherit' })
if (encoded.status !== 0) process.exit(encoded.status ?? 1)
writeFileSync(resolve(directory, 'renders', 'capture.json'), JSON.stringify({ fps: 30, totalDuration, capturedFrames: frames.length, outputFrames: Math.round(totalDuration * 30) }, null, 2) + '\n')
console.log(`${video}: ${frames.length} captured frames, ${Math.round(totalDuration * 30)} output frames`)
