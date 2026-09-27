import test from 'node:test'
import assert from 'node:assert/strict'
import { narrationKey, narrationSettings, assertNarrationFits, captionSchedule, narrationFingerprint } from '../scripts/lib/narration.mjs'

const recording = { text: 'Construimos hoy.', voice: 'ef_dora', language: 'es', speed: 1.1 }

test('a revised sentence selects a new cached recording', () => {
  assert.notEqual(narrationKey(recording), narrationKey({ ...recording, text: 'Crecemos contigo.' }))
})
test('a voice change selects a new cached recording', () => {
  assert.notEqual(narrationKey(recording), narrationKey({ ...recording, voice: 'em_alex' }))
})
test('a speed change selects a new cached recording', () => {
  assert.notEqual(narrationKey(recording), narrationKey({ ...recording, speed: 1 }))
})
test('a narration that overruns its scene stops production', () => {
  assert.throws(() => assertNarrationFits(4.2, 3.5, 'payments'), /exceeds payments/)
})
test('an unreadable narration cannot enter the mix', () => {
  assert.throws(() => assertNarrationFits(NaN, 5, 'intro'), /Invalid narration duration/)
})
test('a narration fitting the scene can enter the mix', () => {
  assert.doesNotThrow(() => assertNarrationFits(3.1, 3.5, 'intro'))
})
test('captions cover the measured voice interval without a gap', () => {
  const cues = captionSchedule(['Construimos hoy.', 'Crecemos contigo.'], 4.2, 6)
  assert.deepEqual(cues, [
    { text: 'Construimos hoy.', start: 4.2, end: 7.2 },
    { text: 'Crecemos contigo.', start: 7.2, end: 10.2 },
  ])
})
test('retiming a scene invalidates the mixed narration', () => {
  const script = { scenes: { intro: { narration: 'Construimos hoy.' } } }
  assert.notEqual(narrationFingerprint(script, { start: 0 }), narrationFingerprint(script, { start: 4 }))
})

test('a provider change selects a new cached recording', () => {
  assert.notEqual(narrationKey(recording), narrationKey({ ...recording, provider: 'edge' }))
})

test('a locale change selects a new cached recording', () => {
  assert.notEqual(narrationKey(recording), narrationKey({ ...recording, locale: 'es-CO' }))
})

test('a revised voice setting invalidates the mixed narration', () => {
  const script = { scenes: { intro: { narration: 'Construimos hoy.' } } }
  const settings = { provider: 'edge', voice: 'es-CO-SalomeNeural', speed: 1, lead: 0.2 }
  assert.notEqual(narrationFingerprint(script, {}, settings), narrationFingerprint(script, {}, { ...settings, voice: 'es-CO-GonzaloNeural' }))
})

test('legacy narration retains the local provider', () => {
  assert.deepEqual(narrationSettings({ voice: 'ef_dora' }), {
    provider: 'kokoro', voice: 'ef_dora', locale: 'es', speed: 1, lead: 0.6,
  })
})

test('the authored voice config supplies the production defaults', () => {
  const config = { provider: 'edge', voice: 'es-CO-SalomeNeural', locale: 'es-CO', speed: 1, lead: 0.2 }
  assert.deepEqual(narrationSettings({}, config), config)
})

test('an unsupported provider cannot silently select a fallback', () => {
  assert.throws(() => narrationSettings({ provider: 'unknown', voice: 'ef_dora' }), /Unknown narration provider/)
})

test('a voice from another locale is rejected', () => {
  assert.throws(() => narrationSettings({ provider: 'edge', voice: 'es-ES-ElviraNeural', locale: 'es-CO' }), /must match/)
})

test('moving the voice lead invalidates the mixed narration', () => {
  const script = { scenes: { intro: { narration: 'Construimos hoy.' } } }
  assert.notEqual(narrationFingerprint(script, {}, { lead: 0.2 }), narrationFingerprint(script, {}, { lead: 0.6 }))
})
