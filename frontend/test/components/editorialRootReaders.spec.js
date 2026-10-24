import { mount } from '@vue/test-utils';
import { nextTick } from 'vue';

import BlogContentRenderer from '../../components/blog/BlogContentRenderer.vue';
import BuildingOnDemandProgramView from '../../components/BuildingOnDemand/ProgramView.vue';
import BuildingWithUsProgramView from '../../components/BuildingWithUs/ProgramView.vue';
import ConsultingProgramView from '../../components/Consulting/ProgramView.vue';
import BaseSegmented from '../../components/base/BaseSegmented.vue';
import { createBuildingOnDemandProgram } from '../utils/buildingOnDemandFixture';

const wrappers = [];

function render(component, props) {
  const wrapper = mount(component, {
    props,
    global: {
      components: { BaseSegmented },
      stubs: {
        BaseAlert: true,
        BaseBadge: true,
        NuxtLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
        Teleport: true,
        Transition: true,
      },
    },
  });
  wrappers.push(wrapper);
  return wrapper;
}

async function settled() {
  await nextTick();
  await nextTick();
}

function paragraphWithText(wrapper, text) {
  return wrapper.findAll('p').find((paragraph) => paragraph.text() === text);
}

beforeEach(() => {
  global.useI18n = () => ({ t: (key) => key });
});

afterEach(() => {
  wrappers.splice(0).forEach((wrapper) => wrapper.unmount());
  delete global.useI18n;
  window.localStorage.clear();
});

describe('editorial root metadata readers', () => {
  it('renders a root Blog annotation without changing the content JSON', async () => {
    const contentJson = {
      intro: '<p style="text-align: center"><strong>Blog evidence</strong></p>',
      sections: [],
      text_formats: { '/intro': 'markdown_html_v1' },
    };
    const wrapper = render(BlogContentRenderer, { contentJson });
    await settled();

    expect(wrapper.get('strong').text()).toBe('Blog evidence');
    expect(paragraphWithText(wrapper, 'Blog evidence').element.style.textAlign).toBe('center');
    expect(contentJson).toEqual({
      intro: '<p style="text-align: center"><strong>Blog evidence</strong></p>',
      sections: [],
      text_formats: { '/intro': 'markdown_html_v1' },
    });
  });

  it('renders a root Building with Us annotation without changing the program', async () => {
    const program = {
      hero: { title: 'Collaborate', subtitle: '<p style="text-align: right"><strong>Partner proof</strong></p>' },
      text_formats: { '/hero/subtitle': 'markdown_html_v1' },
    };
    const wrapper = render(BuildingWithUsProgramView, { floatingActions: false, program });
    await settled();

    expect(wrapper.get('strong').text()).toBe('Partner proof');
    expect(paragraphWithText(wrapper, 'Partner proof').element.style.textAlign).toBe('right');
    expect(program.text_formats).toEqual({ '/hero/subtitle': 'markdown_html_v1' });
  });

  it('renders a root Building on Demand annotation without changing the program', async () => {
    const source = createBuildingOnDemandProgram();
    const program = {
      ...source,
      hero: { ...source.hero, subtitle: '<p style="text-align: center"><strong>Demand proof</strong></p>' },
      text_formats: { '/hero/subtitle': 'markdown_html_v1' },
    };
    const wrapper = render(BuildingOnDemandProgramView, { floatingActions: false, program });
    await settled();

    expect(wrapper.get('strong').text()).toBe('Demand proof');
    expect(paragraphWithText(wrapper, 'Demand proof').element.style.textAlign).toBe('center');
    expect(program.text_formats).toEqual({ '/hero/subtitle': 'markdown_html_v1' });
  });

  it('renders a root Consulting annotation without changing the program', async () => {
    const program = {
      hero: { title: 'Advisory', subtitle: '<p style="text-align: justify"><strong>Consulting proof</strong></p>' },
      text_formats: { '/hero/subtitle': 'markdown_html_v1' },
    };
    const wrapper = render(ConsultingProgramView, { floatingActions: false, program });
    await settled();

    expect(wrapper.get('strong').text()).toBe('Consulting proof');
    expect(paragraphWithText(wrapper, 'Consulting proof').element.style.textAlign).toBe('justify');
    expect(program.text_formats).toEqual({ '/hero/subtitle': 'markdown_html_v1' });
  });
});
