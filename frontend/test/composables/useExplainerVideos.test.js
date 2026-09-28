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

  it('uses the uploaded resource before the language-specific bundled fallback', () => {
    // Fails if a video uploaded from the panel or MCP is ignored for English surfaces.
    const resource = ref({
      mode: 'uploaded',
      video: { src: '/api/video-resources/id/1/video/' },
    })
    const explainer = useExplainerVideo('proposal', ref('en'), resource)

    expect(explainer.value?.src).toBe('/api/video-resources/id/1/video/')
  })

  it('hides a resource explicitly marked as removed', () => {
    // Fails if removing an uploaded resource accidentally brings back the bundled video.
    // quality: allow-negation-only (the public contract for an explicitly removed resource is null)
    const explainer = useExplainerVideo('proposal', ref('es'), ref({ mode: 'none' }))

    expect(explainer.value).toBeNull()
  })

  it('keeps the bundled proposal descriptor when no resource override exists', () => {
    // Fails if ordinary proposal pages lose their published fallback without an override.
    const explainer = useExplainerVideo('proposal', ref('es'))

    expect(explainer.value).toMatchObject({
      id: 'proposal',
      language: 'es',
      durationSeconds: 58.2,
      width: 1920,
      height: 1080,
    })
  })

  it('formats durations as minutes and seconds', () => {
    expect(formatExplainerDuration(70)).toBe('1:10')
    expect(formatExplainerDuration(72)).toBe('1:12')
    expect(formatExplainerDuration(0)).toBe('0:00')
  })
})
