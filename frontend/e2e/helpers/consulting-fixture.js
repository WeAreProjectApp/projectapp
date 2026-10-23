/** Deterministic fixture backed by the approved public consulting presentation. */
import { readFileSync } from 'node:fs';

const programByLanguage = JSON.parse(readFileSync(new URL('./consulting-program.json', import.meta.url), 'utf8'));
const updatedAt = '2026-10-23T10:00:00Z';
const author = { name: 'Equipo ProjectApp', email: 'team@projectapp.test' };

export function consultingProgramFixture(language = 'es') {
  return structuredClone(programByLanguage[language === 'en' ? 'en' : 'es']);
}

function versionSummary(version = 21) {
  return {
    version,
    version_id: 100 + version,
    updated_at: updatedAt,
    author: { ...author },
    change_note: 'Presentación de consultoría actualizada.',
    restored_from_version_id: null,
    restored_from_version: null,
    etag: `consulting-program-${version}`,
  };
}

export function consultingOverviewFixture() {
  return {
    program: versionSummary(),
    connector: { slug: 'commercial', is_active: true },
    public_paths: { es: '/es-co/consulting', en: '/en-us/consulting' },
  };
}

export function consultingVersionsFixture(offset = 0) {
  const versions = Array.from({ length: 21 }, (_, index) => versionSummary(21 - index));
  return { total: versions.length, versions: versions.slice(offset, offset + 20) };
}

export function consultingPdfFixture(filename) {
  return {
    status: 200,
    contentType: 'application/pdf',
    headers: { 'Content-Disposition': `attachment; filename="${filename}"` },
    body: '%PDF-1.4 Consulting\n%%EOF',
  };
}

/** Fulfill the four read endpoints used by the public presentation and panel. */
export function consultingApiFixture({ apiPath, method, route }) {
  if (method !== 'GET') return null;
  const params = new URL(route.request().url()).searchParams;
  const language = params.get('lang') === 'en' ? 'en' : 'es';
  if (apiPath === 'consulting/public/pdf/') return consultingPdfFixture(`consulting-${language}.pdf`);
  const payloads = {
    'consulting/public/': () => consultingProgramFixture(language),
    'consulting/admin/': consultingOverviewFixture,
    'consulting/admin/program/versions/': () => consultingVersionsFixture(Number(params.get('offset') || 0)),
  };
  const payload = payloads[apiPath]?.();
  return payload ? { status: 200, contentType: 'application/json', body: JSON.stringify(payload) } : null;
}
