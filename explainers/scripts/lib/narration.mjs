import { createHash } from 'node:crypto'

export function narrationSettings(options, authored = {}, language = 'es') {
  const settings = { provider: 'kokoro', locale: language, speed: 1, lead: 0.6 }
  for (const key of ['provider', 'voice', 'locale', 'speed', 'lead']) {
    if (authored[key] !== undefined) settings[key] = authored[key]
    if (options[key] !== undefined) settings[key] = options[key]
  }
  settings.speed = Number(settings.speed)
  settings.lead = Number(settings.lead)
  if (!['kokoro', 'edge'].includes(settings.provider)) throw new Error('Unknown narration provider')
  if (!settings.voice) throw new Error('Falta --voice <id> o narrationConfig.voice en el guion')
  if (!Number.isFinite(settings.speed) || settings.speed <= 0) throw new Error('Invalid --speed')
  if (!Number.isFinite(settings.lead) || settings.lead < 0) throw new Error('Invalid --lead')
  if (settings.provider === 'edge' && !settings.voice.startsWith(`${settings.locale}-`)) {
    throw new Error('The Edge voice must match the requested locale')
  }
  return settings
}

export function narrationKey({ text, voice, language, speed, provider = 'kokoro', locale = language }) {
  return createHash('sha256').update(JSON.stringify({ text, voice, language, speed: Number(speed), provider, locale })).digest('hex').slice(0, 20)
}

export function assertNarrationFits(duration, available, sceneId) {
  if (!Number.isFinite(duration) || duration <= 0) throw new Error(`Invalid narration duration: ${sceneId}`)
  if (duration > available) throw new Error(`Narration exceeds ${sceneId}: ${duration.toFixed(2)}s > ${available.toFixed(2)}s; shorten the script or extend the scene.`)
}

export function captionSchedule(captions, start, duration) {
  const weights = captions.map((text) => text.trim().split(/\s+/).length)
  const total = weights.reduce((sum, weight) => sum + weight, 0)
  let cursor = start
  return captions.map((text, index) => {
    const span = duration * weights[index] / total
    const cue = { text, start: cursor, end: cursor + span }
    cursor += span
    return cue
  })
}

export function narrationFingerprint(script, schedule, settings = {}) {
  return createHash('sha256').update(JSON.stringify({ scenes: script.scenes, schedule, settings })).digest('hex')
}
