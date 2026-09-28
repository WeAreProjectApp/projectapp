import { flushPromises, mount } from '@vue/test-utils'

import ExplainerVideoCard from '../../components/ExplainerVideoCard.vue'

global.useI18n = jest.fn(() => ({
  t: (key, params = {}) => `${key}${params.title ? `:${params.title}` : ''}${params.time ? `:${params.time}` : ''}`,
}))

const video = {
  id: 'financing',
  language: 'es',
  src: '/_nuxt/financing-es.abc123.mp4',
  poster: '/_nuxt/financing-es.abc123.webp',
  durationSeconds: 72,
  width: 1920,
  height: 1080,
}
const wrappers = []

function mountCard(props = {}) {
  const wrapper = mount(ExplainerVideoCard, {
    props: {
      video,
      i18nNamespace: 'financing',
      testId: 'financing-explainer',
      ...props,
    },
    global: {
      stubs: {
        NuxtLink: { template: '<a><slot /></a>' },
      },
    },
  })
  wrappers.push(wrapper)
  return wrapper
}

describe('ExplainerVideoCard', () => {
  let playSpy
  let pauseSpy
  let visibilitySpy

  beforeEach(() => {
    playSpy = jest.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined)
    pauseSpy = jest.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {})
    jest.spyOn(document, 'hasFocus').mockReturnValue(true)
    visibilitySpy = jest.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
  })

  afterEach(() => {
    wrappers.splice(0).forEach(wrapper => wrapper.unmount())
    jest.restoreAllMocks()
  })

  it('shows the poster with an accessible play control and the duration', () => {
    const wrapper = mountCard()

    const play = wrapper.get('[data-testid="financing-explainer-play"]')
    expect(play.attributes('aria-label')).toBe('financing.explainerPlayAria:financing.explainerTitle')
    expect(play.get('img').attributes('src')).toBe(video.poster)
    expect(wrapper.text()).toContain('financing.explainerDuration:1:12')
    expect(wrapper.find('video').exists()).toBe(false)
    expect(wrapper.get('[data-testid="financing-explainer-card"]').attributes('data-state')).toBe('idle')
    expect(playSpy).not.toHaveBeenCalled()
  })

  it('swaps the poster for a native player with sound after the play click', async () => {
    const wrapper = mountCard()

    await wrapper.get('[data-testid="financing-explainer-play"]').trigger('click')
    await flushPromises()

    const player = wrapper.get('[data-testid="financing-explainer-player"]')
    expect(player.attributes('src')).toBe(video.src)
    expect(player.attributes('controls')).toBeDefined()
    expect(player.attributes('playsinline')).toBeDefined()
    expect(player.element.muted).toBe(false)
    expect(playSpy).toHaveBeenCalledTimes(1)
    expect(wrapper.find('[data-testid="financing-explainer-play"]').exists()).toBe(false)
    expect(wrapper.emitted('play')).toHaveLength(1)
  })

  it('keeps the player and offers the file when the browser cannot play it', async () => {
    const wrapper = mountCard()
    await wrapper.get('[data-testid="financing-explainer-play"]').trigger('click')
    await flushPromises()

    await wrapper.get('[data-testid="financing-explainer-player"]').trigger('error')

    expect(wrapper.get('[data-testid="financing-explainer-card"]').attributes('data-state')).toBe('error')
    expect(wrapper.find('[data-testid="financing-explainer-player"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="financing-explainer-error"]').text()).toContain('financing.explainerError')
    expect(wrapper.get('[data-testid="financing-explainer-open"]').attributes('href')).toBe(video.src)
    expect(wrapper.emitted('error')).toHaveLength(1)
  })

  it('returns to the poster when the video ends', async () => {
    const wrapper = mountCard()
    await wrapper.get('[data-testid="financing-explainer-play"]').trigger('click')
    await flushPromises()

    await wrapper.get('[data-testid="financing-explainer-player"]').trigger('ended')

    expect(wrapper.find('[data-testid="financing-explainer-player"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="financing-explainer-play"]').exists()).toBe(true)
  })

  it('uses the panel copy in the compact variant', () => {
    const wrapper = mountCard({ variant: 'compact', i18nNamespace: 'additionalModules', testId: 'additional-modules-explainer' })

    const card = wrapper.get('[data-testid="additional-modules-explainer-card"]')
    expect(card.attributes('data-variant')).toBe('compact')
    expect(wrapper.get('h2').text()).toBe('additionalModules.explainerPanelTitle')
    expect(wrapper.text()).toContain('additionalModules.explainerPanelDescription')
  })

  it('keeps playback paused after returning to the window', async () => {
    const wrapper = mountCard()
    await wrapper.get('[data-testid="financing-explainer-play"]').trigger('click')
    await flushPromises()

    window.dispatchEvent(new Event('blur'))
    window.dispatchEvent(new Event('focus'))

    expect(pauseSpy).toHaveBeenCalledTimes(1)
    expect(playSpy).toHaveBeenCalledTimes(1)
    expect(wrapper.get('[data-testid="financing-explainer-player"]').element.autoplay).toBe(false)
  })

  it('keeps playback paused after returning to the tab', async () => {
    const wrapper = mountCard()
    await wrapper.get('[data-testid="financing-explainer-play"]').trigger('click')
    await flushPromises()

    visibilitySpy.mockReturnValue('hidden')
    document.dispatchEvent(new Event('visibilitychange'))
    visibilitySpy.mockReturnValue('visible')
    document.dispatchEvent(new Event('visibilitychange'))

    expect(pauseSpy).toHaveBeenCalledTimes(1)
    expect(playSpy).toHaveBeenCalledTimes(1)
  })

  it('keeps playback paused after restoring a page', async () => {
    const wrapper = mountCard()
    await wrapper.get('[data-testid="financing-explainer-play"]').trigger('click')
    await flushPromises()

    window.dispatchEvent(new Event('pagehide'))
    window.dispatchEvent(new Event('pageshow'))

    expect(pauseSpy).toHaveBeenCalledTimes(1)
    expect(playSpy).toHaveBeenCalledTimes(1)
  })

  it('cancels a start when focus leaves before the player mounts', async () => {
    const wrapper = mountCard()

    const click = wrapper.get('[data-testid="financing-explainer-play"]').trigger('click')
    window.dispatchEvent(new Event('blur'))
    await click
    await flushPromises()
    window.dispatchEvent(new Event('focus'))

    expect(playSpy).not.toHaveBeenCalled()
    expect(wrapper.get('[data-testid="financing-explainer-player"]').element.autoplay).toBe(false)
  })

  it('pauses a delayed start invalidated by a window switch', async () => {
    let finishLoading
    playSpy.mockReturnValue(new Promise(resolve => { finishLoading = resolve }))
    const wrapper = mountCard()
    await wrapper.get('[data-testid="financing-explainer-play"]').trigger('click')

    window.dispatchEvent(new Event('blur'))
    window.dispatchEvent(new Event('focus'))
    pauseSpy.mockClear()
    finishLoading()
    await flushPromises()

    expect(pauseSpy).toHaveBeenCalledTimes(1)
    expect(playSpy).toHaveBeenCalledTimes(1)
  })

  it('rejects a playback event while the tab is hidden', async () => {
    const wrapper = mountCard()
    await wrapper.get('[data-testid="financing-explainer-play"]').trigger('click')
    await flushPromises()
    visibilitySpy.mockReturnValue('hidden')

    await wrapper.get('[data-testid="financing-explainer-player"]').trigger('play')

    expect(pauseSpy).toHaveBeenCalledTimes(1)
  })

  it('requires a new click after changing the video source', async () => {
    const wrapper = mountCard()
    await wrapper.get('[data-testid="financing-explainer-play"]').trigger('click')
    await flushPromises()

    await wrapper.setProps({ video: { ...video, src: '/replacement.mp4' } })

    expect(pauseSpy).toHaveBeenCalledTimes(1)
    expect(wrapper.find('[data-testid="financing-explainer-player"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="financing-explainer-play"]').exists()).toBe(true)
    expect(playSpy).toHaveBeenCalledTimes(1)
  })

  it('releases window listeners when the player is removed', async () => {
    const wrapper = mountCard()
    await wrapper.get('[data-testid="financing-explainer-play"]').trigger('click')
    await flushPromises()

    wrapper.unmount()
    wrappers.splice(wrappers.indexOf(wrapper), 1)
    window.dispatchEvent(new Event('blur'))
    window.dispatchEvent(new Event('pagehide'))
    visibilitySpy.mockReturnValue('hidden')
    document.dispatchEvent(new Event('visibilitychange'))

    expect(pauseSpy).toHaveBeenCalledTimes(1)
  })

  it('keeps native controls available after a rejected play request', async () => {
    playSpy.mockRejectedValue(new DOMException('Playback interrupted', 'AbortError'))
    const wrapper = mountCard()

    await wrapper.get('[data-testid="financing-explainer-play"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="financing-explainer-player"]').element.controls).toBe(true)
    expect(wrapper.find('[data-testid="financing-explainer-error"]').exists()).toBe(false)
  })

  it('hides the subtitle assurance for an uploaded video', () => {
    // Fails if a third-party upload is advertised as having the bundled video's guaranteed subtitles.
    const wrapper = mountCard({
      video: { ...video, source: 'uploaded', src: '/api/video-resources/id/11/video/' },
    })

    expect(wrapper.text()).not.toContain('financing.explainerNoAudioNote')
    expect(wrapper.get('[data-testid="financing-explainer-play"]').attributes('aria-label'))
      .toBe('financing.explainerPlayAria:financing.explainerTitle')
  })
})
