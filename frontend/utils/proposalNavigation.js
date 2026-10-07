const documentStatuses = ['draft', 'sent', 'viewed', 'negotiating', 'accepted', 'rejected', 'expired', 'finished'];

export const proposalNavigationGroups = [
  { id: 'general', label: 'General', sections: [{ id: 'general', label: 'General' }] },
  {
    id: 'proposal', label: 'Propuesta', sections: [
      { id: 'sections', label: 'Secciones' },
      { id: 'technical', label: 'Detalle técnico' },
      { id: 'hour-rate', label: 'Tarifa por hora' },
      { id: 'prompt', label: 'Prompt' },
      { id: 'json', label: 'JSON' },
      { id: 'resources', label: 'Recursos' },
    ],
  },
  {
    id: 'communication', label: 'Comunicación', sections: [
      { id: 'emails', label: 'Correos' },
    ],
  },
  {
    id: 'documents', label: 'Documentos',
    sections: [{ id: 'documents', label: 'Documentos', statuses: documentStatuses }],
  },
  {
    id: 'project', label: 'Proyecto', sections: [
      { id: 'project-data', label: 'Datos' },
      { id: 'schedule', label: 'Cronograma', statuses: ['accepted', 'finished'] },
      { id: 'development', label: 'Desarrollo', statuses: ['accepted'] },
    ],
  },
  {
    id: 'tracking', label: 'Seguimiento', sections: [
      { id: 'activity', label: 'Actividad' },
      { id: 'history', label: 'Historial' },
      { id: 'analytics', label: 'Analítica' },
    ],
  },
];

export function availableProposalGroups(status) {
  return proposalNavigationGroups.map((group) => ({
    ...group,
    sections: group.sections.filter((section) => !status || !section.statuses || section.statuses.includes(status)),
  })).filter((group) => group.sections.length > 0);
}

export function proposalGroupForSection(section) {
  return proposalNavigationGroups.find((group) => group.sections.some((entry) => entry.id === section));
}

/** Accept existing leaf links and new group/section links without discarding
 * a status-gated destination while the proposal is still loading. */
export function resolveProposalSection(query, status) {
  const groups = availableProposalGroups(status);
  const tab = query.tab || 'general';
  if (tab === 'communication' && query.section === 'resources') return 'resources';
  const group = groups.find((entry) => entry.id === tab);
  if (group) {
    if (!query.section) return group.sections[0].id;
    return group.sections.some((section) => section.id === query.section) ? query.section : 'general';
  }
  const legacyGroup = groups.find((entry) => entry.sections.some((section) => section.id === tab));
  return legacyGroup && !query.section ? tab : 'general';
}

export function proposalSectionQuery(section) {
  const group = proposalGroupForSection(section);
  if (!group || group.id === 'general') return {};
  return group.sections.length === 1 ? { tab: group.id } : { tab: group.id, section };
}
