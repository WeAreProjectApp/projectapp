import { mount } from '@vue/test-utils';
import { nextTick } from 'vue';
import BaseCard from '../../components/base/BaseCard.vue';
import BaseRichTextContent from '../../components/base/BaseRichTextContent.vue';
import BaseSegmented from '../../components/base/BaseSegmented.vue';
import ModuleDetails from '../../components/AdditionalModules/ModuleDetails.vue';
import BuildingWithUsProgramView from '../../components/BuildingWithUs/ProgramView.vue';
import BlogContentRenderer from '../../components/blog/BlogContentRenderer.vue';
import ConsultingProgramView from '../../components/Consulting/ProgramView.vue';

const wrappers = [];
const readerComponents = { BaseCard, BaseRichTextContent, BaseSegmented };

async function settled() {
  await nextTick();
  await nextTick();
}

function render(component, props) {
  const wrapper = mount(component, { props, global: { components: readerComponents, stubs: { BaseBadge: true, BaseAlert: true } } });
  wrappers.push(wrapper);
  return wrapper;
}

function paragraphWithText(wrapper, text) {
  return [...wrapper.findAll('p'), ...wrapper.findAll('.editorial-content')].find((content) => content.text() === text);
}

beforeEach(() => { global.useI18n = () => ({ t: (key) => key }); });
afterEach(() => {
  wrappers.splice(0).forEach((wrapper) => wrapper.unmount());
  delete global.useI18n;
  window.localStorage.clear();
});

describe('editorial module readers', () => {
  // Catches structured blog metadata being ignored, which would flatten lists, tables, or alignment in the public article.
  it('renders blog list, table, and alignment formats declared in content metadata', async () => {
    const wrapper = render(BlogContentRenderer, {
      contentJson: {
        intro: '<p style="text-align: center">Centered introduction</p>',
        text_formats: { '/intro': 'markdown_html_v1' },
        sections: [{
          heading: 'Decision', content: '**Approved**',
          list: ['| Plan |\n| --- |\n| Ready |'],
          text_formats: { '/content': 'markdown_html_v1', '/list/0': 'markdown_html_v1' },
        }],
      },
    });
    await settled();

    expect(paragraphWithText(wrapper, 'Centered introduction').element.style.textAlign).toBe('center');
    expect(wrapper.get('strong').text()).toBe('Approved');
    expect(wrapper.get('table').findAll('th').map((cell) => cell.text())).toEqual(['Plan']);
    expect(wrapper.get('table').findAll('td').map((cell) => cell.text())).toEqual(['Ready']);
  });

  // Catches metadata-free content being parsed as Markdown and changing historical readers without an explicit format version.
  it('keeps blog text literal when no metadata declares a rich format', async () => {
    const wrapper = render(BlogContentRenderer, {
      contentJson: { intro: '**Legacy marker**', sections: [] },
    });
    await settled();

    expect(paragraphWithText(wrapper, '**Legacy marker**').text()).toBe('**Legacy marker**');
    expect(wrapper.findAll('strong')).toHaveLength(0);
  });

  // Catches Building with Us public content losing a saved rich hero format on the read path.
  it('renders Building with Us hero formatting from its metadata path', async () => {
    const wrapper = render(BuildingWithUsProgramView, {
      floatingActions: false,
      program: {
        hero: {
          title: 'Build together',
          subtitle: '<p style="text-align: right"><strong>Partner proof</strong></p>',
          note: 'Plain note',
          text_formats: { '/subtitle': 'markdown_html_v1' },
        },
      },
    });
    await settled();

    expect(wrapper.get('strong').text()).toBe('Partner proof');
    expect(paragraphWithText(wrapper, 'Partner proof').element.style.textAlign).toBe('right');
    expect(paragraphWithText(wrapper, 'Plain note').text()).toBe('Plain note');
  });

  // Catches the consulting reader bypassing BaseRichTextContent for formatted hero content.
  it('renders Consulting hero Markdown and keeps its plain note literal', async () => {
    const wrapper = render(ConsultingProgramView, {
      floatingActions: false,
      program: {
        hero: {
          title: 'Advisory', subtitle: '**Evidence-led**', note: '**Literal note**',
          text_formats: { '/subtitle': 'markdown_html_v1' },
        },
      },
    });
    await settled();

    expect(wrapper.get('strong').text()).toBe('Evidence-led');
    expect(paragraphWithText(wrapper, '**Literal note**').text()).toBe('**Literal note**');
  });

  // Catches additional-module array paths falling back to plain output after format metadata was saved per item.
  it('renders module scalar and array formats from their independent metadata paths', async () => {
    const wrapper = render(ModuleDetails, {
      language: 'es',
      module: {
        what_is: '**Automated billing**', purpose: '**Legacy purpose**',
        problems_solved: ['**Manual work**'], integrations: [], implementation_requirements: [],
        text_formats: { '/what_is': 'markdown_html_v1', '/problems_solved/0': 'markdown_html_v1' },
      },
    });
    await settled();

    expect(wrapper.findAll('strong').map((item) => item.text())).toEqual(['Automated billing', 'Manual work']);
    expect(paragraphWithText(wrapper, '**Legacy purpose**').text()).toBe('**Legacy purpose**');
  });
});
