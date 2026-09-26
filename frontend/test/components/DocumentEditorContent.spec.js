import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent, ref } from 'vue';

import DocumentEditorContent from '../../components/panel/documents/DocumentEditorContent.vue';
import BaseSegmented from '../../components/base/BaseSegmented.vue';

const CONTRACT = '# Contrato\n\nEste es el contenido del contrato.';
const mountedWrappers = [];

// The page owns the markdown through v-model and reaches insertAtCursor from
// its own "Pegar" tool, the same wiring the document editor uses.
function mountEditor(initialMarkdown = CONTRACT) {
  const Harness = defineComponent({
    components: { DocumentEditorContent },
    setup() {
      const markdown = ref(initialMarkdown);
      const editor = ref(null);
      return { markdown, editor };
    },
    template: `
      <DocumentEditorContent
        ref="editor"
        v-model="markdown"
        textarea-id="edit-markdown"
        label="Contenido Markdown"
        theme="professional"
      >
        <template #tools>
          <button type="button" data-testid="paste-tool" @click="editor.insertAtCursor(' querido')">Pegar</button>
        </template>
      </DocumentEditorContent>
    `,
  });
  const wrapper = mount(Harness, {
    attachTo: document.body,
    global: { components: { BaseSegmented } },
  });
  mountedWrappers.push(wrapper);
  return wrapper;
}

const textarea = (wrapper) => wrapper.get('#edit-markdown');
const previewPane = (wrapper) => wrapper.find('[data-testid="doc-markdown-preview-pane"]');
const viewTab = (wrapper, view) => wrapper.get(`[data-testid="doc-editor-view-${view}"]`);

// jsdom caches computed styles across v-show toggles, so the inline style is
// the observable switch here; the real layout belongs to the E2E specs.
const isHidden = (element) => element.style.display === 'none';

describe('DocumentEditorContent', () => {
  afterEach(() => {
    mountedWrappers.splice(0).forEach((wrapper) => wrapper.unmount());
  });

  it('opens on the editor with the markdown and its size', () => {
    const wrapper = mountEditor();

    expect(textarea(wrapper).element.value).toBe(CONTRACT);
    expect(isHidden(textarea(wrapper).element)).toBe(false);
    expect(wrapper.get('label[for="edit-markdown"]').text()).toBe('Contenido Markdown');
    expect(viewTab(wrapper, 'edit').attributes('aria-selected')).toBe('true');
    expect(wrapper.text()).toContain(`${CONTRACT.length} caracteres`);
    expect(previewPane(wrapper).exists()).toBe(false);
  });

  it('shows the preview in the place of the editor', async () => {
    const wrapper = mountEditor();

    await viewTab(wrapper, 'preview').trigger('click');
    await flushPromises();

    expect(isHidden(textarea(wrapper).element)).toBe(true);
    expect(viewTab(wrapper, 'preview').attributes('aria-selected')).toBe('true');
    expect(previewPane(wrapper).get('.md-h1').text()).toBe('Contrato');
    expect(previewPane(wrapper).get('.markdown-preview').classes())
      .toContain('markdown-preview--professional');
  });

  it('returns to the editor with the text intact', async () => {
    const wrapper = mountEditor();
    await viewTab(wrapper, 'preview').trigger('click');

    await viewTab(wrapper, 'edit').trigger('click');

    expect(isHidden(textarea(wrapper).element)).toBe(false);
    expect(textarea(wrapper).element.value).toBe(CONTRACT);
    expect(previewPane(wrapper).exists()).toBe(false);
  });

  it('previews the markdown that was just typed', async () => {
    const wrapper = mountEditor('');
    await textarea(wrapper).setValue('# Propuesta');

    await viewTab(wrapper, 'preview').trigger('click');
    await flushPromises();

    expect(previewPane(wrapper).get('.md-h1').text()).toBe('Propuesta');
    expect(wrapper.text()).toContain('11 caracteres');
  });

  it('explains an empty preview', async () => {
    const wrapper = mountEditor('');

    await viewTab(wrapper, 'preview').trigger('click');

    expect(previewPane(wrapper).text()).toBe('Escribe markdown para ver la vista previa...');
  });

  it('pastes at the caret and brings the editor back from the preview', async () => {
    const wrapper = mountEditor('Hola mundo');
    textarea(wrapper).element.setSelectionRange(4, 4);
    await viewTab(wrapper, 'preview').trigger('click');

    await wrapper.get('[data-testid="paste-tool"]').trigger('click');
    await flushPromises();

    const field = textarea(wrapper).element;
    expect(field.value).toBe('Hola querido mundo');
    expect(isHidden(field)).toBe(false);
    expect(viewTab(wrapper, 'edit').attributes('aria-selected')).toBe('true');
    expect(document.activeElement).toBe(field);
    expect(field.selectionStart).toBe('Hola querido'.length);
  });
});
