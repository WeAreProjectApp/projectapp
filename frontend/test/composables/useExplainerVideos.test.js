import { ref } from 'vue'

import {
  explainerVideoFor,
  formatExplainerDuration,
  useExplainerVideo,
} from '../../composables/useExplainerVideos'

describe('useExplainerVideos', () => {
  it.each(['additional-modules', 'financing'])('keeps the Spanish %s render at 45 seconds', (id) => {
    // Fails if an existing explainer render is accidentally replaced by the proposal timing.
    expect(explainerVideoFor(id, 'es')).toMatchObject({
      id,
      language: 'es',
      durationSeconds: 45,
      width: 1920,
      height: 1080,
    })
  })

  it('describes the Spanish proposal render with its production duration', () => {
    // Fails if the public proposal card points to a missing, malformed, or wrongly timed render.
    const descriptor = explainerVideoFor('proposal', 'es')

    expect(descriptor).toMatchObject({
      id: 'proposal',
      language: 'es',
      durationSeconds: 58.2,
      width: 1920,
      height: 1080,
    })
    expect(descriptor.src).not.toBe('')
    expect(descriptor.poster).not.toBe('')
  })

  it('resolves only the known Spanish proposal video', () => {
    // Fails if the Spanish-only proposal video is offered in English or an unregistered surface.
    expect(explainerVideoFor('proposal', 'es')).toMatchObject({ id: 'proposal', language: 'es' })
    expect(explainerVideoFor('proposal', 'en')).toBeNull()
    expect(explainerVideoFor('unknown', 'es')).toBeNull()
    expect(explainerVideoFor('financing', 'en')).toBeNull()
  })

  it('reacts to language changes through the composable', () => {
    const language = ref('es')
    const explainer = useExplainerVideo('additional-modules', language)

    expect(explainer.value?.id).toBe('additional-modules')

    language.value = 'en'
    expect(explainer.value).toBeNull()
  })

  it('formats durations as minutes and seconds', () => {
    expect(formatExplainerDuration(70)).toBe('1:10')
    expect(formatExplainerDuration(72)).toBe('1:12')
    expect(formatExplainerDuration(0)).toBe('0:00')
  })
})
