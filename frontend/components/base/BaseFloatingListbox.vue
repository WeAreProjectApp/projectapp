<script setup>
import {
  computed,
  inject,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from 'vue';

import { BASE_MODAL_FLOATING_CONTEXT } from './modalContext';

const props = defineProps({
  open: { type: Boolean, default: false },
  anchor: { type: Object, default: null },
  owner: { type: Object, default: null },
  id: { type: String, default: undefined },
  ariaLabel: { type: String, default: undefined },
  as: { type: String, default: 'div' },
  maxHeight: { type: Number, default: 320 },
  offset: { type: Number, default: 4 },
  viewportPadding: { type: Number, default: 16 },
  endThreshold: { type: Number, default: 48 },
});

const emit = defineEmits(['close', 'reach-end']);

const modalContext = inject(BASE_MODAL_FLOATING_CONTEXT, null);
const panelRef = ref(null);
const isMounted = ref(false);
const panelStyle = ref({ visibility: 'hidden' });

const teleportTarget = computed(() => (
  modalContext?.floatingRoot?.value
  || (typeof document !== 'undefined' ? document.body : null)
));

let isActive = false;
let animationFrame = null;
let anchorObserver = null;
let panelObserver = null;
let unregisterFloatingLayer = null;

function viewportBounds() {
  const visualViewport = window.visualViewport;
  const left = visualViewport?.offsetLeft || 0;
  const top = visualViewport?.offsetTop || 0;
  const width = visualViewport?.width || window.innerWidth;
  const height = visualViewport?.height || window.innerHeight;
  return {
    left,
    top,
    right: left + width,
    bottom: top + height,
    width,
    height,
  };
}

function updatePosition() {
  animationFrame = null;
  const anchor = props.anchor;
  const panel = panelRef.value;
  if (!props.open || !anchor || !panel) return;

  const bounds = viewportBounds();
  const anchorRect = anchor.getBoundingClientRect();
  const padding = props.viewportPadding;
  const availableWidth = Math.max(0, bounds.width - (padding * 2));
  const width = Math.min(anchorRect.width, availableWidth);
  const left = Math.min(
    Math.max(anchorRect.left, bounds.left + padding),
    bounds.right - padding - width,
  );

  const availableBelow = Math.max(
    0,
    bounds.bottom - padding - anchorRect.bottom - props.offset,
  );
  const availableAbove = Math.max(
    0,
    anchorRect.top - bounds.top - padding - props.offset,
  );
  const placeAbove = availableBelow < props.maxHeight && availableAbove > availableBelow;
  const availableHeight = placeAbove ? availableAbove : availableBelow;
  const maxHeight = Math.max(0, Math.min(props.maxHeight, availableHeight));
  const renderedHeight = Math.min(panel.scrollHeight || maxHeight, maxHeight);
  const top = placeAbove
    ? anchorRect.top - props.offset - renderedHeight
    : anchorRect.bottom + props.offset;

  panelStyle.value = {
    visibility: 'visible',
    left: `${Math.round(left)}px`,
    top: `${Math.round(Math.max(bounds.top + padding, top))}px`,
    width: `${Math.round(width)}px`,
    maxHeight: `${Math.floor(maxHeight)}px`,
  };
}

function schedulePosition() {
  if (animationFrame !== null || typeof window === 'undefined') return;
  if (typeof window.requestAnimationFrame !== 'function') {
    updatePosition();
    return;
  }
  animationFrame = window.requestAnimationFrame(updatePosition);
}

function onPointerDown(event) {
  const target = event.target;
  if (!(target instanceof Node)) return;
  if (props.owner?.contains(target) || panelRef.value?.contains(target)) return;
  emit('close');
}

function onKeydown(event) {
  if (event.key !== 'Escape') return;
  event.preventDefault();
  event.stopImmediatePropagation();
  emit('close');
}

function onScroll(event) {
  const panel = event.currentTarget;
  if (!panel) return;
  const remaining = panel.scrollHeight - panel.scrollTop - panel.clientHeight;
  if (remaining <= props.endThreshold) emit('reach-end');
}

function observeElements() {
  anchorObserver?.disconnect();
  panelObserver?.disconnect();
  anchorObserver = null;
  panelObserver = null;
  if (typeof ResizeObserver === 'undefined') return;

  if (props.anchor) {
    anchorObserver = new ResizeObserver(schedulePosition);
    anchorObserver.observe(props.anchor);
  }
  if (panelRef.value) {
    panelObserver = new ResizeObserver(schedulePosition);
    panelObserver.observe(panelRef.value);
  }
}

async function activate() {
  if (!isMounted.value || !props.open || !props.anchor) return;
  if (!isActive) {
    isActive = true;
    unregisterFloatingLayer = modalContext?.registerFloatingLayer?.() || null;
    window.addEventListener('pointerdown', onPointerDown, true);
    window.addEventListener('keydown', onKeydown, true);
    window.addEventListener('resize', schedulePosition);
    window.addEventListener('scroll', schedulePosition, true);
    window.visualViewport?.addEventListener('resize', schedulePosition);
    window.visualViewport?.addEventListener('scroll', schedulePosition);
  }
  panelStyle.value = { visibility: 'hidden' };
  await nextTick();
  observeElements();
  schedulePosition();
}

function deactivate() {
  if (
    animationFrame !== null
    && typeof window !== 'undefined'
    && typeof window.cancelAnimationFrame === 'function'
  ) {
    window.cancelAnimationFrame(animationFrame);
    animationFrame = null;
  }
  anchorObserver?.disconnect();
  panelObserver?.disconnect();
  anchorObserver = null;
  panelObserver = null;
  panelStyle.value = { visibility: 'hidden' };
  if (!isActive || typeof window === 'undefined') return;

  window.removeEventListener('pointerdown', onPointerDown, true);
  window.removeEventListener('keydown', onKeydown, true);
  window.removeEventListener('resize', schedulePosition);
  window.removeEventListener('scroll', schedulePosition, true);
  window.visualViewport?.removeEventListener('resize', schedulePosition);
  window.visualViewport?.removeEventListener('scroll', schedulePosition);
  unregisterFloatingLayer?.();
  unregisterFloatingLayer = null;
  isActive = false;
}

watch(
  () => [props.open, props.anchor, teleportTarget.value],
  async ([open, anchor]) => {
    if (!isMounted.value) return;
    if (open && anchor) await activate();
    else deactivate();
  },
  { flush: 'post' },
);

onMounted(async () => {
  isMounted.value = true;
  if (props.open && props.anchor) await activate();
});

onBeforeUnmount(deactivate);
</script>

<template>
  <Teleport v-if="isMounted && open && teleportTarget" :to="teleportTarget">
    <component
      :is="as"
      :id="id"
      ref="panelRef"
      role="listbox"
      :aria-label="ariaLabel"
      class="pointer-events-auto fixed z-[10020] overflow-y-auto overscroll-contain rounded-xl border border-border-default bg-surface shadow-raised"
      :style="panelStyle"
      data-floating-listbox
      @scroll.passive="onScroll"
    >
      <slot />
    </component>
  </Teleport>
</template>
