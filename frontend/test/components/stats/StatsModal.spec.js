import { mount } from '@vue/test-utils';
import StatsModal from '~/components/stats/StatsModal.vue';

const TABS = [
  { id: 'evolution', label: 'Evolución' },
  { id: 'concepts', label: 'Top conceptos' },
];

function mountModal(props = {}, options = {}) {
  return mount(StatsModal, {
    props: {
      open: true,
      title: 'Estadísticas de ingresos',
      tabs: TABS,
      modelValue: 'evolution',
      ...props,
    },
    global: {
      stubs: {
        Teleport: { template: '<div><slot /></div>' },
        Transition: { template: '<div><slot /></div>' },
        BaseModal: {
          props: ['modelValue', 'size'],
          emits: ['update:modelValue', 'close'],
          template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>',
        },
        BaseButton: {
          props: ['variant', 'type'],
          emits: ['click'],
          template:
            '<button :type="type || \'button\'" @click="$emit(\'click\', $event)"><slot /></button>',
        },
      },
    },
    ...options,
  });
}

describe('StatsModal', () => {
  it('renders title, subtitle and one tab button per entry', () => {
    const wrapper = mountModal({ subtitle: 'Año 2026' });

    expect(wrapper.text()).toContain('Estadísticas de ingresos');
    expect(wrapper.text()).toContain('Año 2026');
    expect(wrapper.text()).toContain('Evolución');
    expect(wrapper.text()).toContain('Top conceptos');
  });

  it('exposes the active tab to the default slot', () => {
    const wrapper = mountModal(
      {},
      {
        slots: {
          default: `<template #default="{ activeTab }">
            <p data-testid="panel">panel-{{ activeTab }}</p>
          </template>`,
        },
      },
    );

    expect(wrapper.find('[data-testid="panel"]').text()).toBe('panel-evolution');
  });

  it('re-emits tab changes as update:modelValue', async () => {
    const wrapper = mountModal();

    await wrapper.findAll('[role="tab"]')[1].trigger('click');
    expect(wrapper.emitted('update:modelValue')).toEqual([['concepts']]);
  });

  it('shows the loading skeleton instead of the slot while loading', () => {
    const wrapper = mountModal(
      { loading: true },
      { slots: { default: '<p data-testid="panel">contenido</p>' } },
    );

    expect(wrapper.find('[data-testid="stats-modal-loading"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="panel"]').exists()).toBe(false);
  });

  it('emits close from the footer button', async () => {
    const wrapper = mountModal();

    await wrapper.findAll('button').at(-1).trigger('click');
    expect(wrapper.emitted('close')).toHaveLength(1);
  });
});
