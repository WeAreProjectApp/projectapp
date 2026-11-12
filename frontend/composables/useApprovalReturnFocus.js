import { nextTick, onBeforeUnmount, watch } from 'vue';

/** Approval can remove its Review trigger. Resolve a surviving destination after closing. */
export function useApprovalReturnFocus(visible, returnFocus) {
  let opener = null;
  let fallback = null;
  let location = '';
  let generation = 0;
  let frame = null;

  function available(element) {
    if (!element?.isConnected || element === document.body || element === document.documentElement) return false;
    if (element.matches(':disabled, [aria-disabled="true"]')) return false;
    const style = window.getComputedStyle(element);
    return style.display !== 'none' && style.visibility !== 'hidden' && element.getClientRects().length > 0;
  }

  function cancelPending() {
    generation += 1;
    if (frame !== null) window.cancelAnimationFrame(frame);
    frame = null;
  }

  watch(visible, async (open, wasOpen) => {
    if (typeof document === 'undefined') return;
    cancelPending();
    if (open) {
      opener = document.activeElement;
      fallback = returnFocus.value;
      location = window.location.href;
      return;
    }
    if (!wasOpen) return;
    const token = generation;
    const closingDialog = document.querySelector('[data-testid="proposal-approval-modal"]')?.closest('[role="dialog"]');
    await nextTick();
    if (token !== generation) return;
    frame = window.requestAnimationFrame(() => {
      frame = null;
      if (token !== generation || window.location.href !== location) return;
      const anotherDialog = [...document.querySelectorAll('[role="dialog"]')]
        .some((dialog) => dialog !== closingDialog && available(dialog));
      if (anotherDialog) return;
      const target = available(opener) ? opener : fallback?.();
      if (available(target)) target.focus({ preventScroll: true });
    });
  }, { immediate: true, flush: 'sync' });

  onBeforeUnmount(cancelPending);
}
