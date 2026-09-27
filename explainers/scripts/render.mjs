#!/usr/bin/env node
/**
 * Render final de un video: HyperFrames produce un intermedio casi sin pérdida
 * (la composición es muda) y ffmpeg hace UNA sola codificación final mezclando
 * la música y, si se pide, la narración. Agregar o quitar narración nunca
 * vuelve a renderizar el video.
 *
 *   node scripts/render.mjs --video financing --lang es [--with-narration] [--draft] [--crf 25] [--budget-mb 12]
 */
import { spawnSync } from 'node:child_process'
import { existsSync, mkdirSync, statSync, readFileSync } from 'node:fs'
import { pathToFileURL } from 'node:url'
import { narrationFingerprint, narrationSettings } from './lib/narration.mjs'
import { resolve } from 'node:path'

import { EDITION, EDITION_ROOT, AUDIO_DIR, HYPERFRAMES_BIN, SHARED_DIR, assertExists, parseArgs, requireLanguage, requireVideo, videoDir } from './lib/paths.mjs'
import { readSchedule } from './lib/schedule.mjs'

const options = parseArgs(process.argv.slice(2), {
  defaults: { crf: '25', 'budget-mb': '12', 'music-volume': '0.32', workers: '1', priority: '15' },
  flags: ['with-narration', 'draft', 'skip-render'],
})
const video = requireVideo(options)
const language = requireLanguage(options)
const priority = Number(options.priority)
if (!Number.isInteger(priority) || priority < 0 || priority > 19) throw new Error('--priority must be an integer from 0 to 19')
const projectDir = videoDir(video)
const rendersDir = resolve(projectDir, 'renders')
mkdirSync(rendersDir, { recursive: true })

const intermediate = resolve(rendersDir, `${video}-${language}.intermediate.mp4`)
const output = resolve(rendersDir, `${video}-${language}${options.draft ? '.draft' : ''}.mp4`)
const music = resolve(EDITION === 'v1' ? SHARED_DIR : resolve(EDITION_ROOT, 'shared'), 'music', 'bed.mp3')
const narration = resolve(AUDIO_DIR, `${video}-narration-${language}.wav`)
const schedule = readSchedule(video)
const { totalDuration } = schedule

if (EDITION === 'brag-v2') {
  if (!options['with-narration']) throw new Error('brag-v2 requires --with-narration')
  assertExists(music)
  assertExists(narration)
  assertExists(resolve(rendersDir, 'poster.png'), 'Run poster before rendering brag-v2.')
  const { default: script } = await import(pathToFileURL(resolve(projectDir, `script.${language}.js`)).href)
  const metadata = JSON.parse(readFileSync(assertExists(resolve(AUDIO_DIR, `${video}-narration-${language}.json`), 'Generate narration first.'), 'utf8'))
  const settings = narrationSettings(options, script.narrationConfig || metadata, language)
  if (metadata.fingerprint !== narrationFingerprint(script, schedule, settings)) throw new Error('Narration is stale: regenerate it after script, timing or voice changes.')
}

function run(command, args, extra = {}) {
  const pretty = [command, ...args].map((part) => (/\s/.test(part) ? JSON.stringify(part) : part)).join(' ')
  console.log(`\n$ ${pretty}\n`)
  const result = spawnSync(command, args, { stdio: 'inherit', ...extra })
  if (result.status !== 0) {
    console.error(`${command} terminó con código ${result.status}`)
    process.exit(result.status ?? 1)
  }
}

function runNode(script, args) {
  run(process.execPath, [new URL(script, import.meta.url).pathname, ...args])
}

runNode('./sync-assets.mjs', ['--video', video, '--edition', EDITION])
runNode('./stage.mjs', ['--video', video, '--lang', language, '--edition', EDITION])

if (!options['skip-render']) {
  assertExists(HYPERFRAMES_BIN, 'Corré npm install en explainers/.')
  const renderArgs = [
    'render', '.',
    '-o', intermediate,
    '--fps', '30',
    '--quality', options.draft ? 'draft' : 'high',
    '--workers', String(options.workers),
    '--strict',
  ]
  if (!options.draft) renderArgs.push('--crf', '18')
  run('nice', ['-n', String(priority), HYPERFRAMES_BIN, ...renderArgs], {
    cwd: projectDir,
    env: { ...process.env, HYPERFRAMES_NO_TELEMETRY: '1', HYPERFRAMES_NO_UPDATE_CHECK: '1' },
  })
}
assertExists(intermediate, 'El render intermedio no se generó.')

const hasMusic = existsSync(music)
if (EDITION === 'brag-v2' && (!hasMusic || !options['with-narration'])) throw new Error('brag-v2 requires music and --with-narration')
const hasNarration = Boolean(options['with-narration']) && existsSync(narration)
if (options['with-narration'] && !hasNarration) {
  console.error(`Se pidió narración pero no existe ${narration}. Generala con: node scripts/build-narration.mjs --video ${video} --lang ${language} --voice <id>`)
  process.exit(1)
}
if (!hasMusic) console.warn(`Aviso: no hay ${music}; el video saldrá ${hasNarration ? 'sólo con narración' : 'sin audio'}.`)

const inputs = ['-i', intermediate]
const filters = []
let audioLabel = null
const fadeStart = Math.max(0, totalDuration - 4).toFixed(2)

if (hasMusic && hasNarration) {
  inputs.push('-stream_loop', '-1', '-i', music, '-i', narration)
  filters.push(
    `[1:a]atrim=0:${totalDuration},asetpts=PTS-STARTPTS,volume=${options['music-volume']}${EDITION === 'brag-v2' ? `,afade=t=out:st=${fadeStart}:d=4` : ''}[music]`,
    '[2:a]aformat=sample_rates=48000:channel_layouts=stereo,apad[voice]',
    '[music][voice]sidechaincompress=threshold=0.03:ratio=8:attack=25:release=450:makeup=1[ducked]',
    '[ducked][2:a]amix=inputs=2:duration=first:normalize=0[mix]',
    `[mix]loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=out:st=${fadeStart}:d=4[aout]`,
  )
  if (EDITION === 'brag-v2' && video !== 'proposal') {
    inputs.push('-i', assertExists(resolve(EDITION_ROOT, 'shared', 'sfx', 'click.ogg')))
    filters.pop()
    const cueOffsets = video === 'additional-modules' ? [['scene-2', 2], ['scene-4', 2], ['scene-5', 2.2]] : [['scene-2', 2], ['scene-3', 2.2], ['scene-5', 1.2]]
    const cues = cueOffsets.map(([id, offset]) => Math.round((schedule.scenes.find((scene) => scene.id === id).start + offset) * 1000))
    filters.push('[3:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=0.1,lowpass=f=4500,asplit=3[s0][s1][s2]')
    cues.forEach((cue, index) => filters.push(`[s${index}]adelay=${cue}|${cue}[fx${index}]`))
    filters.push('[mix][fx0][fx1][fx2]amix=inputs=4:duration=first:normalize=0[scored]')
    // Leave headroom for inter-sample peaks introduced by AAC encoding.
    filters.push(`[scored]loudnorm=I=-16:TP=-2.5:LRA=11,afade=t=out:st=${totalDuration - 0.5}:d=0.5[aout]`)
  }
  if (EDITION === 'brag-v2' && video === 'proposal') {
    filters.pop()
    filters.push(`[mix]loudnorm=I=-16:TP=-2.5:LRA=11,afade=t=out:st=${totalDuration - 0.5}:d=0.5[aout]`)
  }
  audioLabel = '[aout]'
} else if (hasMusic) {
  inputs.push('-stream_loop', '-1', '-i', music)
  filters.push(
    `[1:a]atrim=0:${totalDuration},asetpts=PTS-STARTPTS,volume=${options['music-volume']},loudnorm=I=-18:TP=-1.5:LRA=11,afade=t=out:st=${fadeStart}:d=4[aout]`,
  )
  audioLabel = '[aout]'
} else if (hasNarration) {
  inputs.push('-i', narration)
  filters.push(`[1:a]loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=out:st=${fadeStart}:d=2[aout]`)
  audioLabel = '[aout]'
}

let videoLabel = '0:v:0'
if (EDITION === 'brag-v2') {
  const posterIndex = inputs.filter((part) => part === '-i').length
  inputs.push('-i', assertExists(resolve(rendersDir, 'poster.png'), 'Run poster before render for brag-v2.'))
  filters.push(`[0:v][${posterIndex}:v]overlay=enable='eq(n,0)'[vout]`)
  videoLabel = '[vout]'
}

const ffmpegArgs = ['-y', '-hide_banner', '-loglevel', 'error', '-stats', ...inputs]
if (audioLabel) {
  ffmpegArgs.push('-filter_complex', filters.join(';'), '-map', videoLabel, '-map', audioLabel)
  ffmpegArgs.push('-c:a', 'aac', '-b:a', '96k', '-ar', '48000', '-ac', '2')
} else {
  ffmpegArgs.push('-map', '0:v:0', '-an')
}
ffmpegArgs.push(
  '-c:v', 'libx264', '-preset', options.draft ? 'veryfast' : 'slow', '-crf', String(options.draft ? 28 : options.crf),
  '-threads', '2', '-tune', 'animation', '-profile:v', 'high', '-level', '4.1', '-pix_fmt', 'yuv420p',
  '-movflags', '+faststart', '-t', String(totalDuration), output,
)
run('nice', ['-n', String(priority), 'ffmpeg', ...ffmpegArgs])

const sizeMb = statSync(output).size / (1024 * 1024)
console.log(`\n${output}\n${sizeMb.toFixed(2)} MB · ${totalDuration}s · audio: ${hasMusic ? 'música' : ''}${hasMusic && hasNarration ? ' + ' : ''}${hasNarration ? 'narración' : ''}${!hasMusic && !hasNarration ? 'ninguno' : ''}`)

const budget = Number(options['budget-mb'])
if (!options.draft && sizeMb > budget) {
  console.error(`Excede el presupuesto de ${budget} MB. Reintentá con --crf ${Number(options.crf) + 2} --skip-render (reusa el intermedio).`)
  process.exit(3)
}
