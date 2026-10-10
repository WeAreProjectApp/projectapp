import { mount } from '@vue/test-utils';
import { nextTick } from 'vue';
import ConfirmModal from '../../components/ConfirmModal.vue';
import BaseModal from '../../components/base/BaseModal.vue';
import BaseButton from '../../components/base/BaseButton.vue';

function mountModal(props = {}) {
  return mount(ConfirmModal, {
    props: {
      modelValue: true,
      title: 'Eliminar elemento',
      message: 'Esta acción no se puede deshacer.',
      confirmText: 'Eliminar',
      cancelText: 'Cancelar',
      variant: 'warning',
      ...props,
    },
    global: {
      components: { BaseModal, BaseButton },
      stubs: {
        Teleport: true,
        Transition: false,
      },
    },
  });
}

describe('ConfirmModal', () => {
  afterEach(() => {
    document.body.style.overflow = '';
  });

  it('renders title, message, and action labels', () => {
    const wrapper = mountModal();

    expect(wrapper.text()).toContain('Eliminar elemento');
    expect(wrapper.text()).toContain('Esta acción no se puede deshacer.');
    expect(wrapper.text()).toContain('Eliminar');
    expect(wrapper.text()).toContain('Cancelar');
  });

  it('emits confirm and closes when the confirm button is clicked', async () => {
    const wrapper = mountModal();

    // Por testid y no por índice: el modal puede montar un botón secundario.
    await wrapper.find('[data-testid="confirm-modal-confirm"]').trigger('click');

    expect(wrapper.emitted('confirm')).toEqual([[]]);
    expect(wrapper.emitted('update:modelValue')).toEqual([[false]]);
  });

  it('emits cancel and closes when the cancel button is clicked', async () => {
    const wrapper = mountModal();

    await wrapper.find('button').trigger('click');

    expect(wrapper.emitted('cancel')).toEqual([[]]);
    expect(wrapper.emitted('update:modelValue')).toEqual([[false]]);
  });

  it('emits cancel when the backdrop is clicked', async () => {
    const wrapper = mountModal();

    await wrapper.get('.absolute.inset-0').trigger('click');

    expect(wrapper.emitted('cancel')).toEqual([[]]);
    expect(wrapper.emitted('update:modelValue')).toEqual([[false]]);
  });

  it('closes on Escape only while the modal is open', async () => {
    const wrapper = mountModal();

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    await nextTick();

    expect(wrapper.emitted('cancel')).toEqual([[]]);

    const closedWrapper = mountModal({ modelValue: false });
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    await nextTick();

    expect(closedWrapper.emitted('cancel')).toBeUndefined();
  });

  it('locks body scroll while open and restores it when closed or unmounted', async () => {
    const wrapper = mountModal({ modelValue: false });
    await wrapper.setProps({ modelValue: true });
    await nextTick();

    expect(document.body.style.overflow).toBe('hidden');

    await wrapper.setProps({ modelValue: false });
    await nextTick();
    expect(document.body.style.overflow).toBe('');

    await wrapper.setProps({ modelValue: true });
    await nextTick();
    wrapper.unmount();
    expect(document.body.style.overflow).toBe('');
  });

  it('renders the correct variant classes for danger and info', () => {
    const dangerWrapper = mountModal({ variant: 'danger' });
    const infoWrapper = mountModal({ variant: 'info' });

    expect(dangerWrapper.html()).toContain('bg-danger-soft');
    expect(infoWrapper.html()).toContain('bg-primary-soft');
  });

  it('falls back to warning styles when the variant is unknown', () => {
    const warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});
    const wrapper = mountModal({ variant: 'unexpected' });

    expect(wrapper.html()).toContain('bg-warning-soft');
    warnSpy.mockRestore();
  });

  describe('scope detail slot', () => {
    it('renders slot content between the message and the confirm buttons', () => {
      const wrapper = mount(ConfirmModal, {
        props: { modelValue: true, message: 'Se asignará Ana Pérez a 2 hostings.' },
        slots: { default: '<p>kore.com.co</p>' },
        global: {
          components: { BaseModal, BaseButton },
          stubs: { Teleport: true, Transition: false },
        },
      });

      const html = wrapper.html();
      expect(wrapper.find('[data-testid="confirm-modal-detail"]').text())
        .toContain('kore.com.co');
      expect(html.indexOf('Se asignará')).toBeLessThan(html.indexOf('kore.com.co'));
      expect(html.indexOf('kore.com.co'))
        .toBeLessThan(html.indexOf('confirm-modal-confirm'));
    });

    it('leaves no empty detail block when nothing is passed', () => {
      const wrapper = mountModal();

      expect(wrapper.find('[data-testid="confirm-modal-detail"]').exists()).toBe(false);
    });

    it('widens the dialog only when asked to', () => {
      expect(mountModal().findComponent(BaseModal).props('size')).toBe('md');
      expect(mountModal({ size: 'lg' }).findComponent(BaseModal).props('size')).toBe('lg');
    });
  });

  describe('requireTypeText', () => {
    it('renders the type-to-confirm input when requireTypeText is set', () => {
      const wrapper = mountModal({ requireTypeText: 'DELETE' });

      const input = wrapper.find('[data-testid="confirm-type-input"]');
      expect(input.exists()).toBe(true);
    });

    it('disables the confirm button until the typed value matches exactly', async () => {
      const wrapper = mountModal({ requireTypeText: 'DELETE' });

      const confirmBtn = wrapper.find('[data-testid="confirm-modal-confirm"]');
      expect(confirmBtn.attributes('disabled')).toBeDefined();

      const input = wrapper.find('[data-testid="confirm-type-input"]');
      await input.setValue('delete');
      expect(confirmBtn.attributes('disabled')).toBeDefined();

      await input.setValue('DELETE');
      expect(confirmBtn.attributes('disabled')).toBeUndefined();

      await confirmBtn.trigger('click');
      expect(wrapper.emitted('confirm')).toEqual([[]]);
    });

    it('does not emit confirm when clicking while disabled', async () => {
      const wrapper = mountModal({ requireTypeText: 'DELETE' });

      await wrapper.find('[data-testid="confirm-modal-confirm"]').trigger('click');
      expect(wrapper.emitted('confirm')).toBeUndefined();
    });

    it('clears the typed value when the modal reopens', async () => {
      const wrapper = mountModal({ modelValue: false, requireTypeText: 'DELETE' });
      await wrapper.setProps({ modelValue: true });
      await nextTick();

      const input = wrapper.find('[data-testid="confirm-type-input"]');
      await input.setValue('DELETE');
      expect(input.element.value).toBe('DELETE');

      await wrapper.setProps({ modelValue: false });
      await nextTick();
      await wrapper.setProps({ modelValue: true });
      await nextTick();

      expect(wrapper.find('[data-testid="confirm-type-input"]').element.value).toBe('');
    });
  });

  describe('hideCancel', () => {
    it('hides the cancel button when hideCancel is true', () => {
      const wrapper = mountModal({ hideCancel: true });

      const buttons = wrapper.findAll('button').filter((b) => b.text() === 'Cancelar');
      expect(buttons.length).toBe(0);
    });

    it('still shows the confirm button when hideCancel is true', () => {
      const wrapper = mountModal({ hideCancel: true });

      expect(wrapper.find('[data-testid="confirm-modal-confirm"]').exists()).toBe(true);
    });
  });

  describe('secondary action', () => {
    it('renders no secondary button by default', () => {
      const wrapper = mountModal();

      expect(wrapper.find('[data-testid="confirm-modal-secondary"]').exists()).toBe(false);
    });

    it('renders the secondary button when secondaryText is set', () => {
      const wrapper = mountModal({ secondaryText: 'Archivar en su lugar' });

      const secondary = wrapper.find('[data-testid="confirm-modal-secondary"]');
      expect(secondary.exists()).toBe(true);
      expect(secondary.text()).toContain('Archivar en su lugar');
    });

    it('emits secondary and closes without emitting confirm', async () => {
      const wrapper = mountModal({ secondaryText: 'Archivar en su lugar' });

      await wrapper.find('[data-testid="confirm-modal-secondary"]').trigger('click');

      expect(wrapper.emitted('secondary')).toEqual([[]]);
      expect(wrapper.emitted('confirm')).toBeUndefined();
      expect(wrapper.emitted('update:modelValue')).toEqual([[false]]);
    });

    it('keeps the secondary usable while the typed-word gate still blocks confirm', async () => {
      const wrapper = mountModal({
        secondaryText: 'Archivar en su lugar',
        requireTypeText: 'DELETE',
      });

      // La reja bloquea el destructivo...
      expect(
        wrapper.find('[data-testid="confirm-modal-confirm"]').attributes('disabled'),
      ).toBeDefined();

      // ...pero la salida sigue disponible sin escribir nada.
      await wrapper.find('[data-testid="confirm-modal-secondary"]').trigger('click');
      expect(wrapper.emitted('secondary')).toEqual([[]]);
    });

    it('renders the secondary hint above the type-to-confirm input', () => {
      const wrapper = mountModal({
        secondaryText: 'Archivar en su lugar',
        secondaryHint: 'Archivar lo conserva y lo saca de la lista.',
        requireTypeText: 'DELETE',
      });

      const html = wrapper.html();
      const hintAt = html.indexOf('confirm-modal-secondary-hint');
      const inputAt = html.indexOf('confirm-type-input');
      expect(hintAt).toBeGreaterThan(-1);
      expect(inputAt).toBeGreaterThan(-1);
      expect(hintAt).toBeLessThan(inputAt);
    });
  });

  it('leaves the body scroll alone when stacked over another modal', async () => {
    document.body.style.overflow = 'hidden';
    const wrapper = mountModal({ lockScroll: false });

    await wrapper.setProps({ modelValue: false });
    await nextTick();

    // The modal underneath is still open: closing this one must not free
    // the page behind both.
    expect(document.body.style.overflow).toBe('hidden');
  });
});
