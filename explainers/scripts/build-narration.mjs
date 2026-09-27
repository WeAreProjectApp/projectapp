#!/usr/bin/env node
/** Offline narration production (Kokoro or Edge); checked before mixing. */
import { spawnSync } from 'node:child_process'
import { existsSync, mkdirSync, writeFileSync, renameSync } from 'node:fs'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { EDITION, AUDIO_DIR, HYPERFRAMES_BIN, TTS_DIR, assertExists, parseArgs, requireLanguage, requireVideo, videoDir } from './lib/paths.mjs'
import { narrationKey, narrationSettings, assertNarrationFits, captionSchedule, narrationFingerprint } from './lib/narration.mjs'
import { readSchedule } from './lib/schedule.mjs'

const options = parseArgs(process.argv.slice(2))
const video = requireVideo(options)
const language = requireLanguage(options)
const projectDir = videoDir(video)
const { default: script } = await import(pathToFileURL(assertExists(resolve(projectDir, `script.${language}.js`))).href)
const settings = narrationSettings(options, script.narrationConfig, language)
const { provider, voice, locale, speed, lead } = settings
if (provider === 'edge') {
  const listing = spawnSync('edge-tts', ['--list-voices'], { encoding: 'utf8', timeout: 60_000 })
  if (listing.status !== 0 || !listing.stdout.split(/\r?\n/).some((line) => line.split(/\s+/)[0] === voice)) {
    throw new Error(`Edge voice unavailable: ${voice}. Check edge-tts on PATH and network access; no voice fallback is used.`)
  }
}
const schedule = readSchedule(video)
const { scenes } = schedule
const ttsDir = resolve(TTS_DIR, video, language)
mkdirSync(ttsDir, { recursive: true })
mkdirSync(AUDIO_DIR, { recursive: true })
function run(command, args, extra = {}) {
  const result = spawnSync(command, args, {
    stdio: 'inherit', env: { ...process.env, HYPERFRAMES_NO_TELEMETRY: '1', HYPERFRAMES_NO_UPDATE_CHECK: '1' }, ...extra,
  })
  if (result.status !== 0) process.exit(result.status ?? 1)
}
function durationOf(file) {
  const result = spawnSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', file], { encoding: 'utf8' })
  if (result.status !== 0) throw new Error(`Cannot read narration: ${file}`)
  return Number(result.stdout.trim())
}
function synthesize(text, file) {
  const temporary = file.replace(/\.wav$/, '.partial.wav')
  if (provider === 'edge') {
    const rate = Math.round((speed - 1) * 100)
    const mp3 = file.replace(/\.wav$/, '.mp3')
    run('edge-tts', ['--voice', voice, `--rate=${rate >= 0 ? '+' : ''}${rate}%`, '--text', text, '--write-media', mp3], { timeout: 60_000 })
    run('ffmpeg', ['-y', '-hide_banner', '-loglevel', 'error', '-i', mp3, '-ar', '48000', '-ac', '2', temporary])
  } else {
    run(HYPERFRAMES_BIN, ['tts', text, '--lang', locale, '--voice', voice, '--speed', String(speed), '-o', temporary])
  }
  assertNarrationFits(durationOf(temporary), Infinity, file)
  renameSync(temporary, file)
}
const clips = []
const captions = []
const overflows = []
for (const scene of scenes) {
  const authored = script.scenes[scene.id]
  if (!authored?.narration) continue
  const segments = authored.voiceSegments || [{ at: 0, text: authored.narration, captions: authored.captions }]
  for (const [index, segment] of segments.entries()) {
    const key = narrationKey({ text: segment.text, language, ...settings })
    const file = resolve(ttsDir, `${scene.id}-${index}-${key}.wav`)
    if (!existsSync(file)) synthesize(segment.text, file)
    const duration = durationOf(file)
    const available = (segments[index + 1]?.at ?? scene.duration) - segment.at - lead - 0.3
    try {
      assertNarrationFits(duration, available, `${scene.id}/${index}`)
    } catch (error) {
      overflows.push(error.message)
    }
    const offset = scene.start + segment.at + lead
    console.log(`${scene.id}/${index}: ${duration.toFixed(2)}s / ${available.toFixed(2)}s`)
    clips.push({ file, offsetMs: Math.round(offset * 1000) })
    if (EDITION === 'brag-v2') captions.push(...captionSchedule(segment.captions || [segment.text], offset, duration))
  }
}
if (!clips.length) throw new Error('El guion no tiene narración')
if (overflows.length) throw new Error(overflows.join('\n'))
const inputs = clips.flatMap((clip) => ['-i', clip.file])
const delayed = clips.map((clip, index) => `[${index}:a]aformat=sample_rates=48000:channel_layouts=stereo,adelay=${clip.offsetMs}|${clip.offsetMs}[d${index}]`)
const mix = `${clips.map((_, index) => `[d${index}]`).join('')}amix=inputs=${clips.length}:duration=longest:normalize=0[out]`
const output = resolve(AUDIO_DIR, `${video}-narration-${language}.wav`)
run('ffmpeg', ['-y', '-hide_banner', '-loglevel', 'error', ...inputs, '-filter_complex', [...delayed, mix].join(';'), '-map', '[out]', output])
if (EDITION === 'brag-v2') writeFileSync(resolve(projectDir, `captions.${language}.json`), JSON.stringify(captions, null, 2) + '\n')
console.log(`Narración: ${output} (${clips.length} segmentos, ${voice})`)

if (EDITION === 'brag-v2') writeFileSync(resolve(AUDIO_DIR, `${video}-narration-${language}.json`), JSON.stringify({ fingerprint: narrationFingerprint(script, schedule, settings), ...settings }, null, 2) + '\n')
