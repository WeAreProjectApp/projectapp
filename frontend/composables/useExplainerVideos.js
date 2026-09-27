import { computed, unref } from 'vue'

import additionalModulesEs from '~/assets/videos/explainers/additional-modules-brag-v2-es.mp4'
import additionalModulesEsPoster from '~/assets/images/explainers/additional-modules-brag-v2-es.webp'
import proposalEs from '~/assets/videos/explainers/proposal-brag-v2-es.mp4'
import proposalEsPoster from '~/assets/images/explainers/proposal-brag-v2-es.webp'
import financingEs from '~/assets/videos/explainers/financing-brag-v2-es.mp4'
import financingEsPoster from '~/assets/images/explainers/financing-brag-v2-es.webp'

/**
 * Explainer videos produced with brag and rendered offline with HyperFrames (see explainers/README.md).
 * Each entry is keyed by module id and language; a missing language means the
 * surface hides the card until that render exists.
 */
export const EXPLAINER_IDS = Object.freeze(['additional-modules', 'financing', 'proposal'])

const EXPLAINERS = Object.freeze({
  proposal: {
    es: { src: proposalEs, poster: proposalEsPoster, durationSeconds: 58.2, width: 1920, height: 1080 },
  },
  'additional-modules': {
    es: {
      src: additionalModulesEs,
      poster: additionalModulesEsPoster,
      durationSeconds: 60,
      width: 1920,
      height: 1080,
    },
  },
  financing: {
    es: {
      src: financingEs,
      poster: financingEsPoster,
      durationSeconds: 60,
      width: 1920,
      height: 1080,
    },
  },
})

export function explainerVideoFor(id, language) {
  const lang = language === 'en' ? 'en' : 'es'
  const entry = EXPLAINERS[id]?.[lang]
  return entry ? { id, language: lang, ...entry } : null
}

export function formatExplainerDuration(seconds) {
  const total = Math.max(0, Math.round(Number(seconds) || 0))
  const minutes = Math.floor(total / 60)
  const rest = String(total % 60).padStart(2, '0')
  return `${minutes}:${rest}`
}

export function useExplainerVideo(id, language) {
  return computed(() => explainerVideoFor(id, unref(language)))
}
