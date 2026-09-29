import { ref } from 'vue';
import {
  buildDevChecklistMarkdown,
  buildDevChecklistFilename,
  useDevChecklistMarkdown,
} from '../../composables/useDevChecklistMarkdown';

function makeProposal(overrides = {}) {
  return {
    id: 42,
    uuid: 'abc-123',
    title: 'Tienda Acme',
    client_name: 'Acme Corp',
    status: 'accepted',
    language: 'es',
    sections: [
      {
        section_type: 'executive_summary',
        content_json: {
          paragraphs: ['Resumen del proyecto.'],
          highlights: ['Diseño', 'Desarrollo'],
        },
      },
      {
        section_type: 'context_diagnostic',
        content_json: {
          paragraphs: ['Contexto del cliente.'],
          opportunity: 'Crecer en línea.',
        },
      },
      {
        section_type: 'functional_requirements',
        content_json: {
          groups: [
            {
              title: 'Vistas',
              description: 'Pantallas del sitio.',
              items: [
                { name: 'Inicio', description: 'Landing principal.' },
                { name: 'Contacto' },
              ],
            },
          ],
          additionalModules: [
            {
              id: 'module_blog',
              title: 'Blog',
              description: 'Sistema de blog.',
              is_calculator_module: false,
              selected: true,
              items: [{ name: 'Editor', description: 'Editor WYSIWYG.' }],
            },
            {
              id: 'integration_dian',
              title: 'Facturación electrónica',
              description: 'Integración DIAN.',
              is_calculator_module: true,
              selected: true,
              items: [{ name: 'API DIAN', description: 'Conexión REST.' }],
            },
          ],
        },
      },
      {
        section_type: 'value_added_modules',
        content_json: {
          module_ids: ['admin_module', 'integration_dian'],
          justifications: {
            admin_module: 'Para que no dependas de un dev.',
            integration_dian: 'Cumplimiento normativo.',
          },
        },
      },
      {
        section_type: 'technical_document',
        content_json: {
          dataModel: {
            entities: [
              { name: 'Product', description: 'SKU y precio.', keyFields: 'id, slug' },
            ],
          },
          epics: [
            {
              title: 'Storefront',
              description: 'Tienda pública.',
              requirements: [
                {
                  title: 'Catálogo con filtros',
                  description: 'Buscar productos.',
                  configuration: 'Índices en category_id.',
                  usageFlow: 'Abre → filtra → ve resultados.',
                },
              ],
            },
          ],
          apiDomains: [
            { domain: 'Catalog', summary: 'GET productos.' },
          ],
          integrations: {
            included: [
              {
                service: 'Pasarela de pagos',
                provider: 'Wompi',
                connection: 'REST + webhooks',
                dataExchange: 'Monto, estado',
                accountOwner: 'Cliente',
              },
            ],
            excluded: [{ service: 'ERP SAP', reason: 'Fuera de alcance' }],
          },
          growthReadiness: {
            strategies: [
              {
                dimension: 'Tráfico',
                preparation: 'SSR y CDN.',
                evolution: 'Más workers Gunicorn.',
              },
            ],
          },
        },
      },
    ],
    ...overrides,
  };
}

describe('buildDevChecklistMarkdown', () => {
  it('renders header with proposal metadata', () => {
    const md = buildDevChecklistMarkdown(makeProposal());
    expect(md).toContain('# Tienda Acme');
    expect(md).toContain('Cliente: Acme Corp');
    expect(md).toContain('Estado: accepted');
    expect(md).toContain('Idioma: es');
  });

  it('renders objective block from executive_summary and context_diagnostic', () => {
    const md = buildDevChecklistMarkdown(makeProposal());
    expect(md).toContain('## 🎯 Objetivo');
    expect(md).toContain('Resumen del proyecto.');
    expect(md).toContain('Contexto del cliente.');
    expect(md).toContain('**Oportunidad:** Crecer en línea.');
    expect(md).toContain('**Incluye:**');
    expect(md).toContain('- Diseño');
    expect(md).toContain('- Desarrollo');
  });

  it('renders components and functionalities as checkboxes', () => {
    const md = buildDevChecklistMarkdown(makeProposal());
    expect(md).toContain('## 🧩 Componentes y funcionalidades');
    expect(md).toContain('### Vistas');
    expect(md).toContain('- [ ] **Inicio** — Landing principal.');
    expect(md).toContain('- [ ] **Contacto**');
  });

  it('lists selected additional modules without prices', () => {
    // Fails if the checklist revives price-based optional-module output.
    const md = buildDevChecklistMarkdown(makeProposal());
    expect(md).toContain('## ➕ Módulos adicionales');
    expect(md).toContain('### Blog');
    expect(md).toContain('- [ ] **Editor** — Editor WYSIWYG.');
    expect(md).toContain('### Facturación electrónica');
    expect(md).toContain('- [ ] **API DIAN** — Conexión REST.');
    expect(md).not.toContain('Costes adicionales');
    expect(md).not.toContain('+60%');
  });

  it('resolves value_added_modules ids against additionalModules titles', () => {
    const md = buildDevChecklistMarkdown(makeProposal());
    expect(md).toContain('## 🎁 Incluidos sin costo extra');
    expect(md).toContain('- [ ] **Admin Module** — Para que no dependas de un dev.');
    expect(md).toContain('- [ ] **Facturación electrónica** — Cumplimiento normativo.');
  });

  it('renders technical sections in the documented order', () => {
    const md = buildDevChecklistMarkdown(makeProposal());
    const order = [
      '## 🗄️ Modelos de datos',
      '## 🏗️ Épicas y requerimientos',
      '## 🔌 API endpoints',
      '## 🔗 Integraciones (incluidas)',
      '## 🌱 Preparación para el crecimiento (visión v2)',
    ];
    let cursor = 0;
    for (const heading of order) {
      const idx = md.indexOf(heading, cursor);
      expect(idx).toBeGreaterThan(-1);
      cursor = idx;
    }
  });

  it('renders entity fields and requirement metadata', () => {
    const md = buildDevChecklistMarkdown(makeProposal());
    expect(md).toContain('- [ ] **Product** — SKU y precio. _(campos clave: id, slug)_');
    expect(md).toContain('### Storefront');
    expect(md).toContain('- [ ] **Catálogo con filtros** — Buscar productos.');
    expect(md).toContain('  - Configuración: Índices en category_id.');
    expect(md).toContain('  - Flujo: Abre → filtra → ve resultados.');
  });

  it('renders included integrations only and skips excluded ones', () => {
    const md = buildDevChecklistMarkdown(makeProposal());
    expect(md).toContain('- [ ] **Pasarela de pagos — Wompi** · REST + webhooks · Datos: Monto, estado · Cuenta: Cliente');
    expect(md).not.toContain('ERP SAP');
  });

  it('omits blocks whose source sections are missing', () => {
    const proposal = makeProposal({
      sections: [
        // Only objective + technical, no functional/value_added
        {
          section_type: 'executive_summary',
          content_json: { paragraphs: ['Solo resumen.'], highlights: [] },
        },
      ],
    });
    const md = buildDevChecklistMarkdown(proposal);
    // The heading set collapses to the objective alone — every other block
    // (components, extras, pricing, data, infra, integrations, seeds…)
    // must vanish with its missing source section.
    const headings = md.match(/^## .+$/gm) || [];
    expect(headings).toHaveLength(1);
    expect(headings[0]).toContain('🎯 Objetivo');
  });

  it('returns empty string for falsy proposal', () => {
    expect(buildDevChecklistMarkdown(null)).toBe('');
    expect(buildDevChecklistMarkdown(undefined)).toBe('');
  });

  it('switches to English labels when language is "en"', () => {
    const md = buildDevChecklistMarkdown(makeProposal({ language: 'en' }));
    expect(md).toContain('## 🎯 Objective');
    expect(md).toContain('## 🧩 Components and features');
    expect(md).toContain('Client: Acme Corp');
    expect(md).toContain('**Opportunity:** Crecer en línea.');
  });
});

describe('buildDevChecklistFilename', () => {
  it('uses uuid when available', () => {
    expect(buildDevChecklistFilename({ uuid: 'abc-123', id: 5 })).toBe('dev-checklist-abc-123.md');
  });

  it('falls back to id when uuid is missing', () => {
    expect(buildDevChecklistFilename({ id: 9 })).toBe('dev-checklist-9.md');
  });

  it('falls back to "proposal" when no identifier is present', () => {
    expect(buildDevChecklistFilename({})).toBe('dev-checklist-proposal.md');
    expect(buildDevChecklistFilename(null)).toBe('dev-checklist-proposal.md');
  });
});

describe('useDevChecklistMarkdown', () => {
  it('exposes reactive markdown and filename', () => {
    const proposal = ref(makeProposal());
    const { markdown, filename } = useDevChecklistMarkdown(proposal);
    expect(markdown.value).toContain('# Tienda Acme');
    expect(filename.value).toBe('dev-checklist-abc-123.md');

    proposal.value = makeProposal({ title: 'Otra propuesta', uuid: 'xyz-999' });
    expect(markdown.value).toContain('# Otra propuesta');
    expect(filename.value).toBe('dev-checklist-xyz-999.md');
  });
});
