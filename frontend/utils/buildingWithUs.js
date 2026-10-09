export function buildingWithUsLanguage(locale) {
  return String(locale || '').startsWith('en') ? 'en' : 'es'
}

export function buildingWithUsPath(lang) {
  return lang === 'en' ? '/en-us/building-with-us' : '/es-co/building-with-us'
}

export function buildingWithUsPublicUrl(lang) {
  return `https://projectapp.co${buildingWithUsPath(lang)}`
}

export function buildingWithUsPdfUrl(lang) {
  return `/api/building-with-us/public/pdf/?lang=${lang}`
}

export function isBuildingWithUsProgram(payload) {
  return Boolean(
    payload && typeof payload === 'object' && !Array.isArray(payload)
    && typeof payload.hero?.title === 'string' && payload.hero.title.trim(),
  )
}

export function safeWhatsappUrl(url) {
  return typeof url === 'string'
    && (url.startsWith('https://wa.me/') || url.startsWith('https://api.whatsapp.com/'))
    ? url
    : 'https://wa.me/573238122373'
}

export function listOf(value) {
  return Array.isArray(value) ? value : []
}
