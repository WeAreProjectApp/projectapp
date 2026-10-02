import {
  buildProposalModuleLinkCatalog,
  buildProposalItemLinkOptions,
  buildTechnicalItemCoverage,
  buildProposalModuleLinkOptions,
  normalizeTechnicalDocumentModuleLinks,
} from '~/utils/proposalModuleLinkOptions'

describe('buildProposalModuleLinkOptions', () => {
  it('returns empty array when sections is not an array', () => {
    expect(buildProposalModuleLinkOptions(null)).toEqual([])
  })

  it('skips hidden groups', () => {
    const sections = [
      {
        section_type: 'functional_requirements',
        content_json: {
          groups: [{ id: 1, title: 'G', is_visible: false, is_calculator_module: true }],
        },
      },
    ]
    expect(buildProposalModuleLinkOptions(sections)).toEqual([])
  })

  it('skips group without title and without items', () => {
    const sections = [
      {
        section_type: 'functional_requirements',
        content_json: { groups: [{ id: 2, is_calculator_module: true }] },
      },
    ]
    expect(buildProposalModuleLinkOptions(sections)).toEqual([])
  })

  it('includes base group ids as canonical group-* options', () => {
    const sections = [
      {
        section_type: 'functional_requirements',
        content_json: {
          groups: [{ id: 3, title: 'T', is_calculator_module: false }],
        },
      },
    ]
    expect(buildProposalModuleLinkOptions(sections)).toEqual([
      expect.objectContaining({ id: 'group-3', label: 'T', isAlwaysIncluded: true }),
    ])
  })

  it('emits module id for calculator group', () => {
    const sections = [
      {
        section_type: 'functional_requirements',
        content_json: {
          groups: [{ id: 9, title: 'Calc', is_calculator_module: true, is_always_included: true }],
        },
      },
    ]
    const opts = buildProposalModuleLinkOptions(sections)
    expect(opts).toEqual([
      expect.objectContaining({ id: 'module-9', label: 'Calc', isAlwaysIncluded: true }),
    ])
  })

  it('marks an explicit base group as included', () => {
    const sections = [
      {
        section_type: 'functional_requirements',
        content_json: {
          groups: [{ id: 4, title: 'Pack', icon: '📦', is_calculator_module: false, is_always_included: true }],
        },
      },
    ]
    const opts = buildProposalModuleLinkOptions(sections)
    expect(opts[0].id).toBe('group-4')
    expect(opts[0].label).toContain('Pack')
    expect(opts[0].isAlwaysIncluded).toBe(true)
  })

  it('merges additionalModules into groups', () => {
    const sections = [
      {
        section_type: 'functional_requirements',
        content_json: {
          groups: [],
          additionalModules: [
            { id: 5, title: 'Add', is_calculator_module: true },
          ],
        },
      },
    ]
    const option = buildProposalModuleLinkOptions(sections)[0]
    expect(option.id).toBe('module-5')
    expect(option.aliases).toContain('5')
  })

  it('adds investment modules with string id', () => {
    const sections = [
      { section_type: 'investment', content_json: { modules: [{ id: 'inv1', title: 'I' }] } },
    ]
    const opts = buildProposalModuleLinkOptions(sections)
    expect(opts).toEqual([
      expect.objectContaining({ id: 'inv1', label: 'I', isAlwaysIncluded: false }),
    ])
  })

  it('skips investment module with empty id', () => {
    const sections = [
      { section_type: 'investment', content_json: { modules: [{ id: '', title: 'x' }] } },
    ]
    expect(buildProposalModuleLinkOptions(sections)).toEqual([])
  })

  it('uses id as label when group title is missing', () => {
    const sections = [
      {
        section_type: 'functional_requirements',
        content_json: {
          groups: [{ id: 7, items: ['x'], is_calculator_module: true }],
        },
      },
    ]
    const opts = buildProposalModuleLinkOptions(sections)
    expect(opts[0].label).toBe('7')
  })

  it('treats an optional group as not included by default', () => {
    const sections = [
      {
        section_type: 'functional_requirements',
        content_json: {
          groups: [{ id: 8, title: 'T', is_calculator_module: true }],
        },
      },
    ]
    const opts = buildProposalModuleLinkOptions(sections)
    expect(opts[0].id).toBe('module-8')
    expect(opts[0].isAlwaysIncluded).toBe(false)
  })

  it('uses module id as label when investment module has no title', () => {
    const sections = [
      { section_type: 'investment', content_json: { modules: [{ id: 'inv2' }] } },
    ]
    const opts = buildProposalModuleLinkOptions(sections)
    expect(opts[0].label).toBe('inv2')
  })

  it('builds alias and always-included metadata for legacy group ids', () => {
    const sections = [
      {
        section_type: 'functional_requirements',
        content_json: {
          groups: [{ id: 'views', title: 'Vistas', is_calculator_module: false }],
          additionalModules: [{ id: 'pwa_module', title: 'PWA', is_calculator_module: true }],
        },
      },
    ]

    const catalog = buildProposalModuleLinkCatalog(sections)

    expect(catalog.aliasMap.views).toBe('group-views')
    expect(catalog.aliasMap.pwa_module).toBe('module-pwa_module')
    expect(catalog.alwaysIncludedIds).toContain('group-views')
    expect(catalog.alwaysIncludedIds).not.toContain('module-pwa_module')
  })

  it('normalizes legacy technical_document linked_module_ids to canonical ids', () => {
    const sections = [
      {
        section_type: 'functional_requirements',
        content_json: {
          groups: [{ id: 'views', title: 'Vistas', is_calculator_module: false }],
          additionalModules: [{ id: 'pwa_module', title: 'PWA', is_calculator_module: true }],
        },
      },
    ]

    const normalized = normalizeTechnicalDocumentModuleLinks({
      epics: [
        {
          title: 'Epic',
          linked_module_ids: ['views'],
          requirements: [{ title: 'Req', linked_module_ids: ['pwa_module'] }],
        },
      ],
    }, buildProposalModuleLinkCatalog(sections).aliasMap)

    expect(normalized.epics[0].linked_module_ids).toEqual(['group-views'])
    expect(normalized.epics[0].linkedModuleIds).toBeUndefined()
    expect(normalized.epics[0].requirements[0].linked_module_ids).toEqual(['module-pwa_module'])
    expect(normalized.epics[0].requirements[0].linkedModuleIds).toBeUndefined()
  })

  it('skips null group entries in array', () => {
    const sections = [
      {
        section_type: 'functional_requirements',
        content_json: {
          groups: [null, { id: 1, title: 'Valid', is_calculator_module: true }],
        },
      },
    ]
    const opts = buildProposalModuleLinkOptions(sections)
    expect(opts).toHaveLength(1)
  })

  it('includes group with items even without title', () => {
    const sections = [
      {
        section_type: 'functional_requirements',
        content_json: {
          groups: [{ id: 2, items: ['a'], is_calculator_module: true }],
        },
      },
    ]
    const opts = buildProposalModuleLinkOptions(sections)
    expect(opts).toHaveLength(1)
    expect(opts[0].id).toBe('module-2')
  })

  it('converts numeric investment module id to string', () => {
    const sections = [
      { section_type: 'investment', content_json: { modules: [{ id: 42, title: 'Num' }] } },
    ]
    const opts = buildProposalModuleLinkOptions(sections)
    expect(opts).toEqual([{ id: '42', label: 'Num', aliases: ['42'], isAlwaysIncluded: false }])
  })

  it('skips investment module when modules key is missing', () => {
    const sections = [
      { section_type: 'investment', content_json: {} },
    ]
    expect(buildProposalModuleLinkOptions(sections)).toEqual([])
  })

  it('skips null investment module', () => {
    const sections = [
      { section_type: 'investment', content_json: { modules: [null, { id: 'ok', title: 'OK' }] } },
    ]
    const opts = buildProposalModuleLinkOptions(sections)
    expect(opts).toHaveLength(1)
  })

  it('falls back to id as label when title is missing', () => {
    const sections = [
      { section_type: 'investment', content_json: { modules: [{ id: 'fallback' }] } },
    ]
    const opts = buildProposalModuleLinkOptions(sections)
    expect(opts[0].label).toBe('fallback')
  })

  it('returns empty array when neither functional_requirements nor investment present', () => {
    expect(buildProposalModuleLinkOptions([{ section_type: 'other' }])).toEqual([])
  })
})

describe('commercial item traceability', () => {
  const sections = [{
    section_type: 'functional_requirements',
    content_json: {
      groups: [{
        id: 'views',
        title: 'Vistas',
        items: [{ id: 'item-views-map', name: 'Mapa' }],
      }],
      additionalModules: [{
        id: 'pwa_module',
        title: 'PWA',
        selected: false,
        items: [{ id: 'item-pwa-install', name: 'Instalación' }],
      }],
    },
  }]

  it('assigns required-item status from commercial inclusion', () => {
    const options = buildProposalItemLinkOptions(sections)

    expect(options[0].isRequiredForCoverage).toBe(true)
    expect(options[1].isRequiredForCoverage).toBe(false)
  })

  it('classifies traceability gaps by commercial inclusion', () => {
    const coverage = buildTechnicalItemCoverage(
      buildProposalItemLinkOptions(sections),
      { epics: [] },
    )

    expect(coverage.missingRequired.map((item) => item.id)).toEqual(['item-views-map'])
    expect(coverage.missingOptional.map((item) => item.id)).toEqual(['item-pwa-install'])
  })

  it('recognizes a linked required item', () => {
    const coverage = buildTechnicalItemCoverage(
      buildProposalItemLinkOptions(sections),
      { epics: [{ requirements: [{ linked_item_ids: ['item-views-map'] }] }] },
    )

    expect(coverage.coveredRequiredCount).toBe(1)
    expect(coverage.missingRequired).toEqual([])
  })
})
