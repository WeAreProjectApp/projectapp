import { mount } from '@vue/test-utils';

jest.mock('../../composables/useSectionAnimations', () => ({
  useSectionAnimations: jest.fn(),
}));

jest.mock('canvas-confetti', () => jest.fn());

global.useProposalStore = jest.fn(() => ({
  respondToProposal: jest.fn().mockResolvedValue({ success: true }),
  commentOnProposal: jest.fn().mockResolvedValue({ success: true }),
  scheduleFollowup: jest.fn().mockResolvedValue({ success: true }),
}));

import ProposalClosing from '../../components/BusinessProposal/ProposalClosing.vue';

const sentProposal = {
  uuid: 'test-uuid-123',
  status: 'sent',
  title: 'Test Proposal',
  total_investment: 1490000,
  currency: 'COP',
};

function mountProposalClosing(props = {}) {
  return mount(ProposalClosing, {
    props: { proposal: sentProposal, ...props },
    global: {
      stubs: {
        Teleport: { template: '<div><slot /></div>' },
        Transition: true,
      },
    },
  });
}

describe('ProposalClosing', () => {
  it('renders the section element', () => {
    const wrapper = mountProposalClosing();

    expect(wrapper.find('section').exists()).toBe(true);
  });

  it('renders the accept button when proposal status is sent', () => {
    const wrapper = mountProposalClosing();

    const acceptBtn = wrapper.findAll('button').find(b => b.text().includes('Acepto'));
    expect(acceptBtn.text()).toBe('Acepto la propuesta');
  });

  it('renders the validity notice when validityMessage is provided', () => {
    const wrapper = mountProposalClosing({ validityMessage: 'Esta propuesta es válida por 30 días.' });

    expect(wrapper.text()).toContain('Esta propuesta es válida por 30 días.');
  });

  it('prefers the server-computed validity_text over validityMessage', () => {
    const wrapper = mountProposalClosing({
      proposal: {
        ...sentProposal,
        validity_text:
          'Esta propuesta tiene una vigencia de 21 días calendario a partir '
          + 'de su fecha de envío (válida hasta el 6 de agosto de 2026).',
      },
      validityMessage: 'mensaje legacy que no debe mostrarse',
    });

    const text = wrapper.text();
    expect(text).toContain('vigencia de 21 días calendario');
    expect(text).toContain('válida hasta el 6 de agosto de 2026');
    expect(text).not.toContain('mensaje legacy');
  });

  it('renders the thank you message when provided', () => {
    const wrapper = mountProposalClosing({ thankYouMessage: '¡Gracias por revisar nuestra propuesta!' });

    expect(wrapper.text()).toContain('¡Gracias por revisar nuestra propuesta!');
  });

  it('does not render accept button when proposal status is accepted', () => {
    const wrapper = mountProposalClosing({
      proposal: { ...sentProposal, status: 'accepted' },
    });

    const acceptBtn = wrapper.findAll('button').find(b => b.text().includes('Acepto la propuesta'));
    expect(acceptBtn).toBeFalsy();
  });

  it('renders the ready message in the final panel', () => {
    const wrapper = mountProposalClosing({ ctaMessage: 'Podemos activar el kickoff.' });

    const readyBlock = wrapper.find('[data-testid="proposal-ready-contact"]');
    expect(readyBlock.text()).toContain('¿Listo para comenzar?');
    expect(readyBlock.text()).toContain('Podemos activar el kickoff.');
  });

  it('renders the configured primary CTA', () => {
    const wrapper = mountProposalClosing({
      primaryCTA: { text: 'Escribir por WhatsApp', link: 'https://wa.me/123' },
    });

    expect(wrapper.find('a[href="https://wa.me/123"]').text()).toBe('Escribir por WhatsApp');
  });

  it('renders the configured contact methods', () => {
    const wrapper = mountProposalClosing({
      contactMethods: [{ icon: '✉️', title: 'Email', value: 'team@projectapp.co', link: 'mailto:team@projectapp.co' }],
    });

    expect(wrapper.find('a[href="mailto:team@projectapp.co"]').text()).toContain('team@projectapp.co');
  });

  it('shows IVA on the closing total', () => {
    const wrapper = mountProposalClosing({
      paymentOptions: [
        { label: '40% al inicio', description: '$112.000.000 COP' },
      ],
    });

    expect(wrapper.text()).toMatch(/\$1\.490\.000\s*COP\s*\+ IVA/);
  });

  test.each([
    ['the supplied agreed investment', 2750000, /\$2\.750\.000\s*COP\s*\+ IVA/],
    ['the proposal investment when no agreed total is supplied', null, /\$1\.490\.000\s*COP\s*\+ IVA/],
  ])('shows %s in the closing payment total', (_source, investmentTotal, expectedTotal) => {
    // Falla si el cierre deja vacío el total acordado o vuelve a mostrar un cálculo retirado.
    const wrapper = mountProposalClosing({
      investmentTotal,
      paymentOptions: [{ label: '40% al inicio', description: '$1.100.000 COP + IVA' }],
    });

    expect(wrapper.text()).toMatch(expectedTotal);
  });

  it('shows IVA on every 40/30/30 payment', () => {
    const wrapper = mountProposalClosing({
      paymentOptions: [
        { label: '40% al inicio', description: '$112.000.000 COP' },
        { label: '30% al aprobar QA', description: '$84.000.000 COP + IVA' },
        { label: '30% al desplegar', description: '$84.000.000 COP' },
      ],
    });

    const text = wrapper.text();
    expect(text).toContain('$112.000.000 COP + IVA');
    expect(text.match(/\$84\.000\.000 COP \+ IVA/g)).toHaveLength(2);
  });
});

// ── Modal flows (additions) ──────────────────────────────────────────────────

async function flushPromises() {
  await Promise.resolve();
  await Promise.resolve();
}

const mockProposalActions = {
  respondToProposal: jest.fn(),
  commentOnProposal: jest.fn(),
  scheduleFollowup: jest.fn(),
};

describe('ProposalClosing modal flows', () => {
  beforeEach(() => {
    mockProposalActions.respondToProposal.mockReset().mockResolvedValue({ success: true });
    mockProposalActions.commentOnProposal.mockReset().mockResolvedValue({ success: true });
    mockProposalActions.scheduleFollowup.mockReset().mockResolvedValue({ success: true });
    global.useProposalStore = jest.fn(() => mockProposalActions);
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  // ── Accept confirm modal ──────────────────────────────────────────────────

  it('opens the accept confirm modal when the accept button is clicked', async () => {
    const wrapper = mountProposalClosing();
    const acceptBtn = wrapper.findAll('button').find(b => b.text().includes('Acepto la propuesta'));
    await acceptBtn.trigger('click');

    expect(wrapper.text()).toContain('¡Perfecto');
  });

  it('calls respondToProposal with accepted when the confirm button is clicked', async () => {
    const wrapper = mountProposalClosing();
    await wrapper.findAll('button').find(b => b.text().includes('Acepto la propuesta')).trigger('click');
    await wrapper.findAll('button').find(b => b.text() === '¡Confirmar!').trigger('click');
    await flushPromises();

    expect(mockProposalActions.respondToProposal).toHaveBeenCalledWith(
      sentProposal.uuid,
      'accepted',
      expect.any(Object)
    );
  });

  // ── Negotiate modal ───────────────────────────────────────────────────────

  it('opens the negotiate modal when the Necesito ajustes button is clicked', async () => {
    const wrapper = mountProposalClosing();
    await wrapper.findAll('button').find(b => b.text().includes('Necesito ajustes')).trigger('click');

    expect(wrapper.text()).toContain('negociemos alcance');
  });

  it('calls respondToProposal with negotiating when the negotiate form is submitted', async () => {
    const wrapper = mountProposalClosing();
    await wrapper.findAll('button').find(b => b.text().includes('Necesito ajustes')).trigger('click');

    await wrapper.find('textarea').setValue('Quiero reducir el alcance');
    const submitBtn = wrapper.findAll('button').find(b => b.text().includes('Enviar solicitud'));
    await submitBtn.trigger('click');
    await flushPromises();

    expect(mockProposalActions.respondToProposal).toHaveBeenCalledWith(
      sentProposal.uuid,
      'negotiating',
      expect.any(Object)
    );
  });

  // ── Comment modal ─────────────────────────────────────────────────────────

  it('opens the comment modal when the Tengo comentarios button is clicked', async () => {
    const wrapper = mountProposalClosing();
    await wrapper.findAll('button').find(b => b.text().includes('Tengo comentarios')).trigger('click');

    expect(wrapper.text()).toContain('Enviar mensaje');
  });

  it('calls commentOnProposal when the comment is submitted', async () => {
    const wrapper = mountProposalClosing();
    await wrapper.findAll('button').find(b => b.text().includes('Tengo comentarios')).trigger('click');

    const textareas = wrapper.findAll('textarea');
    await textareas[textareas.length - 1].setValue('Tengo una duda sobre el alcance');
    const sendBtn = wrapper.findAll('button').find(b => b.text() === 'Enviar mensaje');
    await sendBtn.trigger('click');
    await flushPromises();

    expect(mockProposalActions.commentOnProposal).toHaveBeenCalledWith(
      sentProposal.uuid,
      'Tengo una duda sobre el alcance',
    );
  });

  // ── Reject modal ──────────────────────────────────────────────────────────

  it('opens the reject modal when the No es el momento button is clicked', async () => {
    const wrapper = mountProposalClosing();
    await wrapper.findAll('button').find(b => b.text().includes('No es el momento')).trigger('click');

    expect(wrapper.text()).toContain('Lamentamos que no sea el momento');
  });

  it('calls respondToProposal with rejected when the reject form is confirmed', async () => {
    const wrapper = mountProposalClosing();
    await wrapper.findAll('button').find(b => b.text().includes('No es el momento')).trigger('click');

    await wrapper.findAll('button').find(b => b.text() === 'Confirmar rechazo').trigger('click');
    await flushPromises();

    expect(mockProposalActions.respondToProposal).toHaveBeenCalledWith(
      sentProposal.uuid,
      'rejected',
      expect.any(Object)
    );
  });

  // ── Payment milestones ────────────────────────────────────────────────────

  it('renders payment milestones when proposal has payment_options with milestones', () => {
    const wrapper = mountProposalClosing({
      proposal: {
        ...sentProposal,
        payment_options: {
          milestones: [
            { label: 'Pago inicial', amount: '$500.000' },
            { label: 'Entrega final', amount: '$990.000' },
          ],
        },
      },
    });

    expect(wrapper.text()).toContain('Pago inicial');
    expect(wrapper.text()).toContain('Entrega final');
  });

  it('adds IVA to payment milestone amounts', () => {
    const wrapper = mountProposalClosing({
      proposal: {
        ...sentProposal,
        payment_options: {
          milestones: [
            { label: 'Pago inicial', amount: '$500.000' },
            { label: 'Entrega final', amount: '$990.000' },
          ],
        },
      },
    });

    expect(wrapper.text()).toContain('$500.000 + IVA');
    expect(wrapper.text()).toContain('$990.000 + IVA');
  });

  // ── WhatsApp link ─────────────────────────────────────────────────────────

  it('renders the WhatsApp link when whatsappLink prop is provided', () => {
    const wrapper = mountProposalClosing({ whatsappLink: 'https://wa.me/123?text=hello' });

    const link = wrapper.find('a[href="https://wa.me/123?text=hello"]');
    expect(link.exists()).toBe(true);
  });
});
