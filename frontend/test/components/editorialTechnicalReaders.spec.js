import { mount } from '@vue/test-utils';
import { nextTick } from 'vue';
import BaseRichTextContent from '../../components/base/BaseRichTextContent.vue';
import TechnicalDocumentPublicPanel from '../../components/BusinessProposal/TechnicalDocumentPublicPanel.vue';

jest.mock('../../composables/useSectionAnimations', () => ({ useSectionAnimations: jest.fn() }));
const wrappers = [];
afterEach(() => { wrappers.splice(0).forEach(wrapper => wrapper.unmount()); });
async function render(fragment, contentJson) {
  const wrapper = mount(TechnicalDocumentPublicPanel, {
    props: { fragment, contentJson },
    global: { components: { BaseRichTextContent }, stubs: { Teleport: true } },
  });
  wrappers.push(wrapper);
  await nextTick();
  return wrapper;
}

// Computed prose must retain the metadata of its original JSON field.
it.each([
  ['growthReadiness', { growthReadiness: { summary: '**Capacity**', text_formats: { '/summary': 'markdown_html_v1' } } }],
  ['architecture', { architecture: { diagramNote: '**Capacity**', text_formats: { '/diagramNote': 'markdown_html_v1' } } }],
  ['environments', { environmentsNote: '**Capacity**', text_formats: { '/environmentsNote': 'markdown_html_v1' } }],
  ['backups', { backupsNote: '**Capacity**', text_formats: { '/backupsNote': 'markdown_html_v1' } }],
  ['quality', { quality: { criticalFlowsNote: '**Capacity**', text_formats: { '/criticalFlowsNote': 'markdown_html_v1' } } }],
])('renders the declared format in the %s technical fragment', async (fragment, contentJson) => {
  const wrapper = await render(fragment, contentJson);

  expect(wrapper.get('strong').text()).toBe('Capacity');
});

// Splitting a rich note by physical lines would turn its table into broken fragments.
it('keeps a formatted integration note table intact', async () => {
  const wrapper = await render('integrations', {
    integrations: { notes: '| Phase |\n| --- |\n| Ready |', text_formats: { '/notes': 'markdown_html_v1' } },
  });

  expect(wrapper.get('.editorial-content table th').text()).toBe('Phase');
  expect(wrapper.get('.editorial-content table td').text()).toBe('Ready');
});
