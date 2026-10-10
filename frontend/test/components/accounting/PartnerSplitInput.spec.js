import { flushPromises, mount } from '@vue/test-utils';
import PartnerSplitInput from '~/components/accounting/PartnerSplitInput.vue';

function mountInput(props = {}) {
  return mount(PartnerSplitInput, {
    props: { total: '', gustavoAmount: '', carlosAmount: '', ...props },
  });
}

// Owns the three amounts through v-model, like every modal does, so what the
// component emits lands back in its own fields.
function mountWithParent(initial = {}) {
  return mount({
    components: { PartnerSplitInput },
    data: () => ({ total: '', gustavo: '', carlos: '', ...initial }),
    template: `
      <PartnerSplitInput
        v-model:total="total"
        v-model:gustavoAmount="gustavo"
        v-model:carlosAmount="carlos"
      />
    `,
  });
}

const totalInput = (wrapper) => wrapper.find('[data-testid="partner-split-total"]');
const gustavoInput = (wrapper) => wrapper.find('[data-testid="partner-split-gustavo"]');
const carlosInput = (wrapper) => wrapper.find('[data-testid="partner-split-carlos"]');
const autoToggle = (wrapper) => wrapper.find('[data-testid="partner-split-auto"]');
const remainderLine = (wrapper) => wrapper.find('[data-testid="partner-split-remainder"]');

describe('PartnerSplitInput', () => {
  it('auto mode splits an even total 50/50', async () => {
    const wrapper = mountInput();

    await totalInput(wrapper).setValue('1000');

    expect(wrapper.emitted('update:total')[0]).toEqual([1000]);
    expect(wrapper.emitted('update:gustavoAmount')[0]).toEqual([500]);
    expect(wrapper.emitted('update:carlosAmount')[0]).toEqual([500]);
  });

  it('auto mode leaves the odd peso of an odd total in the ProjectApp pocket', async () => {
    const wrapper = mountWithParent();

    await totalInput(wrapper).setValue('101');

    expect(gustavoInput(wrapper).element.value).toBe('50');
    expect(carlosInput(wrapper).element.value).toBe('50');
    expect(remainderLine(wrapper).text()).toBe('Bolsillo ProjectApp: $1 COP');
  });

  // Bug caught: Liquidar opens on the pending amount with the toggle on and
  // both partner fields empty — auto mode only split a total typed by hand.
  // Switching Contabilidad back to Empresa remounts the block the same way.
  it('shows the automatic split of a total that arrives already filled', async () => {
    const wrapper = mountWithParent({ total: '600000.00' });
    await flushPromises();

    expect(gustavoInput(wrapper).element.value).toBe('300.000');
    expect(carlosInput(wrapper).element.value).toBe('300.000');
    expect(remainderLine(wrapper).exists()).toBe(false);
  });

  // Bug caught: a 70/30 record opened with the 50/50 toggle on, and the next
  // total typed silently replaced the split the record had chosen.
  it('opens a split of its own in manual mode and keeps it when the total changes', async () => {
    const wrapper = mountWithParent({ total: 1000, gustavo: 700, carlos: 300 });
    await flushPromises();

    expect(gustavoInput(wrapper).attributes('disabled')).toBeUndefined();

    await totalInput(wrapper).setValue('2000');

    expect(gustavoInput(wrapper).element.value).toBe('700');
    expect(carlosInput(wrapper).element.value).toBe('300');
    expect(remainderLine(wrapper).text()).toBe('Bolsillo ProjectApp: $1.000 COP');
  });

  it('re-splits a total the parent replaces while auto mode is on', async () => {
    const wrapper = mountWithParent({ total: 1000, gustavo: 500, carlos: 500 });

    await wrapper.setData({ total: 3000 });
    await flushPromises();

    expect(gustavoInput(wrapper).element.value).toBe('1.500');
    expect(carlosInput(wrapper).element.value).toBe('1.500');
  });

  it('disables partner inputs while auto mode is on', () => {
    const wrapper = mountInput({ total: 100 });

    expect(gustavoInput(wrapper).attributes('disabled')).toBeDefined();
    expect(carlosInput(wrapper).attributes('disabled')).toBeDefined();
  });

  it('manual mode enables partner inputs and emits raw partner edits', async () => {
    const wrapper = mountInput({ total: 100, gustavoAmount: 50, carlosAmount: 50 });

    await autoToggle(wrapper).trigger('click');

    expect(gustavoInput(wrapper).attributes('disabled')).toBeUndefined();

    await gustavoInput(wrapper).setValue('70');

    expect(wrapper.emitted('update:gustavoAmount')).toBeTruthy();
    expect(wrapper.emitted('update:gustavoAmount').at(-1)).toEqual([70]);
    // Editing one partner never auto-adjusts the other.
    expect(wrapper.emitted('update:carlosAmount')).toBeFalsy();
  });

  it('opens a split above the total in manual mode, with the warning', () => {
    const wrapper = mountInput({ total: 100, gustavoAmount: 80, carlosAmount: 40 });

    expect(gustavoInput(wrapper).attributes('disabled')).toBeUndefined();
    expect(wrapper.find('[data-testid="partner-split-warning"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('La suma de socios supera el total');
  });

  it('re-enabling auto recomputes the split from the total', async () => {
    const wrapper = mountWithParent({ total: 101, gustavo: 80, carlos: 40 });

    await autoToggle(wrapper).trigger('click');

    expect(gustavoInput(wrapper).element.value).toBe('50');
    expect(carlosInput(wrapper).element.value).toBe('50');
    expect(wrapper.find('[data-testid="partner-split-warning"]').exists()).toBe(false);
  });

  it('shows the ProjectApp pocket remainder when total exceeds the partner sum', () => {
    const wrapper = mountInput({ total: 1000, gustavoAmount: 300, carlosAmount: 300 });

    const remainder = remainderLine(wrapper);
    expect(remainder.exists()).toBe(true);
    expect(remainder.text()).toContain('Bolsillo ProjectApp:');
  });

  it('hides the remainder line when nothing is left over', () => {
    const wrapper = mountInput({ total: 1000, gustavoAmount: 500, carlosAmount: 500 });

    expect(remainderLine(wrapper).exists()).toBe(false);
  });
});
