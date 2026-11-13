import { defineComponent } from 'vue';
import { mount } from '@vue/test-utils';
import fixture from '../../../docs/fixtures/pa257-requirements.json';
import LinkedRequirementsModal from '../../components/BusinessProposal/LinkedRequirementsModal.vue';
import { buildItemRequirementsMap } from '../../utils/itemRequirementLinks';

jest.mock('../../composables/useProposalDarkMode', () => ({
  useProposalDarkMode: () => ({ isDark: require('vue').ref(false) }),
}));

const RichTextStub = defineComponent({
  name: 'BaseRichTextContent',
  props: ['source', 'format'],
  template: '<p data-testid="rendered-requirement-text" :data-format="format">{{ source }}</p>',
});

const BaseButtonStub = defineComponent({
  name: 'BaseButton',
  emits: ['click'],
  template: '<button type="button" @click="$emit(\'click\')"><slot /></button>',
});

function requirementsFor(language) {
  const technical = JSON.parse(JSON.stringify(fixture[language].technicalDocument));
  technical.epics[0].requirements[0].text_formats = {
    '/description': 'markdown_html_v1',
    '/configuration': 'markdown_html_v1',
    '/usageFlow': 'plain',
  };
  technical.epics[0].requirements[1].text_formats = {
    '/description': 'plain',
    '/configuration': 'plain',
    '/usageFlow': 'markdown_html_v1',
  };
  return buildItemRequirementsMap(technical)['pa257-register'];
}

function renderModal(language) {
  return mount(LinkedRequirementsModal, {
    props: {
      visible: true,
      item: fixture[language].functionalRequirements.groups[0].items[0],
      requirements: requirementsFor(language),
      language,
    },
    global: {
      components: { BaseRichTextContent: RichTextStub, BaseButton: BaseButtonStub },
      stubs: { teleport: true, transition: false },
    },
  });
}

describe('LinkedRequirementsModal detail fields', () => {
  // Falla si el detalle técnico o el flujo de uso del requisito se omite al abrir el vínculo español.
  it('renders Spanish configuration and usage flow with their declared formats', () => {
    const wrapper = renderModal('es');
    const firstRequirement = wrapper.findAll('[data-testid="linked-requirement"]')[0];

    expect(wrapper.findAll('[data-testid="linked-requirement"]')).toHaveLength(2);
    expect(firstRequirement.get('[data-testid="linked-requirement-configuration"]').text())
      .toBe('Detalle técnicoValidar correo único y contraseña en servidor.');
    expect(firstRequirement.get('[data-testid="linked-requirement-usage-flow"]').text())
      .toBe('Flujo de usoCompletar campos → enviar → recibir cuenta.');
    expect(firstRequirement.findAll('[data-testid="rendered-requirement-text"]').map((node) => node.text()))
      .toEqual(['Validar datos de registro', 'Validar correo único y contraseña en servidor.', 'Completar campos → enviar → recibir cuenta.']);
    expect(firstRequirement.findAll('[data-testid="rendered-requirement-text"]').map((node) => node.attributes('data-format')))
      .toEqual(['markdown_html_v1', 'markdown_html_v1', 'plain']);
    expect(wrapper.findAll('[data-testid="rendered-requirement-text"]').map((node) => node.attributes('data-format')))
      .toEqual(['markdown_html_v1', 'markdown_html_v1', 'plain', 'plain', 'plain', 'markdown_html_v1']);
  });

  // Falla si el vínculo inglés usa textos o encabezados españoles para los campos técnicos.
  it('renders English configuration and usage flow from the linked requirement', () => {
    const wrapper = renderModal('en');
    const firstRequirement = wrapper.findAll('[data-testid="linked-requirement"]')[0];

    expect(wrapper.findAll('[data-testid="linked-requirement"]')).toHaveLength(2);
    expect(firstRequirement.get('[data-testid="linked-requirement-configuration"]').text())
      .toBe('Technical detailValidate unique email and password on the server.');
    expect(firstRequirement.get('[data-testid="linked-requirement-usage-flow"]').text())
      .toBe('Usage flowFill fields → submit → receive account.');
    expect(firstRequirement.findAll('[data-testid="rendered-requirement-text"]').map((node) => node.text()))
      .toEqual(['Validate registration data', 'Validate unique email and password on the server.', 'Fill fields → submit → receive account.']);
  });

  // Falla si el botón de cerrar deja el modal sin comunicar al padre que debe ocultarlo.
  it('emits close from the modal close button', async () => {
    const wrapper = renderModal('es');
    const closeButton = wrapper.findAll('button').find((button) => button.attributes('aria-label') === 'Cerrar requerimientos vinculados');

    await closeButton.trigger('click');

    expect(wrapper.emitted('close')).toEqual([[]]);
  });
});
