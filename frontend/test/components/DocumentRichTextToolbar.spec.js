import { mount } from '@vue/test-utils';
import { nextTick } from 'vue';
import BaseRichTextEditor from '~/components/base/BaseRichTextEditor.vue';
import BaseSegmented from '~/components/base/BaseSegmented.vue';

const wrappers = [];

function mountDocumentEditor(modelValue = 'Agenda') {
  const wrapper = mount(BaseRichTextEditor, {
    props: { modelValue, toolbarVariant: 'document' },
    attachTo: document.body,
    global: { components: { BaseSegmented } },
  });
  wrappers.push(wrapper);
  return wrapper;
}

function sourceTab(wrapper) {
  return wrapper.findAll('[role="tab"]').find((tab) => tab.text() === 'richText.source');
}

async function chooseInsertItem(wrapper, label) {
  await wrapper.get('[data-testid="document-insert-menu"]').trigger('click');
  await nextTick();
  await wrapper.findAll('[role="menuitem"]').find((item) => item.text() === label).trigger('click');
  await nextTick();
}

const insertTable = (wrapper) => chooseInsertItem(wrapper, 'richText.table');
const openLink = async (wrapper) => {
  await wrapper.get('[aria-label="richText.link"]').trigger('click');
  await nextTick();
};
async function selectExistingLink(wrapper) {
  const visual = wrapper.get('[data-testid="rich-text-visual-input"]').element;
  const link = visual.querySelector('a');
  const range = document.createRange();
  range.selectNodeContents(link);
  visual.focus();
  window.getSelection().removeAllRanges();
  window.getSelection().addRange(range);
  document.dispatchEvent(new Event('selectionchange'));
  await nextTick();
}

beforeEach(() => {
  global.useI18n = () => ({ t: (key) => key });
});

afterEach(() => {
  wrappers.splice(0).forEach((wrapper) => wrapper.unmount());
  window.getSelection().removeAllRanges();
  delete global.useI18n;
});

describe('Document rich text toolbar', () => {
  // Catches the document heading control changing visual state without persisting a Markdown heading.
  it('serializes the selected heading level into source', async () => {
    const wrapper = mountDocumentEditor();
    await nextTick();

    await wrapper.get('[aria-label="richText.heading"]').setValue('2');
    await sourceTab(wrapper).trigger('click');

    expect(wrapper.get('[data-testid="rich-text-source-input"]').element.value).toBe('## Agenda');
  });

  // Catches the Insert menu bypassing the document editor serializer for a table.
  it('serializes a table inserted from the document menu', async () => {
    const wrapper = mountDocumentEditor();
    await nextTick();

    await insertTable(wrapper);
    await sourceTab(wrapper).trigger('click');

    expect(wrapper.get('[data-testid="rich-text-source-input"]').element.value).toBe('Agenda\n\n| <p></p> | <p></p> | <p></p> |\n| --- | --- | --- |\n| <p></p> | <p></p> | <p></p> |\n| <p></p> | <p></p> | <p></p> |');
  });

  // Catches the table controls presenting an executable merge or split outside a compatible selection.
  it.each([
    ['richText.mergeCells', 'richText.selectCells'],
    ['richText.splitCell', 'richText.contextSelection'],
  ])('explains the unavailable %s command', async (command, reason) => {
    const wrapper = mountDocumentEditor();
    await nextTick();

    await insertTable(wrapper);
    const button = wrapper.findAll('button').find((candidate) => candidate.text() === command);

    expect(button.element.disabled).toBe(true);
    expect(button.attributes('title')).toBe(reason);
  });

  // Catches unsafe URLs replacing a document link before the user can correct the address.
  it('keeps an existing link after rejecting an unsafe replacement', async () => {
    const wrapper = mountDocumentEditor('[ProjectApp](https://old.example)');
    await nextTick();

    await selectExistingLink(wrapper);
    await openLink(wrapper);
    await wrapper.get('[aria-label="richText.linkUrl"]').setValue('javascript:alert(1)');
    await wrapper.findAll('button').find((button) => button.text() === 'richText.apply').trigger('click');

    expect(wrapper.get('[role="alert"]').text()).toBe('richText.invalidLink');
    await sourceTab(wrapper).trigger('click');

    expect(wrapper.get('[data-testid="rich-text-source-input"]').element.value).toBe('[ProjectApp](https://old.example)');
  });

  // Catches the link dialog forcing staff to retype an already saved address before editing it.
  it('preloads the existing link address', async () => {
    const wrapper = mountDocumentEditor('[ProjectApp](https://old.example)');
    await nextTick();

    await selectExistingLink(wrapper);
    await openLink(wrapper);

    expect(wrapper.get('[aria-label="richText.linkUrl"]').element.value).toBe('https://old.example');
  });

  // Catches link removal deleting selected text together with its mark.
  it('keeps the linked text when removing its link', async () => {
    const wrapper = mountDocumentEditor('[ProjectApp](https://old.example)');
    await nextTick();

    await selectExistingLink(wrapper);
    await openLink(wrapper);
    await wrapper.findAll('button').find((button) => button.text() === 'richText.removeLink').trigger('click');
    await sourceTab(wrapper).trigger('click');

    expect(wrapper.get('[data-testid="rich-text-source-input"]').element.value).toBe('ProjectApp');
  });

  // Catches cancelling a link edit persisting the unfinished address over the saved document.
  it('keeps the source after cancelling a link edit', async () => {
    const wrapper = mountDocumentEditor('[ProjectApp](https://old.example)');
    await nextTick();

    await selectExistingLink(wrapper);
    await openLink(wrapper);
    await wrapper.get('[aria-label="richText.linkUrl"]').setValue('https://new.example');
    await wrapper.findAll('button').find((button) => button.text() === 'richText.cancel').trigger('click');
    await sourceTab(wrapper).trigger('click');

    expect(wrapper.get('[data-testid="rich-text-source-input"]').element.value).toBe('[ProjectApp](https://old.example)');
  });

  // Catches a link update replacing the document text instead of only its destination.
  it('applies a new address to the existing linked text', async () => {
    const wrapper = mountDocumentEditor('[ProjectApp](https://old.example)');
    await nextTick();

    await selectExistingLink(wrapper);
    await openLink(wrapper);
    await wrapper.get('[aria-label="richText.linkUrl"]').setValue('https://new.example');
    await wrapper.findAll('button').find((button) => button.text() === 'richText.apply').trigger('click');
    await sourceTab(wrapper).trigger('click');

    expect(wrapper.get('[data-testid="rich-text-source-input"]').element.value).toBe('[ProjectApp](https://new.example)');
  });

  // Catches the Insert menu producing an ordinary quote instead of the persisted NOTE callout marker.
  it('serializes an inserted note as a callout', async () => {
    const wrapper = mountDocumentEditor();
    await nextTick();

    await chooseInsertItem(wrapper, 'richText.calloutNOTE');
    await sourceTab(wrapper).trigger('click');

    expect(wrapper.get('[data-testid="rich-text-source-input"]').element.value).toBe('> [!NOTE]\n> Agenda');
  });

  // Catches the document code-block menu losing the fenced Markdown representation on save.
  it('serializes an inserted code block as fenced Markdown', async () => {
    const wrapper = mountDocumentEditor();
    await nextTick();

    await chooseInsertItem(wrapper, 'richText.codeBlock');
    await sourceTab(wrapper).trigger('click');

    expect(wrapper.get('[data-testid="rich-text-source-input"]').element.value).toBe('```\nAgenda\n```');
  });

  // Catches the separator menu action failing to persist an explicit Markdown rule.
  it('serializes an inserted separator as a Markdown rule', async () => {
    const wrapper = mountDocumentEditor();
    await nextTick();

    await chooseInsertItem(wrapper, 'richText.separator');
    await sourceTab(wrapper).trigger('click');

    expect(wrapper.get('[data-testid="rich-text-source-input"]').element.value).toBe('Agenda\n\n---');
  });
});
