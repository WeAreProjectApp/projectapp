/**
 * Tests for FunctionalRequirementsModal logic.
 *
 * Covers: group prop structure, items rendering logic,
 * default prop values, and edge cases for empty/missing data.
 */

// ── Fixtures ─────────────────────────────────────────────────────────────────

const GROUP_FIXTURE = {
  icon: '🖥️',
  title: 'Vistas',
  description: 'Pantallas principales del sitio web.',
  items: [
    { icon: '🏠', name: 'Home', description: 'Landing page con CTAs.' },
    { icon: '📧', name: 'Contacto', description: 'Formulario de contacto.' },
    { icon: '📜', name: 'Términos', description: 'Políticas y condiciones.' },
  ],
};

const GROUP_NO_DESCRIPTION = {
  icon: '🧩',
  title: 'Componentes',
  description: '',
  items: [
    { icon: '🔝', name: 'Header', description: 'Logo y navegación.' },
  ],
};

const GROUP_EMPTY_ITEMS = {
  icon: '⚙️',
  title: 'Features',
  description: 'Funcionalidades interactivas.',
  items: [],
};

const GROUP_MINIMAL = {
  icon: '',
  title: '',
  description: '',
  items: [],
};

const DEFAULT_GROUP = {
  icon: '🧩',
  title: '',
  description: '',
  items: [],
};


// ── Group prop validation ────────────────────────────────────────────────────

/**
 * Mirrors the default prop structure from FunctionalRequirementsModal.vue.
 * Validates that the group object has the expected shape.
 */
function normalizeGroup(group) {
  return {
    icon: group?.icon || '🧩',
    title: group?.title || '',
    description: group?.description || '',
    items: group?.items || [],
  };
}

describe('normalizeGroup', () => {
  it('returns group data unchanged when all fields present', () => {
    const result = normalizeGroup(GROUP_FIXTURE);
    expect(result.icon).toBe('🖥️');
    expect(result.title).toBe('Vistas');
    expect(result.description).toBe('Pantallas principales del sitio web.');
    expect(result.items).toHaveLength(3);
  });

  it('defaults icon to puzzle emoji when missing', () => {
    const result = normalizeGroup({ title: 'Test', description: '', items: [] });
    expect(result.icon).toBe('🧩');
  });

  it('defaults icon to puzzle emoji when empty string', () => {
    const result = normalizeGroup(GROUP_MINIMAL);
    expect(result.icon).toBe('🧩');
  });

  it('defaults all fields when group is null', () => {
    const result = normalizeGroup(null);
    expect(result).toEqual(DEFAULT_GROUP);
  });

  it('defaults all fields when group is undefined', () => {
    const result = normalizeGroup(undefined);
    expect(result).toEqual(DEFAULT_GROUP);
  });

  it('preserves items array reference', () => {
    const result = normalizeGroup(GROUP_FIXTURE);
    expect(result.items).toBe(GROUP_FIXTURE.items);
  });
});


// ── Items structure validation ───────────────────────────────────────────────

describe('group items structure', () => {
  it('each item has icon, name, and description', () => {
    for (const item of GROUP_FIXTURE.items) {
      expect(item).toHaveProperty('icon');
      expect(item).toHaveProperty('name');
      expect(item).toHaveProperty('description');
    }
  });

  it('items should NOT have a price field (prices only in calculator)', () => {
    for (const item of GROUP_FIXTURE.items) {
      expect(item).not.toHaveProperty('price');
    }
  });

  it('handles group with no description', () => {
    const result = normalizeGroup(GROUP_NO_DESCRIPTION);
    expect(result.description).toBe('');
    expect(result.items).toHaveLength(1);
  });

  it('handles group with empty items array', () => {
    const result = normalizeGroup(GROUP_EMPTY_ITEMS);
    expect(result.items).toHaveLength(0);
    expect(result.description).toBe('Funcionalidades interactivas.');
  });
});


// ── Rendering conditions ─────────────────────────────────────────────────────

/**
 * Mirrors template v-if conditions from FunctionalRequirementsModal.vue.
 */
function shouldShowDescription(group) {
  return Boolean(group?.description);
}

function shouldShowItemsGrid(group) {
  return Boolean(group?.items && group.items.length > 0);
}

describe('rendering conditions', () => {
  it('shows description when non-empty', () => {
    expect(shouldShowDescription(GROUP_FIXTURE)).toBe(true);
  });

  it('hides description when empty string', () => {
    expect(shouldShowDescription(GROUP_NO_DESCRIPTION)).toBe(false);
  });

  it('hides description when group is null', () => {
    expect(shouldShowDescription(null)).toBe(false);
  });

  it('shows items grid when items exist', () => {
    expect(shouldShowItemsGrid(GROUP_FIXTURE)).toBe(true);
  });

  it('hides items grid when items is empty array', () => {
    expect(shouldShowItemsGrid(GROUP_EMPTY_ITEMS)).toBe(false);
  });

  it('hides items grid when items is undefined', () => {
    expect(shouldShowItemsGrid({ title: 'Test' })).toBe(false);
  });

  it('hides items grid when group is null', () => {
    expect(shouldShowItemsGrid(null)).toBe(false);
  });
});


// ── Item icon fallback ───────────────────────────────────────────────────────

/**
 * Mirrors the template fallback: {{ item.icon || '✅' }}.
 */
function getItemIcon(item) {
  return item?.icon || '✅';
}

describe('item icon fallback', () => {
  it('returns the item icon when present', () => {
    expect(getItemIcon({ icon: '🏠', name: 'Home', description: '' })).toBe('🏠');
  });

  it('falls back to checkmark when icon is empty', () => {
    expect(getItemIcon({ icon: '', name: 'Test', description: '' })).toBe('✅');
  });

  it('falls back to checkmark when icon is missing', () => {
    expect(getItemIcon({ name: 'Test', description: '' })).toBe('✅');
  });

  it('falls back to checkmark when item is null', () => {
    expect(getItemIcon(null)).toBe('✅');
  });
});


// ── Multiple groups simulation ───────────────────────────────────────────────

describe('multiple groups from functional requirements', () => {
  const GROUPS = [GROUP_FIXTURE, GROUP_NO_DESCRIPTION, GROUP_EMPTY_ITEMS];

  it('each group can be independently normalized', () => {
    const normalized = GROUPS.map(normalizeGroup);
    expect(normalized).toHaveLength(3);
    expect(normalized[0].title).toBe('Vistas');
    expect(normalized[1].title).toBe('Componentes');
    expect(normalized[2].title).toBe('Features');
  });

  it('total items across all groups is correct', () => {
    const totalItems = GROUPS.reduce((sum, g) => sum + (g.items?.length || 0), 0);
    expect(totalItems).toBe(4);
  });

  it('only groups with items should show the items grid', () => {
    const withItems = GROUPS.filter(shouldShowItemsGrid);
    expect(withItems).toHaveLength(2);
  });
});


// ── Mounted tests: nested linked-requirements modal ──────────────────────────

import { mount } from '@vue/test-utils';
import FunctionalRequirementsModal from '../../components/BusinessProposal/FunctionalRequirementsModal.vue';
import LinkedRequirementsModal from '../../components/BusinessProposal/LinkedRequirementsModal.vue';
import BaseRichTextContent from '../../components/base/BaseRichTextContent.vue';

const GROUP_WITH_IDS = {
  icon: '🖥️',
  title: 'Vistas',
  description: 'Pantallas del sitio.',
  items: [
    { icon: '🏠', name: 'Home', description: 'Landing.', id: 'item-views-home' },
    { icon: '📧', name: 'Contacto', description: 'Formulario.', id: 'item-views-contacto' },
    { icon: '📜', name: 'Legacy sin id', description: 'Item viejo.' },
  ],
};

const ITEM_REQUIREMENTS_MAP = {
  'item-views-home': [
    {
      title: 'Home dinámico con CTAs',
      description: 'Página de inicio con secciones administrables.',
      priority: 'high',
      epicKey: 'views',
      flowKey: 'req-home',
      configuration: 'NO debe mostrarse',
      usageFlow: 'NO debe mostrarse',
    },
    {
      title: 'Estados vacío y de error del Home',
      description: 'Comportamiento sin contenido cargado y ante fallas.',
      priority: 'medium',
      epicKey: 'views',
      flowKey: 'req-home-estados',
    },
  ],
};

function mountModal(props = {}) {
  return mount(FunctionalRequirementsModal, {
    props: {
      visible: true,
      group: GROUP_WITH_IDS,
      itemRequirementsMap: ITEM_REQUIREMENTS_MAP,
      language: 'es',
      ...props,
    },
    global: { components: { BaseRichTextContent }, stubs: { teleport: true, transition: false } },
  });
}

describe('nested linked-requirements link', () => {
  it('shows the "Ver requerimientos" link only for items with linked requirements', () => {
    const wrapper = mountModal();
    const links = wrapper.findAll('[data-testid="view-requirements-link"]');
    expect(links).toHaveLength(1);
    expect(links[0].text()).toContain('Ver requerimientos (2)');
  });

  it('shows no link at all for legacy groups without item ids', () => {
    const wrapper = mountModal({
      group: {
        ...GROUP_WITH_IDS,
        items: GROUP_WITH_IDS.items.map(({ id, ...rest }) => rest),
      },
    });
    expect(wrapper.findAll('[data-testid="view-requirements-link"]')).toHaveLength(0);
  });

  it('shows no link when the map is empty', () => {
    const wrapper = mountModal({ itemRequirementsMap: {} });
    expect(wrapper.findAll('[data-testid="view-requirements-link"]')).toHaveLength(0);
  });

  it('uses English label when language is en', () => {
    const wrapper = mountModal({ language: 'en' });
    expect(wrapper.find('[data-testid="view-requirements-link"]').text())
      .toContain('View requirements (2)');
  });

  it('opens the nested modal with title, priority and description but not configuration/usageFlow', async () => {
    const wrapper = mountModal();
    await wrapper.find('[data-testid="view-requirements-link"]').trigger('click');

    const nested = wrapper.findComponent(LinkedRequirementsModal);
    expect(nested.props('visible')).toBe(true);
    expect(nested.props('requirements')).toHaveLength(2);

    const text = nested.text();
    expect(text).toContain('Home dinámico con CTAs');
    expect(text).toContain('Alta'); // priority high → Alta (es)
    expect(text).toContain('Página de inicio con secciones administrables.');
    expect(text).toContain('Estados vacío y de error del Home');
    expect(text).not.toContain('NO debe mostrarse');
  });

  it('closing the nested modal keeps the parent modal open', async () => {
    const wrapper = mountModal();
    await wrapper.find('[data-testid="view-requirements-link"]').trigger('click');

    const nested = wrapper.findComponent(LinkedRequirementsModal);
    nested.vm.$emit('close');
    await wrapper.vm.$nextTick();

    expect(wrapper.findComponent(LinkedRequirementsModal).props('visible')).toBe(false);
    expect(wrapper.emitted('close')).toBeUndefined();
    expect(wrapper.text()).toContain('Vistas');
  });

  it('resets the nested modal when the parent closes', async () => {
    const wrapper = mountModal();
    await wrapper.find('[data-testid="view-requirements-link"]').trigger('click');
    await wrapper.setProps({ visible: false });
    await wrapper.setProps({ visible: true });
    expect(wrapper.findComponent(LinkedRequirementsModal).props('visible')).toBe(false);
  });
});
