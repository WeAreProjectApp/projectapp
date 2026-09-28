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

function mountCard(props = {}) {
  return mount(ExplainerVideoCard, {
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
}

describe('ExplainerVideoCard', () => {
  let playSpy

  beforeEach(() => {
    playSpy = jest.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined)
  })

  afterEach(() => {
    playSpy.mockRestore()
  })

  it('shows the poster with an accessible play control and the duration', () => {
    const wrapper = mountCard()

    const play = wrapper.get('[data-testid="financing-explainer-play"]')
    expect(play.attributes('aria-label')).toBe('financing.explainerPlayAria:financing.explainerTitle')
    expect(play.get('img').attributes('src')).toBe(video.poster)
    expect(wrapper.text()).toContain('financing.explainerDuration:1:12')
    expect(wrapper.find('video').exists()).toBe(false)
    expect(wrapper.get('[data-testid="financing-explainer-card"]').attributes('data-state')).toBe('idle')
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
