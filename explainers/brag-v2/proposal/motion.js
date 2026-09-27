/* All animation lives on one paused timeline so any frame can be reproduced. */
(() => {
  const timeline = gsap.timeline({ paused: true })
  const scenes = [...document.querySelectorAll('.scene')]
  scenes.forEach((scene, index) => {
    const start = Number(scene.dataset.start)
    const duration = Number(scene.dataset.duration)
    timeline.set(scene, { autoAlpha: 0 }, 0)
    timeline.set(scene, { autoAlpha: 1 }, start)
    const targets = [...scene.querySelectorAll('.reveal')]
    if (index === 0) {
      timeline.set(targets, { y: 0, opacity: 1 }, 0)
    } else {
      timeline.fromTo(targets, { y: 24, opacity: 0 }, {
        y: 0, opacity: 1, duration: 0.5, stagger: 0.07, ease: 'power3.out',
      }, start + 0.08)
    }
    if (index < scenes.length - 1) {
      timeline.to(scene.querySelector('.body'), {
        y: -12, opacity: 0, duration: 0.2, ease: 'power2.in',
      }, start + duration - 0.2)
      timeline.set(scene, { autoAlpha: 0 }, start + duration)
    }
  })
  const captionRoot = document.getElementById('captions')
  for (const cue of window.EXPLAINER_SCRIPT.captionCues || []) {
    const node = document.createElement('p')
    node.className = 'caption'
    node.textContent = cue.text
    captionRoot.appendChild(node)
    timeline.set(node, { autoAlpha: 0 }, 0)
    timeline.set(node, { autoAlpha: 1 }, cue.start)
    timeline.set(node, { autoAlpha: 0 }, cue.end)
  }
  timeline.fromTo('.progress-fill', { scaleX: 0 }, {
    scaleX: 1, duration: Number(document.getElementById('root').dataset.duration), ease: 'none',
  }, 0)
  window.BRAG_TIMELINE = timeline
})()
