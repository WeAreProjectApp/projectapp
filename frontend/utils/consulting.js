export function consultingLanguage(locale) {
  return String(locale || '').startsWith('en') ? 'en' : 'es'
}

export function consultingPath(lang) {
  return lang === 'en' ? '/en-us/consulting' : '/es-co/consulting'
}

export function consultingPublicUrl(lang) {
  return `https://projectapp.co${consultingPath(lang)}`
}

export function consultingPdfUrl(lang) {
  return `/api/consulting/public/pdf/?lang=${lang}`
}

export function isConsultingProgram(payload) {
  return Boolean(
    payload && typeof payload === 'object' && !Array.isArray(payload)
    && typeof payload.hero?.title === 'string' && payload.hero.title.trim(),
  )
}

export function safeConsultingWhatsappUrl(url) {
  return typeof url === 'string'
    && (url.startsWith('https://wa.me/') || url.startsWith('https://api.whatsapp.com/'))
    ? url
    : 'https://wa.me/573238122373'
}

export function consultingListOf(value) {
  return Array.isArray(value) ? value : []
}
