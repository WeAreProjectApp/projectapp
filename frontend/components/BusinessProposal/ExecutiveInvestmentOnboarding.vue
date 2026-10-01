<template>
  <Teleport to="body">
    <!-- Backdrop overlay (blur + dim) -->
    <Transition name="exo-fade">
      <div
        v-if="visible"
        class="onb-backdrop fixed inset-0 z-[9998] bg-surface-muted/60 backdrop-blur-[2px]"
        :data-theme="isDark ? 'dark' : 'light'"
      />
    </Transition>

    <!-- Cloned target element (crisp, above blur) -->
    <div
      v-if="visible"
      ref="cloneContainerRef"
      class="fixed z-[9999] pointer-events-none"
      :style="cloneStyle"
    />

    <!-- Spotlight ring around clone -->
    <Transition name="exo-fade">
      <div
        v-if="visible && spotlightRect"
        class="fixed z-[9999] pointer-events-none rounded-2xl
               ring-[3px] ring-green-light/60
               transition-all duration-400 ease-out"
        :style="spotlightStyle"
      />
    </Transition>

    <!-- Tooltip card -->
    <Transition name="exo-tooltip-pop" mode="out-in">
      <div
        v-if="visible"
        :key="currentStep"
        ref="tooltipRef"
        class="fixed z-[10000]"
        :data-theme="isDark ? 'dark' : 'light'"
        :style="tooltipStyle"
      >
        <!-- Arrow -->
        <div
          class="tooltip-arrow absolute w-3 h-3 bg-surface rotate-45 border border-border-default"
          :style="arrowComputedStyle"
        />

        <!-- Content card -->
        <div class="relative bg-surface rounded-2xl shadow-overlay border border-border-default p-5 w-[272px] sm:w-[296px]">
          <!-- Progress dots -->
          <div class="flex items-center gap-1.5 mb-3">
            <div
              v-for="i in totalSteps"
              :key="i"
              class="h-1.5 rounded-full transition-all duration-300"
              :class="i - 1 === currentStep
                ? 'w-5 bg-primary'
                : i - 1 < currentStep
                  ? 'w-1.5 bg-primary/40'
                  : 'w-1.5 bg-border-default'"
            />
            <span class="ml-auto text-[10px] text-text-subtle font-medium tabular-nums">
              {{ currentStep + 1 }}/{{ totalSteps }}
            </span>
          </div>

          <!-- Step content -->
          <h4 class="text-sm font-bold text-text-default mb-1">{{ currentStepData.title }}</h4>
          <p class="text-xs text-text-muted leading-relaxed mb-4">{{ currentStepData.description }}</p>

          <!-- Actions -->
          <div class="flex items-center justify-between">
            <button
              class="text-xs text-text-subtle hover:text-text-muted transition-colors pointer-events-auto"
              @click="dismiss"
            >
              {{ btnLabels.skip }}
            </button>
            <div class="flex items-center gap-2">
              <button
                v-if="currentStep > 0"
                class="px-3 py-1.5 text-xs text-text-muted hover:text-text-default transition-colors pointer-events-auto"
                @click="prev"
              >
                {{ btnLabels.back }}
              </button>
              <button
                class="px-4 py-1.5 text-xs font-medium text-white bg-primary rounded-lg
                       hover:bg-primary/90 transition-colors shadow-sm pointer-events-auto"
                @click="next"
              >
                {{ isLastStep ? btnLabels.done : btnLabels.next }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>

  </Teleport>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue';
import { useProposalDarkMode } from '~/composables/useProposalDarkMode';
import { smoothScrollTo, smoothScrollToElement } from '~/composables/useSmoothScroll';

const STORAGE_KEY_PREFIX = 'executive_investment_onboarding_seen';
const TOOLTIP_W = 296;
const TOOLTIP_H_EST = 190;
const GAP = 14;
const ARROW_SIZE = 6;
const VIEWPORT_PAD = 12;

const { isDark } = useProposalDarkMode();

const props = defineProps({
  language: { type: String, default: 'es' },
  proposalUuid: { type: String, default: '' },
});

const emit = defineEmits(['complete']);

const visible = ref(false);
const currentStep = ref(0);
const tooltipRef = ref(null);
const cloneContainerRef = ref(null);

const spotlightRect = ref(null);
const cloneStyle = ref({});
const tooltipStyle = ref({});
const arrowComputedStyle = ref({});

const stepsI18n = {
  es: [
    { target: '.switch-to-detailed-btn', title: 'Descubre la propuesta completa', description: 'Este botón te lleva a la versión detallada donde encontrarás todos los módulos de tu proyecto, un catálogo de módulos adicionales para explorar y guardar tu interés, y mucho más.', prefer: 'bottom' },
  ],
  en: [
    { target: '.switch-to-detailed-btn', title: 'Discover the full proposal', description: 'This button takes you to the detailed version where you\'ll find all your project modules, an additional-module catalog to explore and save your interests, and much more.', prefer: 'bottom' },
  ],
};
const steps = computed(() => stepsI18n[props.language] || stepsI18n.es);

const btnLabels = computed(() => props.language === 'en'
  ? { skip: 'Skip', back: 'Back', next: 'Next', done: 'Got it' }
  : { skip: 'Omitir', back: 'Atrás', next: 'Siguiente', done: 'Entendido' }
);

const activeSteps = ref([]);
const totalSteps = computed(() => activeSteps.value.length);
const currentStepData = computed(() => activeSteps.value[currentStep.value] || steps.value[0]);
const isLastStep = computed(() => currentStep.value === activeSteps.value.length - 1);

const spotlightStyle = computed(() => {
  if (!spotlightRect.value) return { display: 'none' };
  const r = spotlightRect.value;
  const pad = 4;
  return {
    top: `${r.top - pad}px`,
    left: `${r.left - pad}px`,
    width: `${r.width + pad * 2}px`,
    height: `${r.height + pad * 2}px`,
  };
});

function getRect(selector) {
  const el = document.querySelector(selector);
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return { top: r.top, left: r.left, width: r.width, height: r.height, bottom: r.bottom, right: r.right, el };
}

function cloneTarget(rect) {
  if (!cloneContainerRef.value || !rect?.el) return;
  cloneContainerRef.value.innerHTML = '';
  const clone = rect.el.cloneNode(true);
  clone.removeAttribute('class');
  const cs = window.getComputedStyle(rect.el);
  const skip = new Set([
    'position', 'top', 'right', 'bottom', 'left',
    'transform', 'translate', 'margin',
    'margin-top', 'margin-right', 'margin-bottom', 'margin-left',
    'z-index', 'animation', 'animation-name', 'animation-duration',
    'animation-delay', 'animation-fill-mode',
  ]);
  for (const prop of cs) {
    if (skip.has(prop)) continue;
    try { clone.style.setProperty(prop, cs.getPropertyValue(prop)); } catch { /* skip */ }
  }
  clone.style.pointerEvents = 'none';
  cloneContainerRef.value.appendChild(clone);
  cloneStyle.value = {
    top: `${rect.top}px`,
    left: `${rect.left}px`,
    width: `${rect.width}px`,
    height: `${rect.height}px`,
    overflow: 'hidden',
  };
}

function computePosition(rect, prefer) {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const cx = rect.left + rect.width / 2;
  const cy = rect.top + rect.height / 2;

  const sides = [prefer, 'top', 'bottom', 'right', 'left'].filter((v, i, a) => a.indexOf(v) === i);

  for (const side of sides) {
    const pos = calcSidePosition(side, rect, vw, vh, cx, cy);
    if (pos) return pos;
  }
  return {
    style: { top: '50%', left: '50%', transform: 'translate(-50%, -50%)' },
    arrow: { display: 'none' },
    side: 'center',
  };
}

function calcSidePosition(side, rect, vw, vh, cx, cy) {
  let tipTop, tipLeft, arrowSty;

  if (side === 'right') {
    tipLeft = rect.right + GAP;
    if (tipLeft + TOOLTIP_W > vw - VIEWPORT_PAD) return null;
    tipTop = clampVertical(cy - TOOLTIP_H_EST / 2, vh);
    const arrowTop = Math.max(16, Math.min(TOOLTIP_H_EST - 24, cy - tipTop));
    arrowSty = { top: `${arrowTop}px`, left: `-${ARROW_SIZE}px`, transform: 'rotate(45deg)', borderRight: 'none', borderTop: 'none' };
    return { style: { top: `${tipTop}px`, left: `${tipLeft}px` }, arrow: arrowSty, side };
  }

  if (side === 'left') {
    tipLeft = rect.left - GAP - TOOLTIP_W;
    if (tipLeft < VIEWPORT_PAD) return null;
    tipTop = clampVertical(cy - TOOLTIP_H_EST / 2, vh);
    const arrowTop = Math.max(16, Math.min(TOOLTIP_H_EST - 24, cy - tipTop));
    arrowSty = { top: `${arrowTop}px`, right: `-${ARROW_SIZE}px`, transform: 'rotate(45deg)', borderLeft: 'none', borderBottom: 'none' };
    return { style: { top: `${tipTop}px`, left: `${tipLeft}px` }, arrow: arrowSty, side };
  }

  if (side === 'bottom') {
    tipTop = rect.bottom + GAP;
    if (tipTop + TOOLTIP_H_EST > vh - VIEWPORT_PAD) return null;
    tipLeft = clampHorizontal(cx - TOOLTIP_W / 2, vw);
    const arrowLeft = Math.max(20, Math.min(TOOLTIP_W - 28, cx - tipLeft));
    arrowSty = { top: `-${ARROW_SIZE}px`, left: `${arrowLeft}px`, transform: 'rotate(45deg)', borderBottom: 'none', borderRight: 'none' };
    return { style: { top: `${tipTop}px`, left: `${tipLeft}px` }, arrow: arrowSty, side };
  }

  if (side === 'top') {
    tipTop = rect.top - GAP - TOOLTIP_H_EST;
    if (tipTop < VIEWPORT_PAD) return null;
    tipLeft = clampHorizontal(cx - TOOLTIP_W / 2, vw);
    const arrowLeft = Math.max(20, Math.min(TOOLTIP_W - 28, cx - tipLeft));
    arrowSty = { bottom: `-${ARROW_SIZE}px`, left: `${arrowLeft}px`, transform: 'rotate(45deg)', borderTop: 'none', borderLeft: 'none' };
    return { style: { top: `${tipTop}px`, left: `${tipLeft}px` }, arrow: arrowSty, side };
  }

  return null;
}

function clampVertical(top, vh) {
  return Math.max(VIEWPORT_PAD, Math.min(vh - TOOLTIP_H_EST - VIEWPORT_PAD, top));
}

function clampHorizontal(left, vw) {
  return Math.max(VIEWPORT_PAD, Math.min(vw - TOOLTIP_W - VIEWPORT_PAD, left));
}

async function scrollAndPosition() {
  const step = currentStepData.value;
  const el = document.querySelector(step.target);
  if (el) {
    // Place button near top of viewport so tooltip has room below
    await smoothScrollToElement(el, { duration: 2200, viewportOffset: 0.15 });
    positionAll();
    await new Promise(r => setTimeout(r, 300));
    positionAll();
  } else {
    positionAll();
  }
}

function positionAll() {
  const step = currentStepData.value;
  const rect = getRect(step.target);

  if (!rect) {
    spotlightRect.value = null;
    cloneStyle.value = { display: 'none' };
    tooltipStyle.value = { top: '50%', left: '50%', transform: 'translate(-50%, -50%)' };
    arrowComputedStyle.value = { display: 'none' };
    return;
  }

  spotlightRect.value = rect;
  cloneTarget(rect);

  const pos = computePosition(rect, step.prefer);
  tooltipStyle.value = pos.style;
  arrowComputedStyle.value = pos.arrow;
}

function next() {
  if (isLastStep.value) { dismiss(); return; }
  currentStep.value++;
  nextTick(scrollAndPosition);
}

function prev() {
  if (currentStep.value > 0) {
    currentStep.value--;
    nextTick(scrollAndPosition);
  }
}

function dismiss() {
  if (cloneContainerRef.value) cloneContainerRef.value.innerHTML = '';
  spotlightRect.value = null;
  cloneStyle.value = { display: 'none' };
  tooltipStyle.value = { display: 'none' };
  visible.value = false;
  const storageKey = props.proposalUuid
    ? `${STORAGE_KEY_PREFIX}_${props.proposalUuid}`
    : STORAGE_KEY_PREFIX;
  try { localStorage.setItem(storageKey, 'true'); } catch { /* noop */ }
  smoothScrollTo(0, 2200);
  emit('complete');
}

function start() {
  const storageKey = props.proposalUuid
    ? `${STORAGE_KEY_PREFIX}_${props.proposalUuid}`
    : STORAGE_KEY_PREFIX;
  try { if (localStorage.getItem(storageKey)) return; } catch { /* noop */ }

  setTimeout(() => {
    activeSteps.value = steps.value.filter((s) => document.querySelector(s.target));
    if (!activeSteps.value.length) return;
    currentStep.value = 0;
    visible.value = true;
    nextTick(scrollAndPosition);
  }, 1200);
}

function onResize() {
  if (visible.value) positionAll();
}

onMounted(() => {
  window.addEventListener('resize', onResize);
});
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize);
});

defineExpose({ start });
</script>

<style scoped>
.exo-fade-enter-active,
.exo-fade-leave-active {
  transition: opacity 0.3s ease;
}
.exo-fade-enter-from,
.exo-fade-leave-to {
  opacity: 0;
}

.exo-tooltip-pop-enter-active {
  transition: opacity 0.3s ease, transform 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.exo-tooltip-pop-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.exo-tooltip-pop-enter-from {
  opacity: 0;
  transform: scale(0.92);
}
.exo-tooltip-pop-leave-to {
  opacity: 0;
  transform: scale(0.96);
}

.tooltip-arrow {
  z-index: -1;
}
</style>
