import { mount } from '@vue/test-utils';

global.useLocalePath = jest.fn(() => (path) => path);

jest.mock('../../components/legal/LegalFooter.vue', () => ({
  __esModule: true,
  default: { name: 'LegalFooter', template: '<footer data-testid="legal-footer-stub" />' },
}));

import LegalDocument from '../../components/legal/LegalDocument.vue';
import waiterEs from '../../locales/waiter/es.js';
import { LEGAL_ENTITY } from '../../config/legalEntity.js';

const NuxtLinkStub = { props: ['to'], template: '<a :href="to"><slot /></a>' };

function mountDoc(doc, props = {}) {
  return mount(LegalDocument, {
    props: { doc, backLabel: 'Volver a Waiter', ...props },
    global: { stubs: { NuxtLink: NuxtLinkStub } },
  });
}

describe('LegalDocument', () => {
  it('renders the title, date, notice and every section heading', () => {
    const wrapper = mountDoc({
      title: 'Documento',
      last_updated: 'Última actualización: hoy.',
      notice: 'Aviso **clave**',
      sections: [
        { id: 'uno', title: '1. Uno', blocks: [{ p: 'Texto uno' }] },
        { id: 'dos', title: '2. Dos', blocks: [{ h3: 'Sub' }, { note: 'Nota' }] },
      ],
    });

    expect(wrapper.get('h1').text()).toBe('Documento');
    expect(wrapper.text()).toContain('Última actualización: hoy.');
    expect(wrapper.get('[data-testid="legal-document-notice"] strong').text()).toBe('clave');
    expect(wrapper.findAll('h2').map((h) => h.text())).toEqual(['1. Uno', '2. Dos']);
    expect(wrapper.get('#dos h3').text()).toBe('Sub');
  });

  it('renders nested list items under their parent item', () => {
    const wrapper = mountDoc({
      title: 'Doc',
      sections: [{ title: 'S', blocks: [{ ul: ['Simple', { text: 'Padre', items: ['Hijo A', 'Hijo B'] }] }] }],
    });

    const parent = wrapper.findAll('li').find((li) => li.text().startsWith('Padre'));
    expect(parent.findAll('li').map((li) => li.text())).toEqual(['Hijo A', 'Hijo B']);
  });

  it('renders ordered steps as an ordered list', () => {
    const wrapper = mountDoc({ title: 'Doc', sections: [{ title: 'S', blocks: [{ ol: ['Paso 1', 'Paso 2'] }] }] });

    expect(wrapper.findAll('ol > li')).toHaveLength(2);
  });

  it('renders tables with their header and one row per entry', () => {
    const wrapper = mountDoc({
      title: 'Doc',
      sections: [{ title: 'S', blocks: [{ table: { head: ['Quién', 'Dónde'], rows: [['AWS', 'Estados Unidos'], ['Wompi', 'Colombia']] } }] }],
    });

    expect(wrapper.findAll('th').map((th) => th.text())).toEqual(['Quién', 'Dónde']);
    expect(wrapper.findAll('tbody tr')).toHaveLength(2);
  });

  it('links back to the Waiter page by default', () => {
    const back = mountDoc({ title: 'Doc', sections: [] }).findAll('a').at(-1);

    expect(back.attributes('href')).toBe('/waiter');
    expect(back.text()).toContain('Volver a Waiter');
  });

  it('publishes the Spanish privacy policy with the WhatsApp section and the verified legal identity', () => {
    const wrapper = mountDoc(waiterEs.privacy);
    const text = wrapper.text();

    expect(wrapper.get('#whatsapp h2').text()).toBe('7. WhatsApp');
    expect(text).toContain(LEGAL_ENTITY.tradeName);
    expect(text).toContain(LEGAL_ENTITY.owner);
    expect(text).toContain(`NIT ${LEGAL_ENTITY.nit}`);
    expect(text).toContain(`${LEGAL_ENTITY.address}, ${LEGAL_ENTITY.city}`);
    expect(wrapper.find(`a[href="mailto:${LEGAL_ENTITY.email}"]`).exists()).toBe(true);
    expect(text).not.toMatch(/\[[A-ZÁÉÍÓÚ ]{3,}\]/); // no unfilled [PLACEHOLDER]
  });
});
