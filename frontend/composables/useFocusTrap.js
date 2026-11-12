import { nextTick, onBeforeUnmount, unref, watch } from 'vue';

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

/**
 * Keyboard focus trap for dialogs/overlays. Keydown-based on purpose: it
 * adds no sentinel siblings, so the container's DOM structure (and any
 * positional selectors that depend on it) stays untouched.
 *
 * While `active` is true, Tab/Shift+Tab wrap inside `containerRef`. On
 * activation the previously focused element is remembered and focus moves
 * to (in priority order): `initialFocus()`, the first `[data-autofocus]`
 * descendant, or the container itself (give it `tabindex="-1"`). Focusing
 * the container first avoids scroll-jumps in long forms. On deactivation
 * focus returns to the remembered element if it is still in the document.
 *
 * @param {import('vue').Ref<HTMLElement|null>} containerRef - Trap container
 * @param {Object} options
 * @param {import('vue').Ref<boolean>} options.active - Trap on/off switch
 * @param {(() => HTMLElement|null)|null} [options.initialFocus] - Preferred
 *   initial focus target; return null to fall through to the defaults
 * @param {import('vue').Ref<boolean>|boolean} [options.paused] - Leave focus handling to a nested dialog without forgetting the original opener
 * @returns {{ activate: () => Promise<void>, deactivate: () => void }}
 */
export function useFocusTrap(containerRef, { active, initialFocus = null, paused = false } = {}) {
  let previouslyFocused = null;

  function focusables() {
    const el = unref(containerRef);
    if (!el) return [];
    return Array.from(el.querySelectorAll(FOCUSABLE_SELECTOR));
  }

  function onKeydown(event) {
    if (unref(paused)) return;
    if (event.key !== 'Tab') return;
    const el = unref(containerRef);
    if (!el) return;
    const nodes = focusables();
    if (!nodes.length) {
      event.preventDefault();
      el.focus();
      return;
    }
    const first = nodes[0];
    const last = nodes[nodes.length - 1];
    const current = document.activeElement;
    if (event.shiftKey) {
      if (current === first || !el.contains(current)) {
        event.preventDefault();
        last.focus();
      }
    } else if (current === last || !el.contains(current)) {
      event.preventDefault();
      first.focus();
    }
  }

  async function activate() {
    if (typeof document === 'undefined') return;
    previouslyFocused = document.activeElement;
    await nextTick();
    const el = unref(containerRef);
    if (!el) return;
    const preferred = typeof initialFocus === 'function' ? initialFocus() : null;
    const target = preferred || el.querySelector('[data-autofocus]') || el;
    target.focus();
    el.addEventListener('keydown', onKeydown);
  }

  function deactivate() {
    if (typeof document === 'undefined') return;
    const el = unref(containerRef);
    if (el) el.removeEventListener('keydown', onKeydown);
    if (
      previouslyFocused
      && typeof previouslyFocused.focus === 'function'
      && document.contains(previouslyFocused)
    ) {
      previouslyFocused.focus();
    }
    previouslyFocused = null;
  }

  if (active) {
    watch(
      active,
      (isActive, wasActive) => {
        if (isActive && !wasActive) activate();
        else if (!isActive && wasActive) deactivate();
      },
      { immediate: true },
    );
  }

  onBeforeUnmount(() => {
    if (previouslyFocused) deactivate();
  });

  return { activate, deactivate };
}
