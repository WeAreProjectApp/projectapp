import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent, ref } from 'vue';

import { useProgramContractRefresh } from '../../composables/useProgramContractRefresh';

function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}

function mountRefresh(activeSection, store, onReady = () => {}) {
  const Host = defineComponent({
    setup() {
      onReady(useProgramContractRefresh(store, activeSection));
      return () => null;
    },
  });
  return mount(Host);
}

describe('useProgramContractRefresh', () => {
  it('refreshes the saved contract on focus', async () => {
    const activeSection = ref('contract');
    const store = {
      contractUnavailable: false,
      fetchContract: jest.fn().mockResolvedValue({ success: true }),
      fetchVersions: jest.fn().mockResolvedValue({ success: true }),
    };
    const wrapper = mountRefresh(activeSection, store);

    // Fails if returning from the document editor leaves the module on an old contract version.
    window.dispatchEvent(new Event('focus'));
    await flushPromises();

    expect(store.fetchContract).toHaveBeenCalledTimes(1);
    expect(store.fetchVersions).toHaveBeenCalledWith('contract');
    wrapper.unmount();
  });

  it('does not refresh contracts while another program tab has focus', async () => {
    const activeSection = ref('program');
    const store = {
      contractUnavailable: false,
      fetchContract: jest.fn().mockResolvedValue({ success: true }),
      fetchVersions: jest.fn().mockResolvedValue({ success: true }),
    };
    const wrapper = mountRefresh(activeSection, store);

    // Fails if a focus event reloads contracts while the user is working in another tab.
    window.dispatchEvent(new Event('focus'));
    await flushPromises();

    expect(store.fetchContract).toHaveBeenCalledTimes(0);
    expect(store.fetchVersions).toHaveBeenCalledTimes(0);
    wrapper.unmount();
  });

  it('shares an in-flight refresh between repeated requests', async () => {
    const activeSection = ref('contract');
    const request = deferred();
    const store = {
      contractUnavailable: false,
      fetchContract: jest.fn().mockReturnValue(request.promise),
      fetchVersions: jest.fn().mockResolvedValue({ success: true }),
    };
    let refresh;
    const wrapper = mountRefresh(activeSection, store, (registeredRefresh) => { refresh = registeredRefresh; });

    // Fails if two focus events race and request the same contract twice.
    const first = refresh();
    window.dispatchEvent(new Event('focus'));
    expect(store.fetchContract).toHaveBeenCalledTimes(1);

    request.resolve({ success: true });
    await first;

    expect(store.fetchVersions).toHaveBeenCalledTimes(1);
    expect(store.fetchVersions).toHaveBeenCalledWith('contract');
    wrapper.unmount();
  });

  it('stops observing focus when its page unmounts', async () => {
    const activeSection = ref('contract');
    const store = {
      contractUnavailable: false,
      fetchContract: jest.fn().mockResolvedValue({ success: true }),
      fetchVersions: jest.fn().mockResolvedValue({ success: true }),
    };
    const wrapper = mountRefresh(activeSection, store);

    // Fails if a destroyed panel still refreshes after navigation to another module.
    wrapper.unmount();
    window.dispatchEvent(new Event('focus'));
    await flushPromises();

    expect(store.fetchContract).toHaveBeenCalledTimes(0);
    expect(store.fetchVersions).toHaveBeenCalledTimes(0);
  });
});
