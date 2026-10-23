import {
  consultingLanguage,
  consultingPath,
  consultingPublicUrl,
  consultingPdfUrl,
  consultingListOf,
  isConsultingProgram,
  safeConsultingWhatsappUrl,
} from '../../utils/consulting';

describe('consulting public utilities', () => {
  it.each([
    ['en-us', 'en', '/en-us/consulting', 'https://projectapp.co/en-us/consulting', '/api/consulting/public/pdf/?lang=en'],
    ['es-co', 'es', '/es-co/consulting', 'https://projectapp.co/es-co/consulting', '/api/consulting/public/pdf/?lang=es'],
  ])('maps %s to its public resources', (locale, language, path, publicUrl, pdfUrl) => {
    // Bug caught: locale-specific links could send prospects to another language or a non-existent document.
    expect({
      language: consultingLanguage(locale),
      path: consultingPath(language),
      publicUrl: consultingPublicUrl(language),
      pdfUrl: consultingPdfUrl(language),
    }).toEqual({ language, path, publicUrl, pdfUrl });
  });

  it('accepts a program with a visible hero title', () => {
    // Bug caught: a usable public consulting program could be rejected before it reaches the page.
    expect(isConsultingProgram({ hero: { title: 'Automatiza donde más impacto genera' } })).toBe(true);
  });

  it.each([null, [], {}, { hero: { title: '   ' } }, { hero: { title: 22 } }])('rejects malformed public content %p', (payload) => {
    // Bug caught: incomplete payloads could render a broken public presentation.
    expect(isConsultingProgram(payload)).toBe(false);
  });

  it.each([
    'https://wa.me/573238122373?text=Quiero%20una%20consultoría',
    'https://api.whatsapp.com/send?phone=573238122373',
  ])('keeps the supported WhatsApp contact %s', (url) => {
    // Bug caught: a configured WhatsApp call to action could be replaced despite using an approved host.
    expect(safeConsultingWhatsappUrl(url)).toBe(url);
  });

  it.each(['javascript:alert(1)', 'https://wa.me.example.com/redirect', 'https://example.com/whatsapp', null])('replaces the unsafe WhatsApp URL %p', (url) => {
    // Bug caught: editorial content could turn the contact button into a script or a link to an unapproved domain.
    expect(safeConsultingWhatsappUrl(url)).toBe('https://wa.me/573238122373');
  });

  it.each([
    [['Horas recuperadas'], ['Horas recuperadas']],
    [undefined, []],
    [{ title: 'No es una lista' }, []],
  ])('returns the list contract for %p', (value, expected) => {
    // Bug caught: optional content sections could crash when their API value is not an array.
    expect(consultingListOf(value)).toEqual(expected);
  });
});
