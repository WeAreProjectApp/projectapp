import { mount } from '@vue/test-utils';
import { createPinia } from 'pinia';
import { nextTick, reactive } from 'vue';
import BaseInput from '~/components/base/BaseInput.vue';
import BaseSelect from '~/components/base/BaseSelect.vue';
import ProposalGeneralTab from '~/components/panel/proposal/ProposalGeneralTab.vue';

function createForm(overrides = {}) {
  return reactive({
    title: 'Propuesta de regresión',
    project_type: '',
    market_type: '',
    language: 'es',
    expires_at: '',
    reminder_days: 3,
    urgency_reminder_days: 15,
    discount_percent: 0,
    ...overrides,
  });
}

function mountGeneral(form) {
  return mount(ProposalGeneralTab, {
    props: {
      proposal: { id: 226, title: form.title, status: 'draft', slug: '', sections: [] },
      form,
    },
    global: {
      plugins: [createPinia()],
      components: { BaseInput, BaseSelect },
      stubs: {
        TabSplitLayout: { template: '<div><slot name="main" /></div>' },
        BaseTooltip: true,
      },
    },
  });
}

describe('ProposalGeneralTab expiry', () => {
  let wrapper;

  beforeEach(() => {
    jest.useFakeTimers();
    jest.setSystemTime(new Date(2026, 10, 6, 10, 0));
  });

  afterEach(() => {
    wrapper?.unmount();
    jest.useRealTimers();
  });

  // PA-226: the tab mounts before the page hydrates its shared form.
  it.each([
    ['expired', '2026-10-15T14:30', '1'],
    ['future', '2026-11-20T14:30', '14'],
    ['late future', '2026-11-20T23:30', '14'],
    ['empty', '', '21'],
  ])('preserves the saved %s expiry during hydration', async (_label, savedDate, days) => {
    const form = createForm();
    wrapper = mountGeneral(form);

    form.expires_at = savedDate;
    await nextTick();

    expect(wrapper.get('[data-testid="proposal-expiry-date"]').element.value).toBe(savedDate);
    expect(wrapper.get('[data-testid="proposal-expiry-days"]').element.value).toBe(days);
    expect(form.expires_at).toBe(savedDate);
  });

  it('preserves the refreshed expiry on a mounted tab', async () => {
    const form = createForm({ expires_at: '2026-11-20T14:30' });
    wrapper = mountGeneral(form);

    form.expires_at = '2026-10-15T14:30';
    await nextTick();

    expect(wrapper.get('[data-testid="proposal-expiry-days"]').element.value).toBe('1');
    expect(form.expires_at).toBe('2026-10-15T14:30');
  });

  it('preserves a date typed near midnight', async () => {
    const form = createForm({ expires_at: '2026-11-20T14:30' });
    wrapper = mountGeneral(form);

    await wrapper.get('[data-testid="proposal-expiry-date"]').setValue('2026-11-20T23:30');

    expect(wrapper.get('[data-testid="proposal-expiry-days"]').element.value).toBe('14');
    expect(form.expires_at).toBe('2026-11-20T23:30');
  });

  it('updates the expiry after editing the days', async () => {
    const form = createForm({ expires_at: '2026-10-15T14:30' });
    wrapper = mountGeneral(form);

    await wrapper.get('[data-testid="proposal-expiry-days"]').setValue('7');

    expect(wrapper.get('[data-testid="proposal-expiry-date"]').element.value).toBe('2026-11-13T14:30');
    expect(form.expires_at).toBe('2026-11-13T14:30');
  });

  it('uses the current time when adding days to an empty expiry', async () => {
    const form = createForm();
    wrapper = mountGeneral(form);

    await wrapper.get('[data-testid="proposal-expiry-days"]').setValue('7');

    expect(form.expires_at).toBe('2026-11-13T10:00');
  });

  it('keeps a cleared expiry empty', async () => {
    const form = createForm({ expires_at: '2026-11-20T14:30' });
    wrapper = mountGeneral(form);

    await wrapper.get('[data-testid="proposal-expiry-date"]').setValue('');

    expect(wrapper.get('[data-testid="proposal-expiry-days"]').element.value).toBe('21');
    expect(form.expires_at).toBe('');
  });
});
