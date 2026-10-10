/** Deterministic program and contract data; commercial terms are agreed privately. */
const updatedAt = '2026-10-09T10:00:00Z';
const author = { name: 'Equipo ProjectApp', email: 'team@projectapp.test' };

const content = {
  es: {
    hero: {
      eyebrow: 'Alianza de producto', title: 'Construye con nosotros',
      subtitle: 'Tu experiencia de negocio, nuestra tecnología. Incubamos productos juntos.',
      note: 'La participación se gana con compromisos verificables.',
    },
    origin: {
      title: 'Partimos de un problema real', summary: 'Tu industria conoce la necesidad.',
      industries: ['Logística', 'Salud', 'Educación'], points: ['Impacto económico comprobable', 'Acceso a usuarios reales'],
    },
    contribution: {
      title: 'La cadena completa de producción', summary: 'ProjectApp lleva el producto hasta su operación.',
      items: [
        { id: 'requirements', title: 'Requerimientos', summary: 'Convertimos el problema en alcance verificable.' },
        { id: 'design', title: 'Diseño', summary: 'Prototipos que validamos con usuarios.' },
        { id: 'development', title: 'Desarrollo', summary: 'Construcción del producto.' },
        { id: 'quality', title: 'Calidad', summary: 'Pruebas del comportamiento acordado.' },
        { id: 'operations', title: 'Operación', summary: 'Publicación, infraestructura y continuidad.' },
      ],
    },
    expert_profile: {
      title: 'Un experto comprometido', summary: 'Experiencia y acceso al mercado.',
      items: [{ id: 'industry', title: 'Conocimiento de la industria', summary: 'Contacto directo con usuarios reales.' }],
    },
    participation_models: {
      title: 'Formas de participar', summary: 'Los aportes particulares se pactan en privado.',
      items: [
        {
          id: 'monthly-investment', name: 'Inversión mensual', badge: 'Compromiso continuo',
          summary: 'Apoya la incubación durante el periodo acordado.', ideal_for: 'Expertos con capacidad de invertir.',
          expert_contributes: ['Experiencia de negocio', 'Inversión mensual acordada'],
          projectapp_contributes: ['Diseño y desarrollo', 'Infraestructura y operación'],
        },
        {
          id: 'shared-investment', name: 'Inversión compartida', badge: 'Aportes complementarios',
          summary: 'Cada parte asume compromisos definidos.', ideal_for: 'Equipos que comparten recursos.',
          expert_contributes: ['Acceso al mercado'], projectapp_contributes: ['Capacidad de producción'],
        },
        {
          id: 'expert-dedication', name: 'Dedicación del experto', badge: 'Experiencia aplicada',
          summary: 'La dedicación se demuestra con resultados.', ideal_for: 'Expertos disponibles para validar el producto.',
          expert_contributes: ['Validación con usuarios'], projectapp_contributes: ['Construcción del producto'],
        },
      ],
    },
    incubation_periods: {
      title: 'Tiempo para incubar', summary: 'El horizonte depende del alcance.',
      items: [
        { id: 'three-months', months: 3, title: 'Tres meses', summary: 'Validación inicial.' },
        { id: 'six-months', months: 6, title: 'Seis meses', summary: 'Primera versión utilizable.' },
        { id: 'nine-months', months: 9, title: 'Nueve meses', summary: 'Evolución con usuarios.' },
        { id: 'twelve-months', months: 12, title: 'Doce meses', summary: 'Consolidación del producto.' },
      ],
    },
    scope: { title: 'Un alcance definido', summary: 'Acordamos qué incluye la incubación.', items: [{ id: 'deliverables', title: 'Entregables verificables', summary: 'Cada entrega tiene criterios de aceptación.' }] },
    milestones: {
      title: 'Participación ganada por hitos', summary: 'Los resultados hacen visible el compromiso.',
      items: [{ id: 'validation', title: 'Validación del problema', summary: 'Evidencia de usuarios de la industria.' }],
      note: 'La participación no se obtiene automáticamente por el paso del tiempo.',
    },
    agreement: { title: 'Reglas del contrato', summary: 'La alianza se formaliza antes de construir.', items: [{ id: 'intellectual-property', title: 'Propiedad intelectual', summary: 'Titularidad y uso quedan pactados.' }] },
    process: { title: 'Cómo comenzamos', items: [{ id: 'conversation', title: 'Conversemos', summary: 'Presenta el problema y su impacto económico.' }] },
    faq: { title: 'Preguntas frecuentes', items: [{ id: 'participation', question: '¿Cuándo se gana la participación?', answer: 'Al cumplir los hitos pactados y demostrar los resultados.' }] },
    cta: { title: 'Hablemos de tu industria', body: 'Cuéntanos el problema que quieres resolver.', button_label: 'Hablar por WhatsApp', whatsapp_url: 'https://wa.me/573238122373?text=Building' },
    legal: { disclaimer: 'La propuesta y el contrato definen las condiciones de cada alianza.' },
  },
  en: {
    hero: {
      eyebrow: 'Product partnership', title: 'Build with us',
      subtitle: 'Your business expertise, our technology. We incubate products together.',
      note: 'Participation is earned through verifiable commitments.',
    },
    origin: {
      title: 'Start with a real problem', summary: 'Your industry knows the need.',
      industries: ['Logistics', 'Healthcare', 'Education'], points: ['Demonstrable economic impact', 'Access to real users'],
    },
    contribution: {
      title: 'The complete production chain', summary: 'ProjectApp takes the product into operation.',
      items: [
        { id: 'requirements', title: 'Requirements', summary: 'Turn the problem into verifiable scope.' },
        { id: 'design', title: 'Design', summary: 'Validate prototypes with users.' },
        { id: 'development', title: 'Development', summary: 'Build the product.' },
        { id: 'quality', title: 'Quality', summary: 'Test the agreed behavior.' },
        { id: 'operations', title: 'Operations', summary: 'Launch, infrastructure and continuity.' },
      ],
    },
    expert_profile: {
      title: 'A committed expert', summary: 'Experience and market access.',
      items: [{ id: 'industry', title: 'Industry knowledge', summary: 'Direct contact with real users.' }],
    },
    participation_models: {
      title: 'Ways to participate', summary: 'Specific contributions are agreed privately.',
      items: [
        {
          id: 'monthly-investment', name: 'Monthly investment', badge: 'Ongoing commitment',
          summary: 'Support incubation throughout the agreed period.', ideal_for: 'Experts able to invest.',
          expert_contributes: ['Business expertise', 'Agreed monthly investment'],
          projectapp_contributes: ['Design and development', 'Infrastructure and operations'],
        },
        {
          id: 'shared-investment', name: 'Shared investment', badge: 'Complementary contributions',
          summary: 'Each party takes on defined commitments.', ideal_for: 'Teams sharing resources.',
          expert_contributes: ['Market access'], projectapp_contributes: ['Production capabilities'],
        },
        {
          id: 'expert-dedication', name: 'Expert dedication', badge: 'Applied experience',
          summary: 'Dedication is demonstrated through results.', ideal_for: 'Experts available to validate the product.',
          expert_contributes: ['User validation'], projectapp_contributes: ['Product development'],
        },
      ],
    },
    incubation_periods: {
      title: 'Time to incubate', summary: 'The horizon depends on scope.',
      items: [
        { id: 'three-months', months: 3, title: 'Three months', summary: 'Initial validation.' },
        { id: 'six-months', months: 6, title: 'Six months', summary: 'First usable version.' },
        { id: 'nine-months', months: 9, title: 'Nine months', summary: 'Evolve with users.' },
        { id: 'twelve-months', months: 12, title: 'Twelve months', summary: 'Product consolidation.' },
      ],
    },
    scope: { title: 'Defined scope', summary: 'Agree what incubation includes.', items: [{ id: 'deliverables', title: 'Verifiable deliverables', summary: 'Each delivery has acceptance criteria.' }] },
    milestones: {
      title: 'Participation earned through milestones', summary: 'Results make commitment visible.',
      items: [{ id: 'validation', title: 'Problem validation', summary: 'Evidence from industry users.' }],
      note: 'Participation is not earned automatically through the passage of time.',
    },
    agreement: { title: 'Contract rules', summary: 'Formalize the partnership before building.', items: [{ id: 'intellectual-property', title: 'Intellectual property', summary: 'Agree ownership and use.' }] },
    process: { title: 'How we start', items: [{ id: 'conversation', title: 'Let’s talk', summary: 'Present the problem and its economic impact.' }] },
    faq: { title: 'Frequently asked questions', items: [{ id: 'participation', question: 'When is participation earned?', answer: 'By meeting the agreed milestones and demonstrating results.' }] },
    cta: { title: 'Tell us about your industry', body: 'Describe the problem you want to solve.', button_label: 'Talk on WhatsApp', whatsapp_url: 'https://wa.me/573238122373?text=Building' },
    legal: { disclaimer: 'The proposal and contract define each partnership’s conditions.' },
  },
};

export function buildingWithUsProgramFixture(language = 'es') {
  const lang = language === 'en' ? 'en' : 'es';
  return {
    language: lang, version: 21, updated_at: updatedAt,
    canonical_path: `/${lang === 'en' ? 'en-us' : 'es-co'}/building-with-us`,
    alternate_path: `/${lang === 'en' ? 'es-co' : 'en-us'}/building-with-us`,
    pdf_path: `/api/building-with-us/public/pdf/?lang=${lang}`,
    seo: { title: 'Building with Us | Project App.', description: content[lang].hero.subtitle },
    ...structuredClone(content[lang]),
  };
}

function versionSummary(kind, version = 21) {
  return {
    version, version_id: (kind === 'program' ? 100 : 200) + version,
    updated_at: updatedAt, author: { ...author },
    change_note: kind === 'program' ? 'Programa actualizado con aportes verificables.' : 'Contrato de alianza publicado.',
    restored_from_version_id: null, restored_from_version: null,
    etag: `building-with-us-${kind}-${version}`,
  };
}

export function buildingWithUsMirrorFixture(status = 'synchronized') {
  return {
    status, document_id: status === 'not_initialized' ? null : 731,
    title: 'Contrato Building with Us', folder_path: 'ProjectApp › Contratos',
    version: status === 'not_initialized' ? null : status === 'out_of_sync' ? 20 : 21,
    last_synced_at: status === 'not_initialized' ? null : updatedAt,
  };
}

export function buildingWithUsOverviewFixture() {
  return {
    program: versionSummary('program'),
    contract: { ...versionSummary('contract'), mirror: buildingWithUsMirrorFixture() },
    connector: { slug: 'building-with-us', is_active: true },
    public_paths: { es: '/es-co/building-with-us', en: '/en-us/building-with-us' },
  };
}

export function buildingWithUsVersionsFixture(kind = 'program', offset = 0) {
  const versions = Array.from({ length: 21 }, (_, index) => versionSummary(kind, 21 - index));
  return { total: versions.length, versions: versions.slice(offset, offset + 20) };
}

export function buildingWithUsContractFixture(status = 'synchronized') {
  return {
    ...versionSummary('contract'), mirror: buildingWithUsMirrorFixture(status),
    markdown: '# Contrato de alianza Building with Us\n\n## Objeto\n\nIncubar un producto con alcance definido y aportes verificables.\n\n## Compromisos\n\n| Parte | Aporte | Evidencia |\n| --- | --- | --- |\n| Experto | Validación con usuarios | Resultados documentados |\n| ProjectApp | Diseño y desarrollo | Entregables acordados |\n\nLa participación se gana al cumplir los hitos pactados.\n',
  };
}

export function buildingWithUsPdfFixture(filename) {
  return { status: 200, contentType: 'application/pdf', headers: { 'Content-Disposition': `attachment; filename="${filename}"` }, body: '%PDF-1.4 Building with Us\n%%EOF' };
}

/** Fulfill the seven read endpoints exactly as the public page and panel request them. */
export function buildingWithUsApiFixture({ apiPath, method, route }) {
  if (method !== 'GET') return null;
  const params = new URL(route.request().url()).searchParams;
  const lang = params.get('lang') === 'en' ? 'en' : 'es';
  if (apiPath === 'building-with-us/public/pdf/') return buildingWithUsPdfFixture(`building-with-us-${lang}.pdf`);
  if (apiPath === 'building-with-us/admin/contract/pdf/') return buildingWithUsPdfFixture('building-with-us-contract.pdf');
  const payloads = {
    'building-with-us/public/': () => buildingWithUsProgramFixture(lang),
    'building-with-us/admin/': buildingWithUsOverviewFixture,
    'building-with-us/admin/program/versions/': () => buildingWithUsVersionsFixture('program', Number(params.get('offset') || 0)),
    'building-with-us/admin/contract/versions/': () => buildingWithUsVersionsFixture('contract', Number(params.get('offset') || 0)),
    'building-with-us/admin/contract/': buildingWithUsContractFixture,
  };
  const payload = payloads[apiPath]?.();
  return payload ? { status: 200, contentType: 'application/json', body: JSON.stringify(payload) } : null;
}
