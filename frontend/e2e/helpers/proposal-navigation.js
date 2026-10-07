import { expect } from './test.js';

const GROUP_LABELS = {
  general: 'General',
  proposal: 'Propuesta',
  communication: 'Comunicación',
  documents: 'Documentos',
  project: 'Proyecto',
  tracking: 'Seguimiento',
};

const SECTION_LABELS = {
  general: 'General', sections: 'Secciones', technical: 'Detalle técnico',
  'hour-rate': 'Tarifa por hora', prompt: 'Prompt', json: 'JSON',
  emails: 'Correos', resources: 'Recursos', documents: 'Documentos',
  'project-data': 'Datos', schedule: 'Cronograma', development: 'Desarrollo', activity: 'Actividad',
  history: 'Historial', analytics: 'Analítica',
};

/**
 * Select a proposal editor destination through both levels of its responsive
 * navigation. This catches specs that would otherwise click a leaf tool while
 * its parent group is still hidden after navigation regrouping.
 */
export async function selectProposalDestination(page, group, section) {
  const viewport = page.viewportSize();
  const primary = page.getByTestId('proposal-primary-navigation');

  if (viewport && viewport.width < 1024) {
    await primary.getByRole('combobox', { name: 'Áreas de la propuesta' }).selectOption(group);
  } else {
    await primary.getByRole('tab', { name: GROUP_LABELS[group], exact: true }).click();
  }

  if (!section || section === 'general' || (group === 'documents' && section === 'documents') || (group === 'communication' && section === 'emails') || (group === 'project' && section === 'project-data')) return;

  const secondary = page.getByTestId('proposal-secondary-navigation');
  if (viewport && viewport.width < 1024) {
    await secondary.getByRole('combobox').selectOption(section);
  } else {
    await secondary.getByRole('tab', { name: SECTION_LABELS[section], exact: true }).click();
  }

  await expect(secondary).toBeAttached();
}
