/* Seek-safe GSAP timeline. CSS describes the settled frame; all motion is on
 * this paused timeline, with no timers, random state or real user interaction. */
(() => {
  const timeline = gsap.timeline({ paused: true })
  const scenes = [...document.querySelectorAll('.scene')]
  scenes.forEach((scene, index) => {
    const start = Number(scene.dataset.start)
    const duration = Number(scene.dataset.duration)
    timeline.set(scene, { autoAlpha: 0 }, 0)
    timeline.set(scene, { autoAlpha: 1 }, start)
    const targets = [...scene.querySelectorAll('.reveal')]
    // The opening is already readable at frame zero: the poster must not flash
    // into an empty entrance frame when playback starts.
    if (index === 0) {
      timeline.set(targets, { y: 0, opacity: 1 }, 0)
      timeline.set(scene.querySelector('.masthead p'), { x: 0, opacity: 1 }, 0)
    } else {
      timeline.fromTo(targets, { y: 34, opacity: 0 }, {
        y: 0, opacity: 1, duration: 0.55, stagger: 0.08, ease: 'power3.out',
      }, start + 0.08)
      timeline.fromTo(scene.querySelector('.masthead p'), { x: 18, opacity: 0 }, {
        x: 0, opacity: 1, duration: 0.45, ease: 'power2.out',
      }, start + 0.05)
    }
    if (index < scenes.length - 1) {
      timeline.to(scene.querySelector('.body'), { y: -18, opacity: 0, duration: 0.25, ease: 'power2.in' }, start + duration - 0.25)
      timeline.set(scene, { autoAlpha: 0 }, start + duration)
    }
    // Actual catalogue/partnership UI, with a small simulated tap on a card.
    const browser = scene.querySelector('.browser')
    if (browser) {
      browser.style.position = 'relative'
      const cursor = document.createElement('div')
      cursor.className = 'cursor'
      cursor.dataset.layoutIgnore = ''
      cursor.innerHTML = '<svg viewBox="0 0 24 24" fill="currentColor" stroke="white" stroke-width="1.5"><path d="m4 3 15 10-7 1-3 7Z" /></svg>'
      browser.appendChild(cursor)
      const target = scene.querySelector('.catalog-card, .detail-row')
      const x = Math.min(browser.clientWidth - 80, 250)
      const y = Math.min(browser.clientHeight - 90, 250)
      timeline.fromTo(cursor, { x: x + 180, y: y + 120, autoAlpha: 0 }, { x, y, autoAlpha: 1, duration: 0.8, ease: 'power2.out' }, start + 1.1)
      timeline.to(cursor, { scale: 0.86, duration: 0.12, yoyo: true, repeat: 1 }, start + 2)
      timeline.to(cursor, { autoAlpha: 0, duration: 0.3 }, start + 2.5)
      if (target) timeline.to(target, { backgroundColor: '#E6EFEF', duration: 0.3 }, start + 2)
    }
    const detailRows = scene.querySelectorAll('.detail-row')
    if (detailRows.length) timeline.fromTo(detailRows, { x: 24, opacity: 0 }, { x: 0, opacity: 1, duration: 0.5, stagger: 0.55, ease: 'power2.out' }, start + 1.8) // beat-locked: scene 2 reveal at 5.8s
  })

  // Product moments inherit the scene's timing, including editorial retiming.
  document.querySelectorAll('[data-feature]').forEach((feature, index) => {
    const scene = feature.closest('.scene')
    const duration = Number(scene.dataset.duration) / scene.querySelectorAll('[data-feature]').length
    const start = Number(scene.dataset.start) + index * duration
    timeline.set(feature, { autoAlpha: 0 }, 0)
    timeline.set(feature, { autoAlpha: 1 }, start)
    timeline.fromTo(feature.querySelector('.copy'), { y: 28, opacity: 0 }, { y: 0, opacity: 1, duration: 0.55, ease: 'power3.out' }, start)
    timeline.fromTo(feature.querySelector('.demo'), { x: 50, opacity: 0 }, { x: 0, opacity: 1, duration: 0.6, ease: 'power3.out' }, start + 0.1)
    timeline.fromTo(feature.querySelectorAll('.demo-line, .day, .cta'), { y: 16, opacity: 0 }, { y: 0, opacity: 1, duration: 0.4, stagger: 0.18, ease: 'power2.out' }, start + 0.8)
    timeline.to(feature, { autoAlpha: 0, duration: 0.2 }, start + duration - 0.2)
  })

  const captionRoot = document.getElementById('captions')
  const script = window.EXPLAINER_SCRIPT
  const fallback = scenes.flatMap((scene) => {
    const captions = script.scenes[scene.id].captions
    const start = Number(scene.dataset.start) + 0.3
    const span = (Number(scene.dataset.duration) - 0.6) / captions.length
    return captions.map((text, index) => ({ text, start: start + index * span, end: start + (index + 1) * span }))
  })
  for (const cue of script.captionCues || fallback) {
    const node = document.createElement('p')
    node.className = 'caption'
    node.textContent = cue.text
    captionRoot.appendChild(node)
    timeline.set(node, { autoAlpha: 0 }, 0)
    timeline.set(node, { autoAlpha: 1 }, cue.start)
    timeline.set(node, { autoAlpha: 0 }, cue.end)
  }
  timeline.fromTo('.progress-fill', { scaleX: 0 }, { scaleX: 1, duration: Number(document.getElementById('root').dataset.duration), ease: 'none' }, 0)
  window.BRAG_TIMELINE = timeline
})()
