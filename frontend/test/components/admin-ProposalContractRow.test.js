jest.mock('#imports', () => ({
  ...jest.requireActual('#imports'),
  useI18n: () => ({ t: (key) => {
    const messages = jest.requireActual('../../locales/pwa/es').default;
    return key.split('.').slice(1).reduce((value, part) => value?.[part], messages) || key;
  } }),
}));

import { mount } from '@vue/test-utils';

jest.mock('~/stores/services/request_http', () => ({ get_request: jest.fn() }));

import ProposalContractRow from '../../components/BusinessProposal/admin/ProposalContractRow.vue';
import { CONTRACT_VARIANTS } from '~/stores/proposals_constants';
import { get_request } from '~/stores/services/request_http';

const proposal = { id: 7 };
const doc = {
  id: 30, document_type: 'contract_service', file: '/media/servicio.pdf',
  created_at: '2026-09-26T10:00:00Z', updated_at: '2026-09-26T10:00:00Z',
};

function mountRow(props) {
  return mount(ProposalContractRow, {
    props: { proposal, variant: CONTRACT_VARIANTS.combined, doc: null, ...props },
  });
}

describe('ProposalContractRow', () => {
  it('keeps the historical URLs and copy action of the single contract', () => {
    // Falla si el contrato único cambia las rutas que usan descargas y pruebas existentes.
    const wrapper = mountRow({ doc: { ...doc, document_type: 'contract' } });
    const links = wrapper.findAll('a').map(link => link.attributes('href'));

    expect(links).toEqual(['/api/proposals/7/contract/pdf/', '/api/proposals/7/contract/draft-pdf/']);
    expect(wrapper.find('[data-testid="proposal-copy-contract"]').exists()).toBe(true);
  });

  it('names the separate document in every URL it serves', async () => {
    // Falla si el contrato de servicio descarga o copia el documento equivocado.
    get_request.mockResolvedValueOnce({ data: { markdown: 'contenido del contrato' } });
    const wrapper = mountRow({ variant: CONTRACT_VARIANTS.service, doc });
    const links = wrapper.findAll('a').map(link => link.attributes('href'));

    expect(wrapper.text()).toContain('Hosting, mantenimiento y soporte');
    expect(links).toEqual([
      '/api/proposals/7/contract/pdf/?variant=service',
      '/api/proposals/7/contract/draft-pdf/?variant=service',
    ]);

    await wrapper.get('[data-testid="proposal-copy-contract-service"]').trigger('click');

    expect(get_request).toHaveBeenCalledWith('proposals/7/contract/markdown/?variant=service', expect.anything());
  });

  it('asks the tab to preview and edit its own document', async () => {
    // Falla si la vista previa o la edición apuntan al documento equivocado.
    const wrapper = mountRow({ variant: CONTRACT_VARIANTS.service, doc });

    await wrapper.get('button[aria-label="Vista previa del contrato de servicio"]').trigger('click');
    await wrapper.findAll('button').find(button => button.text() === 'Editar parámetros').trigger('click');

    expect(wrapper.emitted('preview')).toEqual([
      ['Contrato de servicio', '/api/proposals/7/contract/pdf/?variant=service'],
    ]);
    expect(wrapper.emitted('edit')).toHaveLength(1);
  });

  it('hides generation while the contract is locked', () => {
    // Falla si una propuesta enviada o vista ofrece generar un contrato antes de negociar.
    const wrapper = mountRow({ variant: CONTRACT_VARIANTS.product, actionsDisabled: true });

    expect(wrapper.text()).toContain('PDF · No generado');
    expect(wrapper.find('[data-testid="proposal-generate-contract-product"]').exists()).toBe(false);
  });
});
