import {
  buildItemId,
  ensureFunctionalRequirementItemIds,
  buildItemRequirementsMap,
} from '../../utils/itemRequirementLinks';

describe('buildItemId', () => {
  it('builds item-<group>-<slug> from the name', () => {
    expect(buildItemId('views', 'Registro de Usuario')).toBe('item-views-registro-de-usuario');
  });

  it('strips diacritics like the backend slugify', () => {
    expect(buildItemId('features', 'Búsqueda avanzada')).toBe('item-features-busqueda-avanzada');
  });

  it('returns empty string when the name has no slug content', () => {
    expect(buildItemId('views', '   ')).toBe('');
    expect(buildItemId('views', null)).toBe('');
  });

  it('falls back to "group" when the group id is empty', () => {
    expect(buildItemId('', 'Home')).toBe('item-group-home');
  });
});

describe('ensureFunctionalRequirementItemIds', () => {
  it('returns empty object for non-object input', () => {
    expect(ensureFunctionalRequirementItemIds(null)).toEqual({});
    expect(ensureFunctionalRequirementItemIds('nope')).toEqual({});
  });

  it('assigns ids to items missing one', () => {
    const result = ensureFunctionalRequirementItemIds({
      groups: [{ id: 'views', items: [{ name: 'Registro de usuario' }] }],
    });
    expect(result.groups[0].items[0].id).toBe('item-views-registro-de-usuario');
  });

  it('preserves existing ids verbatim', () => {
    const result = ensureFunctionalRequirementItemIds({
      groups: [{ id: 'views', items: [{ name: 'Home', id: 'custom-id' }] }],
    });
    expect(result.groups[0].items[0].id).toBe('custom-id');
  });

  it('dedupes generated ids with a numeric suffix', () => {
    const result = ensureFunctionalRequirementItemIds({
      groups: [{ id: 'views', items: [{ name: 'Home' }, { name: 'Home' }] }],
    });
    const ids = result.groups[0].items.map((i) => i.id);
    expect(ids).toEqual(['item-views-home', 'item-views-home-2']);
  });

  it('covers additionalModules items too', () => {
    const result = ensureFunctionalRequirementItemIds({
      additionalModules: [{ id: 'pwa_module', items: [{ name: 'Modo offline' }] }],
    });
    expect(result.additionalModules[0].items[0].id).toBe('item-pwa_module-modo-offline');
  });

  it('leaves items with unsluggable names id-less', () => {
    const result = ensureFunctionalRequirementItemIds({
      groups: [{ id: 'views', items: [{ name: '', description: 'x' }] }],
    });
    expect(result.groups[0].items[0].id).toBeUndefined();
  });

  it('does not mutate the input', () => {
    const input = { groups: [{ id: 'views', items: [{ name: 'Home' }] }] };
    ensureFunctionalRequirementItemIds(input);
    expect(input.groups[0].items[0].id).toBeUndefined();
  });
});

describe('buildItemRequirementsMap', () => {
  it('preserves technical detail formatting without aliasing the saved document', () => {
    const source = { flowKey: 'registration', title: 'Registro', linked_item_ids: ['item-a'],
      configuration: 'Validar correo único.', usageFlow: 'Completar → enviar.',
      text_formats: { '/configuration': 'markdown_html_v1' } };
    const map = buildItemRequirementsMap({ epics: [{ requirements: [source] }] });

    expect(map['item-a'][0].configuration).toBe(source.configuration);
    expect(map['item-a'][0].usageFlow).toBe(source.usageFlow);
    expect(map['item-a'][0].text_formats).toEqual(source.text_formats);
    map['item-a'][0].text_formats['/configuration'] = 'plain';
    expect(source.text_formats['/configuration']).toBe('markdown_html_v1');
  });
  const TECH_DOC = {
    epics: [{
      epicKey: 'views',
      requirements: [
        {
          flowKey: 'req-registro',
          title: 'Registro con verificación',
          description: 'Formulario con validación.',
          priority: 'high',
          linked_item_ids: ['item-views-registro', 'item-views-home'],
        },
        { flowKey: 'req-login', title: 'Login', linked_item_ids: ['item-views-registro'] },
      ],
    }],
  };

  it('maps each linked item id to its requirements', () => {
    const map = buildItemRequirementsMap(TECH_DOC);
    expect(map['item-views-registro'].map((r) => r.title)).toEqual([
      'Registro con verificación', 'Login',
    ]);
    expect(map['item-views-home']).toHaveLength(1);
  });

  it('carries title, description, priority, epicKey and flowKey', () => {
    const map = buildItemRequirementsMap(TECH_DOC);
    expect(map['item-views-home'][0]).toEqual({
      title: 'Registro con verificación',
      description: 'Formulario con validación.',
      priority: 'high',
      epicKey: 'views',
      flowKey: 'req-registro',
    });
  });

  it('accepts camelCase linkedItemIds', () => {
    const map = buildItemRequirementsMap({
      epics: [{ requirements: [{ title: 'R', linkedItemIds: ['item-x'] }] }],
    });
    expect(map['item-x']).toHaveLength(1);
  });

  it('ignores requirements without links and duplicate ids in one requirement', () => {
    const map = buildItemRequirementsMap({
      epics: [{ requirements: [
        { title: 'Sin enlaces' },
        { title: 'Duplicado', linked_item_ids: ['item-a', 'item-a'] },
      ] }],
    });
    expect(Object.keys(map)).toEqual(['item-a']);
    expect(map['item-a']).toHaveLength(1);
  });

  it('returns empty map for malformed input', () => {
    expect(buildItemRequirementsMap(null)).toEqual({});
    expect(buildItemRequirementsMap({ epics: 'nope' })).toEqual({});
    expect(buildItemRequirementsMap({ epics: ['nope', { requirements: 'nope' }] })).toEqual({});
  });
});
