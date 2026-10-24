import { mount } from '@vue/test-utils';
import { nextTick } from 'vue';
import BaseRichTextContent from '../../components/base/BaseRichTextContent.vue';

const wrappers = [];

function render(props) {
  const wrapper = mount(BaseRichTextContent, { props });
  wrappers.push(wrapper);
  return wrapper;
}

afterEach(() => wrappers.splice(0).forEach((wrapper) => wrapper.unmount()));

describe('BaseRichTextContent', () => {
  // Catches legacy plain values acquiring formatting simply because their punctuation resembles Markdown.
  it('renders plain legacy Markdown markers as literal reader text', async () => {
    const wrapper = render({ source: '**contract**\n<script>alert(1)</script>', format: 'plain' });
    await nextTick();

    expect(wrapper.text()).toBe('**contract**<script>alert(1)</script>');
    expect(wrapper.find('strong').exists()).toBe(false);
  });

  // Catches the rich reader treating saved Markdown as plain source after hydration.
  it('renders saved Markdown into the expected formatted document', async () => {
    const wrapper = render({ source: '# Summary\n\n**Approved**\n\n1. First\n2. Second', format: 'markdown_html_v1' });
    await nextTick();

    expect(wrapper.get('h1').text()).toBe('Summary');
    expect(wrapper.get('strong').text()).toBe('Approved');
    expect(wrapper.findAll('ol > li').map((item) => item.text())).toEqual(['First', 'Second']);
  });

  // Catches WhatsApp source being interpreted with the document parser instead of its channel-specific syntax.
  it('renders WhatsApp emphasis and list content with the WhatsApp profile', async () => {
    const wrapper = render({ source: '*Confirmado*\n\n- Cliente', format: 'whatsapp_v1', profile: 'whatsapp' });
    await nextTick();

    expect(wrapper.get('strong').text()).toBe('Confirmado');
    expect(wrapper.get('li').text()).toBe('Cliente');
  });
});
