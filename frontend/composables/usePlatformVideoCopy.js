import { useI18n } from '#imports'
import es from '~/locales/platformVideos/es'
import en from '~/locales/platformVideos/en'

export function usePlatformVideoCopy() {
  return useI18n({
    useScope: 'local',
    messages: { 'es-co': { platformVideos: es }, 'en-us': { platformVideos: en } },
  })
}
