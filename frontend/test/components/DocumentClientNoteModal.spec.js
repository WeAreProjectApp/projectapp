import { flushPromises, mount } from '@vue/test-utils';
import { nextTick } from 'vue';
import { createPinia, setActivePinia } from 'pinia';

import DocumentClientNoteModal from '../../components/panel/documents/DocumentClientNoteModal.vue';
import BaseActionIcon from '../../components/base/BaseActionIcon.vue';
import BaseAlert from '../../components/base/BaseAlert.vue';
import BaseButton from '../../components/base/BaseButton.vue';
import BaseBadge from '../../components/base/BaseBadge.vue';
import BaseInput from '../../components/base/BaseInput.vue';
import BaseModal from '../../components/base/BaseModal.vue';
import BaseModalActions from '../../components/base/BaseModalActions.vue';
import BaseTextarea from '../../components/base/BaseTextarea.vue';
import BaseToggle from '../../components/base/BaseToggle.vue';
import { useDocumentStateStore } from '../../stores/document_states';

const mockNotifyError = jest.fn();

jest.mock('../../composables/usePanelNotify', () => ({
  usePanelNotify: () => ({ error: mockNotifyError }),
}));

function mountModal(props = {}) {
  return mount(DocumentClientNoteModal, {
    props: { modelValue: true, ...props },
    global: {
      components: {
        BaseAlert, BaseBadge, BaseButton, BaseInput, BaseModal, BaseModalActions, BaseTextarea, BaseToggle,
      },
      stubs: {
        Teleport: true,
        Transition: false,
        NuxtLink: { template: '<a><slot /></a>' },
      },
    },
  });
}

const subjectField = (wrapper) => wrapper.find('[data-testid="client-note-subject"]');
const emailField = (wrapper) => wrapper.find('[data-testid="client-note-email"]');
const whatsappField = (wrapper) => wrapper.find('[data-testid="client-note-whatsapp"]');
const customTitleField = (wrapper, index = 0) => wrapper.find(`[data-testid="client-note-custom-title-${index}"]`);
const customContentField = (wrapper, index = 0) => wrapper.find(`[data-testid="client-note-custom-content-${index}"]`);

describe('DocumentClientNoteModal', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    mockNotifyError.mockReset();
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: jest.fn().mockResolvedValue(undefined) },
    });
  });

  it('opens with the stored notes', () => {
    const wrapper = mountModal({
      subject: 'Entrega lista',
      emailBody: 'Hola Ana, el documento está listo.',
      whatsappMessage: 'Hola Ana, revisa tu correo.',
      customNotes: [{ title: 'Seguimiento', content: 'Llamar el viernes.' }],
    });

    expect(subjectField(wrapper).element.value).toBe('Entrega lista');
    expect(emailField(wrapper).element.value).toBe('Hola Ana, el documento está listo.');
    expect(whatsappField(wrapper).element.value).toBe('Hola Ana, revisa tu correo.');
    expect(customTitleField(wrapper).element.value).toBe('Seguimiento');
    expect(customContentField(wrapper).element.value).toBe('Llamar el viernes.');
  });

  it('submits a trimmed client note', async () => {
    const wrapper = mountModal();
    await subjectField(wrapper).setValue('  Informe listo  ');
    await emailField(wrapper).setValue('  Correo completo  ');
    await whatsappField(wrapper).setValue('  WhatsApp breve  ');
    await wrapper.find('[data-testid="client-note-add-custom"]').trigger('click');
    await customTitleField(wrapper).setValue('  Próximo paso  ');
    await customContentField(wrapper).setValue('  Confirmar la fecha.  ');

    await wrapper.find('[data-testid="client-note-submit"]').trigger('click');

    expect(wrapper.emitted('submit')[0]).toEqual([{
      subject: 'Informe listo',
      emailBody: 'Correo completo',
      whatsappMessage: 'WhatsApp breve',
      customNotes: [{ title: 'Próximo paso', content: 'Confirmar la fecha.' }],
    }]);
    expect(wrapper.emitted('update:modelValue')).toBeFalsy();
  });

  it('closes without submitting draft changes', async () => {
    const wrapper = mountModal({ subject: 'Original' });
    await subjectField(wrapper).setValue('Borrador');

    await wrapper.find('[data-testid="client-note-cancel"]').trigger('click');

    expect(wrapper.emitted('submit')).toBeFalsy();
    expect(wrapper.emitted('update:modelValue')[0]).toEqual([false]);
  });

  it('copies the email body', async () => {
    const wrapper = mountModal({ emailBody: 'Correo para copiar' });

    await wrapper.find('[data-testid="client-note-copy-email"]').trigger('click');
    await nextTick();

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('Correo para copiar');
    expect(wrapper.get('[role="status"]').text()).toBe('Copiado: correo');
    expect(wrapper.find('[data-testid="client-note-copy-email"]').attributes('aria-label'))
      .toBe('Copiado: correo');
  });

  it('renders client messages as read only', () => {
    const wrapper = mountModal({
      readonly: true,
      subject: 'Asunto guardado',
    });

    expect(subjectField(wrapper).element.disabled).toBe(true);
    expect(emailField(wrapper).element.disabled).toBe(true);
    expect(whatsappField(wrapper).element.disabled).toBe(true);
    expect(wrapper.find('[data-testid="client-note-submit"]').exists()).toBe(false);
  });

  it('permits observation deletion on a read-only issued document', () => {
    const wrapper = mountModal({
      readonly: true,
      documentId: 8,
      notes: [{ id: 9, title: 'Prueba', content: 'No debía existir', status: 'open' }],
    });

    expect(wrapper.find('[data-testid="document-observation-delete-9"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="document-observation-edit-9"]').exists()).toBe(false);
  });

  it('keeps generated version messages immutable while observations stay editable', () => {
    const wrapper = mountModal({
      immutableContent: true,
      documentId: 8,
      subject: 'Propuesta enviada',
      notes: [{ id: 9, title: 'Seguimiento', content: 'Llamar mañana', status: 'open' }],
    });

    expect(subjectField(wrapper).element.disabled).toBe(true);
    expect(wrapper.text()).toContain('El PDF y los mensajes guardados con esta versión son inmutables');
    expect(wrapper.find('[data-testid="client-note-submit"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="document-observation-edit-9"]').exists()).toBe(true);
  });

  it('renders custom notes as read only', () => {
    const wrapper = mountModal({
      readonly: true,
      customNotes: [{ title: 'Seguimiento', content: 'Llamar el viernes.' }],
    });

    expect(customTitleField(wrapper).element.disabled).toBe(true);
    expect(customContentField(wrapper).element.disabled).toBe(true);
    expect(wrapper.find('[data-testid="client-note-add-custom"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="client-note-custom-delete-0"]').exists()).toBe(false);
  });

  it('requires complete custom notes before submitting', async () => {
    const wrapper = mountModal();
    await wrapper.find('[data-testid="client-note-add-custom"]').trigger('click');

    await wrapper.find('[data-testid="client-note-submit"]').trigger('click');

    expect(wrapper.emitted('submit')).toBeFalsy();
    expect(wrapper.find('[data-testid="client-note-custom-title-error-0"]').text())
      .toBe('El título es obligatorio.');
    expect(wrapper.find('[data-testid="client-note-custom-content-error-0"]').text())
      .toBe('El contenido es obligatorio.');
  });

  it('marks the custom note delete action with the shared trash icon', () => {
    const wrapper = mountModal({
      customNotes: [{ title: 'Temporal', content: 'No conservar.' }],
    });

    const remove = wrapper.find('[data-testid="client-note-custom-delete-0"]');
    expect(remove.findComponent(BaseActionIcon).props('action')).toBe('delete');
    expect(remove.text()).toBe('');
  });

  it('deletes a custom note from the draft', async () => {
    const wrapper = mountModal({
      customNotes: [{ title: 'Temporal', content: 'No conservar.' }],
    });

    await wrapper.find('[data-testid="client-note-custom-delete-0"]').trigger('click');
    await wrapper.find('[data-testid="client-note-submit"]').trigger('click');

    expect(wrapper.emitted('submit')[0][0].customNotes).toEqual([]);
  });

  it('labels the persisted action as Guardar cambios', () => {
    const wrapper = mountModal();

    expect(wrapper.find('[data-testid="client-note-submit"]').text()).toBe('Guardar cambios');
    expect(wrapper.find('[data-testid="client-note-draft-hint"]').exists()).toBe(false);
  });

  it('explains the draft action before document creation', () => {
    const wrapper = mountModal({ mode: 'draft' });

    expect(wrapper.find('[data-testid="client-note-submit"]').text()).toBe('Aplicar al borrador');
    expect(wrapper.find('[data-testid="client-note-draft-hint"]').text())
      .toContain('Quedarán guardadas cuando crees el documento');
  });

  it('keeps Guardar cambios disabled until a message changes', async () => {
    const wrapper = mountModal({ subject: 'Entrega lista', emailBody: 'Hola Ana.' });
    const submit = wrapper.get('[data-testid="client-note-submit"]');
    expect(submit.attributes('disabled')).toBe('');
    expect(submit.attributes('title')).toBe('No hay cambios por guardar.');

    await emailField(wrapper).setValue('Hola Ana, el documento está listo.');

    expect(submit.attributes('disabled')).toBeUndefined();
    expect(wrapper.get('[data-testid="client-note-unsaved"]').text()).toBe('Cambios sin guardar');
  });

  it('disables the save again when the change is undone', async () => {
    const wrapper = mountModal({ whatsappMessage: 'Hola Ana, revisa tu correo.' });
    await whatsappField(wrapper).setValue('Hola Ana, revisa tu correo hoy.');

    await whatsappField(wrapper).setValue('Hola Ana, revisa tu correo.');

    expect(wrapper.get('[data-testid="client-note-submit"]').attributes('disabled')).toBe('');
    expect(wrapper.find('[data-testid="client-note-unsaved"]').exists()).toBe(false);
  });

  it('treats whitespace the save would trim as no change', async () => {
    const wrapper = mountModal({ subject: 'Entrega lista' });

    await subjectField(wrapper).setValue('Entrega lista  ');

    expect(wrapper.get('[data-testid="client-note-submit"]').attributes('title'))
      .toBe('No hay cambios por guardar.');
  });

  it('measures changes against the notes present when the modal opens', async () => {
    const wrapper = mountModal({ subject: 'Entrega lista' });
    await subjectField(wrapper).setValue('Entrega corregida');
    await wrapper.setProps({ modelValue: false });

    await wrapper.setProps({ subject: 'Entrega corregida', modelValue: true });

    expect(subjectField(wrapper).element.value).toBe('Entrega corregida');
    expect(wrapper.get('[data-testid="client-note-submit"]').attributes('disabled')).toBe('');
  });

  it('lets a new custom note be applied to the draft', async () => {
    const wrapper = mountModal({ mode: 'draft' });
    const submit = wrapper.get('[data-testid="client-note-submit"]');
    expect(submit.attributes('title')).toBe('No hay cambios para aplicar.');

    await wrapper.get('[data-testid="client-note-add-custom"]').trigger('click');

    expect(submit.attributes('disabled')).toBeUndefined();
    expect(wrapper.get('[data-testid="client-note-unsaved"]').text()).toBe('Cambios sin aplicar');
  });

  it('blocks dismissal while the save is running', async () => {
    const wrapper = mountModal({ saving: true });

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    await wrapper.find('[data-testid="client-note-cancel"]').trigger('click');

    expect(wrapper.emitted('update:modelValue')).toBeFalsy();
    expect(wrapper.find('[data-testid="client-note-submit"]').attributes('disabled')).toBe('');
  });

  it('copies a custom note content', async () => {
    const wrapper = mountModal({
      customNotes: [{ title: 'Seguimiento', content: 'Llamar el viernes.' }],
    });

    await wrapper.find('[data-testid="client-note-custom-copy-content-0"]').trigger('click');
    await nextTick();

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('Llamar el viernes.');
    expect(wrapper.get('[role="status"]').text()).toBe('Copiado: contenido de la nota 1');
  });

  it('copies a custom note title', async () => {
    const wrapper = mountModal({
      customNotes: [{ title: 'Seguimiento', content: 'Llamar el viernes.' }],
    });
    const copyButton = wrapper.find('[data-testid="client-note-custom-copy-title-0"]');
    expect(copyButton.findComponent(BaseActionIcon).props('action')).toBe('copy');

    await copyButton.trigger('click');
    await nextTick();

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('Seguimiento');
    expect(wrapper.get('[role="status"]').text()).toBe('Copiado: título de la nota 1');
    expect(copyButton.attributes('aria-label')).toBe('Copiado: título de la nota 1');
  });

  it('creates a normalized observation linked to needs-fix', async () => {
    const store = useDocumentStateStore();
    jest.spyOn(store, 'createNote').mockResolvedValue({
      success: true,
      data: { id: 9, title: '', content: 'Corregir el total', status: 'open', episode: 30 },
    });
    const wrapper = mountModal({
      documentId: 8,
      notes: [],
      customNotes: [{ title: 'Legado', content: 'Ya normalizada' }],
    });
    expect(wrapper.find('[data-testid="client-note-custom-0"]').exists()).toBe(false);
    await wrapper.find('[data-testid="document-observation-content"]').setValue('Corregir el total');

    await wrapper.find('[data-testid="document-observation-add"]').trigger('click');

    expect(store.createNote).toHaveBeenCalledWith(8, {
      title: '',
      content: 'Corregir el total',
      mark_needs_fix: true,
    });
    expect(wrapper.emitted('workflow-changed')).toHaveLength(1);
  });

  it('resolves an observation from the panel form', async () => {
    const store = useDocumentStateStore();
    jest.spyOn(store, 'finishNote').mockResolvedValue({
      success: true,
      data: { note: { id: 9, status: 'resolved', episode: 30 } },
    });
    const wrapper = mountModal({
      documentId: 8,
      notes: [{ id: 9, title: 'Total', content: 'Corregir', status: 'open', episode: 30 }],
    });

    await wrapper.find('[data-testid="document-observation-resolve-9"]').trigger('click');
    await wrapper.find('[data-testid="document-observation-resolution"]').setValue('Corregido');
    await wrapper.find('[data-testid="document-observation-finish-form"] input[type="checkbox"]').setValue(true);
    await wrapper.find('[data-testid="document-observation-finish-form"]').trigger('submit');
    await flushPromises();

    expect(store.finishNote).toHaveBeenCalledWith(8, 9, {
      outcome: 'resolved',
      resolution_note: 'Corregido',
      move_cycle_to_bug_attended: true,
    });
  });

  it('shows the note content before deleting it', async () => {
    const store = useDocumentStateStore();
    jest.spyOn(store, 'deleteNote').mockResolvedValue({
      success: true,
      data: { deleted_note_ids: [9] },
    });
    const wrapper = mountModal({
      documentId: 8,
      notes: [{ id: 9, title: 'Prueba', content: 'Texto equivocado', status: 'open' }],
    });

    await wrapper.find('[data-testid="document-observation-delete-9"]').trigger('click');

    const confirmation = wrapper.get('[data-testid="document-observation-delete-confirmation"]');
    expect(confirmation.text()).toContain('Texto equivocado');
    expect(confirmation.text()).toContain('podrás recuperarlas desde la papelera');
    expect(confirmation.text()).toContain('no lo borra de la bandeja');
  });

  it('deletes a finished observation', async () => {
    const store = useDocumentStateStore();
    jest.spyOn(store, 'deleteNote').mockResolvedValue({
      success: true,
      data: { deleted_note_ids: [9] },
    });
    const wrapper = mountModal({
      documentId: 8,
      notes: [{ id: 9, title: 'Duplicada', content: 'No aplica', status: 'discarded' }],
    });

    await wrapper.find('[data-testid="document-observation-delete-9"]').trigger('click');
    await wrapper.find('[data-testid="document-observation-confirm-delete"]').trigger('click');
    await flushPromises();

    expect(store.deleteNote).toHaveBeenCalledWith(8, 9);
    expect(wrapper.find('[data-testid="document-observation-9"]').exists()).toBe(false);
  });

  it('deletes selected observations in one request', async () => {
    const store = useDocumentStateStore();
    jest.spyOn(store, 'bulkDeleteNotes').mockResolvedValue({
      success: true,
      data: { deleted_note_ids: [9, 10] },
    });
    const wrapper = mountModal({
      documentId: 8,
      notes: [
        { id: 9, title: 'Prueba uno', content: 'Uno', status: 'open' },
        { id: 10, title: 'Prueba dos', content: 'Dos', status: 'resolved' },
      ],
    });
    await wrapper.find('[data-testid="document-observation-select-9"] input').setValue(true);
    await wrapper.find('[data-testid="document-observation-select-10"] input').setValue(true);

    await wrapper.find('[data-testid="document-observation-bulk-delete"]').trigger('click');
    await wrapper.find('[data-testid="document-observation-confirm-delete"]').trigger('click');
    await flushPromises();

    expect(store.bulkDeleteNotes).toHaveBeenCalledWith(8, [9, 10]);
  });

  it('restores a note from the trash', async () => {
    const store = useDocumentStateStore();
    jest.spyOn(store, 'fetchDeletedNotes').mockResolvedValue({
      success: true,
      data: [{
        id: 9,
        title: 'Recuperable',
        content: 'Volver a mostrar',
        status: 'open',
        order: 0,
        deleted_at: '2026-08-26T12:00:00Z',
        deleted_by_name: 'Ana',
      }],
    });
    jest.spyOn(store, 'restoreNote').mockResolvedValue({
      success: true,
      data: { note: { id: 9, title: 'Recuperable', content: 'Volver a mostrar', status: 'open', order: 0 } },
    });
    const wrapper = mountModal({ documentId: 8, notes: [] });

    await wrapper.find('[data-testid="document-observation-tab-trash"]').trigger('click');
    await flushPromises();
    await wrapper.find('[data-testid="document-observation-restore-9"]').trigger('click');
    await flushPromises();

    expect(store.restoreNote).toHaveBeenCalledWith(8, 9);
    expect(wrapper.text()).toContain('La papelera está vacía');
  });
});
