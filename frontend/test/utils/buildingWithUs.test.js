import {
  buildingWithUsLanguage,
  buildingWithUsPath,
  buildingWithUsPublicUrl,
  buildingWithUsPdfUrl,
  isBuildingWithUsProgram,
  safeWhatsappUrl,
  listOf,
} from '../../utils/buildingWithUs'

describe('Building with Us public utilities', () => {
  it.each([['en-us', 'en'], ['es-co', 'es']])('maps locale %s to API language %s', (locale, language) => {
    expect(buildingWithUsLanguage(locale)).toBe(language)
  })

  it.each([['es', '/es-co/building-with-us'], ['en', '/en-us/building-with-us']])('locates the %s public page', (language, path) => {
    expect(buildingWithUsPath(language)).toBe(path)
  })

  it.each([
    ['es', 'https://projectapp.co/es-co/building-with-us'],
    ['en', 'https://projectapp.co/en-us/building-with-us'],
  ])('builds the %s public URL', (language, url) => {
    expect(buildingWithUsPublicUrl(language)).toBe(url)
  })

  it.each([
    ['es', '/api/building-with-us/public/pdf/?lang=es'],
    ['en', '/api/building-with-us/public/pdf/?lang=en'],
  ])('builds the %s PDF URL', (language, url) => {
    expect(buildingWithUsPdfUrl(language)).toBe(url)
  })

  it('accepts a program with a populated hero title', () => {
    expect(isBuildingWithUsProgram({ hero: { title: 'Construye con nosotros' } })).toBe(true)
  })

  it.each([null, {}, [], { hero: { title: '   ' } }])('rejects an unusable program %p', (payload) => {
    expect(isBuildingWithUsProgram(payload)).toBe(false)
  })

  it.each(['https://wa.me/573238122373?text=Hola', 'https://api.whatsapp.com/send?phone=573238122373'])('keeps a supported WhatsApp URL %s', (url) => {
    expect(safeWhatsappUrl(url)).toBe(url)
  })

  it.each(['javascript:alert(1)', 'https://wa.me.example.com/redirect', null])('replaces an unsafe WhatsApp URL %p', (url) => {
    expect(safeWhatsappUrl(url)).toBe('https://wa.me/573238122373')
  })

  it('preserves a list of contributions', () => {
    const items = ['Experiencia en logística']

    expect(listOf(items)).toBe(items)
  })

  it('replaces an absent list with an empty list', () => {
    expect(listOf(undefined)).toEqual([])
  })
})
