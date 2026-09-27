import { ref } from 'vue'

import {
  explainerVideoFor,
  formatExplainerDuration,
  useExplainerVideo,
} from '../../composables/useExplainerVideos'

describe('useExplainerVideos', () => {
  it.each([
    ['additional-modules', 60],
    ['financing', 60],
  ])('describes the published %s video', (id, durationSeconds) => {
    const descriptor = explainerVideoFor(id, 'es')
    expect(descriptor).toMatchObject({ id, language: 'es', width: 1920, height: 1080 })
    expect(descriptor.src).toBeTruthy()
    expect(descriptor.poster).toBeTruthy()
    expect(descriptor.durationSeconds).toBe(durationSeconds)
  })

  it('only resolves languages that have a render and ids from the registry', () => {
    expect(explainerVideoFor('financing', 'es')).toMatchObject({ id: 'financing', language: 'es' })
    expect(explainerVideoFor('financing', 'en')).toBeNull()
    expect(explainerVideoFor('proposal', 'es')).toBeNull()
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
