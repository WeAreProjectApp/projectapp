import { flushPromises, mount } from '@vue/test-utils';
import EmailLogTable from '~/components/accounting/EmailLogTable.vue';

// The row menu is a BaseModal; rendered inline so its entries can be queried.
const MenuModalStub = {
  props: ['modelValue', 'kind', 'titleId', 'lockScroll'],
  emits: ['close'],
  template: '<div v-if="modelValue" :data-lock-scroll="String(lockScroll)"><slot /></div>',
};

const SENT = {
  id: 1,
  template_key: 'accounting_change',
  template_label: 'Cambio contable',
  recipient: 'ana@test.com',
  subject: '[Contabilidad] Hosting creado: Kore',
  status: 'sent',
  status_label: 'Enviado',
  error_message: '',
  sent_at: '2026-08-15T09:00:00-05:00',
  targets: [
    {
      entity_type: 'hosting',
      entity_type_label: 'Hosting',
      object_id: 4,
      object_repr: 'Kore',
    },
  ],
  has_body: true,
  is_retryable: false,
  retry_blocked_reason: '',
  retry_of: null,
  copies: [],
};

const FAILED = {
  ...SENT,
  id: 2,
  recipient: 'zoe@test.com',
  status: 'failed',
  status_label: 'Fallido',
  error_message: 'SMTP timeout',
  has_body: false,
  is_retryable: true,
};

const DIGEST_FAILED = {
  ...FAILED,
  id: 3,
  template_key: 'accounting_payment_calendar',
  template_label: 'Calendario de cobros y pagos',
  is_retryable: false,
  retry_blocked_reason: 'Este aviso resume varios registros del día.',
};

const wrappers = [];

function mountTable(entries, props = {}) {
  const wrapper = mount(EmailLogTable, {
    props: { entries, ...props },
    global: { stubs: { BaseModal: MenuModalStub } },
  });
  wrappers.push(wrapper);
  return wrapper;
}

async function openMenu(wrapper, id) {
  await wrapper.get(`[data-testid="email-log-actions-${id}"]`).trigger('click');
  return wrapper.get('[data-testid="email-log-actions-modal"]');
}

describe('EmailLogTable', () => {
  afterEach(() => {
    wrappers.splice(0).forEach(wrapper => wrapper.unmount());
    document.body.innerHTML = '';
  });

  it('contains unbroken labels, recipients and subjects in their columns', () => {
    const wrapper = mountTable([{
      ...SENT,
      template_label: 'Respuesta_Etapa_3_Inventario',
      recipient: 'guia_apuntar_dominio_ux_26082026@example.com',
      subject: 'Levantamiento_Fase_4_Multi-Tenant_24082026',
    }]);
    const row = wrapper.get('[data-testid="email-log-row-1"]');

    for (const field of ['notice', 'recipient', 'subject']) {
      expect(row.get(`[data-field="${field}"] span:last-child`).classes())
        .toContain('[overflow-wrap:anywhere]');
    }
  });

  it('offers the message only for the sends that kept one', async () => {
    const wrapper = mountTable([SENT, FAILED]);

    expect((await openMenu(wrapper, 1)).find('[data-testid="email-log-view-body-1"]').exists())
      .toBe(true);
    expect((await openMenu(wrapper, 2)).find('[data-testid="email-log-view-body-2"]').exists())
      .toBe(false);
  });

  it('emits the row when the message is opened from its menu', async () => {
    const wrapper = mountTable([SENT]);

    const menu = await openMenu(wrapper, 1);
    await menu.get('[data-testid="email-log-view-body-1"]').trigger('click');
    await flushPromises();

    expect(wrapper.emitted('view-body')[0]).toEqual([SENT]);
  });

  it('offers a retry only on a failure', async () => {
    const wrapper = mountTable([SENT, FAILED]);

    expect((await openMenu(wrapper, 1)).find('[data-testid="email-log-retry-1"]').exists())
      .toBe(false);
    expect((await openMenu(wrapper, 2)).find('[data-testid="email-log-retry-2"]').exists())
      .toBe(true);
  });

  it('shows the digest retry disabled, carrying its visible reason', async () => {
    const wrapper = mountTable([DIGEST_FAILED]);

    const menu = await openMenu(wrapper, 3);
    const retry = menu.get('[data-testid="email-log-retry-3"]');

    // Disabled and explained, rather than absent: a missing entry reads as
    // "this failure cannot be acted on" without saying why.
    expect(retry.attributes('disabled')).toBe('');
    expect(menu.get(`#${retry.attributes('aria-describedby')}`).text())
      .toContain('resume varios registros');
  });

  it('blocks a second retry while one is in flight', () => {
    const wrapper = mountTable([FAILED], { retryingId: 2 });

    expect(wrapper.get('[data-testid="email-log-actions-2"]').attributes('disabled')).toBe('');
  });

  // Bug caught: the menu cell sits inside a row that expands on click.
  it('keeps the row collapsed when its menu opens', async () => {
    const wrapper = mountTable([FAILED]);

    await openMenu(wrapper, 2);

    expect(wrapper.find('[data-testid="email-log-detail-2"]').exists()).toBe(false);
    expect(wrapper.get('[data-testid="email-log-actions-modal"]').text()).toContain('zoe@test.com');
  });

  it('shows no kebab on a send with nothing to do', () => {
    const wrapper = mountTable([SENT, { ...SENT, id: 4, has_body: false }]);

    expect(wrapper.find('[data-testid="email-log-actions-1"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="email-log-actions-4"]').exists()).toBe(false);
  });

  it('tells its host while the row menu is open', async () => {
    const wrapper = mountTable([SENT], { nested: true });

    const menu = await openMenu(wrapper, 1);
    expect(wrapper.get('[data-lock-scroll]').attributes('data-lock-scroll')).toBe('false');
    await menu.get('[data-testid="base-modal-actions"] button').trigger('click');

    expect(wrapper.emitted('menu-open-change')).toEqual([[true], [false]]);
  });

  it('names the records the email was about when the row is expanded', async () => {
    const wrapper = mountTable([SENT]);

    await wrapper.get('[data-testid="email-log-row-1"]').trigger('click');

    const detail = wrapper.get('[data-testid="email-log-detail-1"]');
    expect(detail.text()).toContain('Hosting: Kore');
  });

  it('still shows the failure reason it always showed', async () => {
    const wrapper = mountTable([FAILED]);

    await wrapper.get('[data-testid="email-log-row-2"]').trigger('click');

    expect(wrapper.get('[data-testid="email-log-detail-2"]').text())
      .toContain('SMTP timeout');
  });

  it('points a retry back at what it retried', async () => {
    const wrapper = mountTable([{ ...SENT, id: 9, retry_of: 2, targets: [] }]);

    await wrapper.get('[data-testid="email-log-row-9"]').trigger('click');

    expect(wrapper.get('[data-testid="email-log-detail-9"]').text())
      .toContain('Reintento del envío #2');
  });

  it('does not expand a row that has nothing more to say', async () => {
    const wrapper = mountTable([{ ...SENT, targets: [], error_message: '' }]);

    await wrapper.get('[data-testid="email-log-row-1"]').trigger('click');

    expect(wrapper.find('[data-testid="email-log-detail-1"]').exists()).toBe(false);
  });

  it('shows BCC delivery status after expanding the primary row', async () => {
    const entry = {
      ...SENT,
      targets: [],
      copies: [{
        id: 21,
        recipient: 'audit@example.com',
        status: 'sent',
        status_label: 'Enviado',
        error_message: '',
      }],
    };
    const wrapper = mountTable([entry]);

    await wrapper.get('[data-testid="email-log-row-1"]').trigger('click');

    expect(wrapper.get('[data-testid="email-log-copies-1"]').text())
      .toContain('audit@example.com');
  });
});
