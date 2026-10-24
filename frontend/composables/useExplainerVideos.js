import { computed, unref } from 'vue'

import additionalModulesEs from '~/assets/videos/explainers/additional-modules-brag-v2-es.mp4'
import additionalModulesEsPoster from '~/assets/images/explainers/additional-modules-brag-v2-es.webp'
import proposalEs from '~/assets/videos/explainers/proposal-brag-v2-es.mp4'
import proposalEsPoster from '~/assets/images/explainers/proposal-brag-v2-es.webp'
import financingEs from '~/assets/videos/explainers/financing-brag-v2-es.mp4'
import financingEsPoster from '~/assets/images/explainers/financing-brag-v2-es.webp'
import buildingOnDemandEs from '~/assets/videos/explainers/building-on-demand-brag-v2-es.mp4'
import buildingOnDemandEsPoster from '~/assets/images/explainers/building-on-demand-brag-v2-es.webp'
import platformOverviewEs from '~/assets/videos/explainers/platform-overview-brag-v2-es.mp4'
import platformOverviewPoster from '~/assets/images/explainers/platform-overview-brag-v2-es.webp'
import platformChatbotEs from '~/assets/videos/explainers/platform-chatbot-brag-v2-es.mp4'
import platformChatbotPoster from '~/assets/images/explainers/platform-chatbot-brag-v2-es.webp'
import platformVoiceEs from '~/assets/videos/explainers/platform-voice-reporting-brag-v2-es.mp4'
import platformVoicePoster from '~/assets/images/explainers/platform-voice-reporting-brag-v2-es.webp'

/**
 * Explainer videos authored with brag/HyperFrames and rendered offline (see explainers/README.md).
 * Each entry is keyed by module id and language; a missing language means the
 * surface hides the card until that render exists.
 */
export const EXPLAINER_IDS = Object.freeze(['additional-modules', 'financing', 'proposal', 'building-on-demand', 'platform-overview', 'platform-chatbot', 'platform-voice-reporting'])

const EXPLAINERS = Object.freeze({
  'platform-overview': {
    es: { src: platformOverviewEs, poster: platformOverviewPoster, durationSeconds: 90, width: 1920, height: 1080 },
  },
  'platform-chatbot': {
    es: { src: platformChatbotEs, poster: platformChatbotPoster, durationSeconds: 72, width: 1920, height: 1080 },
  },
  'platform-voice-reporting': {
    es: { src: platformVoiceEs, poster: platformVoicePoster, durationSeconds: 72, width: 1920, height: 1080 },
  },
  'building-on-demand': {
    es: { src: buildingOnDemandEs, poster: buildingOnDemandEsPoster, durationSeconds: 60, width: 1920, height: 1080 },
  },
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

export function useExplainerVideo(id, language, resource) {
  return computed(() => {
    const current = unref(resource)
    if (current?.mode === 'none') return null
    if (current?.mode === 'uploaded') return current.video
    return explainerVideoFor(id, unref(language))
  })
}
