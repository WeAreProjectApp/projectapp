import { nextTick, onBeforeUnmount } from 'vue';

/** Three restrained pulses, with an equivalent static cue for reduced motion. */
export function useRadarFocus() {
  let timer;
  let previous;
  onBeforeUnmount(() => { clearTimeout(timer); previous?.classList.remove('radar-record-highlight'); });
  return async (selector) => {
    await nextTick();
    const element = document.querySelector(selector);
    if (!element) return;
    clearTimeout(timer);
    previous?.classList.remove('radar-record-highlight');
    previous = element;
    if (!element.matches('a[href], button, input, textarea, select, [tabindex]')) {
      element.setAttribute('tabindex', '-1');
    }
    element.scrollIntoView?.({ block: 'center', behavior: 'auto' });
    element.focus({ preventScroll: true });
    element.classList.add('radar-record-highlight');
    timer = setTimeout(() => element.classList.remove('radar-record-highlight'), 3000);
  };
}
