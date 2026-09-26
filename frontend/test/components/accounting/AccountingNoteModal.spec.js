import { mount } from '@vue/test-utils';

import AccountingNoteModal from '~/components/accounting/AccountingNoteModal.vue';

const NOTE = 'Pago mínimo cubierto.\nFalta conciliar la cuota de octubre.';

function mountModal(props = {}) {
  return mount(AccountingNoteModal, {
    props: {
      open: true,
      subtitle: 'T.C 0064 · Sáb, 19 sep 2026',
      notes: NOTE,
      ...props,
    },
    global: {
      stubs: {
        NuxtLink: { template: '<a><slot /></a>' },
        BaseModal: {
          props: ['modelValue', 'kind'],
          emits: ['close'],
          template: '<div v-if="modelValue"><slot /></div>',
        },
      },
    },
  });
}

describe('AccountingNoteModal', () => {
  // Bug caught: a long note stretched its table row; the full text now lives here.
  it('shows the complete note, line breaks included, with its record', () => {
    const wrapper = mountModal();

    expect(wrapper.get('[data-testid="accounting-note-body"]').text()).toBe(NOTE);
    expect(wrapper.get('[data-testid="accounting-note-modal"]').text())
      .toContain('T.C 0064 · Sáb, 19 sep 2026');
  });

  it('highlights the table search inside the note', () => {
    const wrapper = mountModal({ highlightQuery: 'cuota' });

    expect(wrapper.get('[data-testid="accounting-note-body"] mark').text()).toBe('cuota');
  });

  it('closes from its Cerrar button, not while the note is being read', async () => {
    const wrapper = mountModal();

    await wrapper.get('[data-testid="accounting-note-body"]').trigger('click');
    expect(wrapper.emitted('close')).toBeUndefined();

    await wrapper.get('button').trigger('click');
    expect(wrapper.emitted('close')).toHaveLength(1);
  });

  it('tells who can read the note when the owner gives a hint', () => {
    const wrapper = mountModal({ hint: 'Sólo para ti: no se muestran al cliente.' });

    expect(wrapper.get('[data-testid="accounting-note-hint"]').text())
      .toBe('Sólo para ti: no se muestran al cliente.');
  });

  it('renders nothing while closed', () => {
    const wrapper = mountModal({ open: false });

    expect(wrapper.find('[data-testid="accounting-note-modal"]').exists()).toBe(false);
  });
});
