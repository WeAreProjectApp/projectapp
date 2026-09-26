// v-auto-resize: grows a <textarea> with its content so no inner scroll is
// needed. The `rows` attribute still defines the minimum height.
export const vAutoResize = {
  mounted(el) {
    el.style.overflow = 'hidden';

    const cs = window.getComputedStyle(el);
    const borderY =
      (parseFloat(cs.borderTopWidth) || 0) + (parseFloat(cs.borderBottomWidth) || 0);

    const computeMinHeight = () => {
      const rows = parseInt(el.getAttribute('rows'), 10) || 3;
      const lineHeight =
        parseFloat(cs.lineHeight) ||
        parseFloat(cs.fontSize) * 1.5;
      const paddingY =
        parseFloat(cs.paddingTop) + parseFloat(cs.paddingBottom);
      return rows * lineHeight + paddingY + borderY;
    };

    el._autoResizeMinHeight = computeMinHeight();
    // scrollHeight stops at the padding edge, while a border-box height (the
    // Tailwind default) also spans the borders: without them the last line
    // stays clipped behind the hidden overflow.
    el._autoResizeBorderY = cs.boxSizing === 'border-box' ? borderY : 0;
    el._autoResizeHandler = () => {
      // Memoize by value, not by height — a height check after the `auto`
      // collapse would skip the restore and strand the element clipped.
      if (el._autoResizeLastValue === el.value) return;
      el._autoResizeLastValue = el.value;
      el.style.height = 'auto';
      el.style.height = Math.max(
        el.scrollHeight + el._autoResizeBorderY,
        el._autoResizeMinHeight,
      ) + 'px';
    };
    el.addEventListener('input', el._autoResizeHandler);
    el._autoResizeHandler();
  },
  updated(el) {
    if (!el._autoResizeHandler) return;
    el._autoResizeHandler();
  },
  beforeUnmount(el) {
    el.removeEventListener('input', el._autoResizeHandler);
  },
};
