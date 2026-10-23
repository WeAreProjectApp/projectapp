<template>
  <Teleport to="body">
    <!-- Backdrop overlay (blur + dark) -->
    <Transition name="fade">
      <div
        v-if="visible"
        data-testid="onboarding-backdrop"
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
    <Transition name="fade">
      <div
        v-if="visible && spotlightRect"
        class="fixed z-[9999] pointer-events-none rounded-2xl
               ring-[3px] ring-green-light/60
               transition-all duration-400 ease-out"
        :style="spotlightStyle"
      />
    </Transition>

    <!-- Tooltip card -->
    <Transition name="tooltip-pop" mode="out-in">
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
                  ? 'w-1.5 bg-esmerald/40'
                  : 'w-1.5 bg-border-default'"
            />
            <span data-testid="onboarding-step-progress" class="ml-auto text-[10px] text-text-subtle font-medium tabular-nums">
              {{ currentStep + 1 }}/{{ totalSteps }}
            </span>
          </div>

          <!-- Step content -->
          <h4 class="text-sm font-bold text-text-default mb-1">{{ currentStepData.title }}</h4>
          <BaseRichTextContent class="text-xs text-text-muted leading-relaxed mb-4" :source="currentStepData.description" :format="currentStepData.text_formats?.['/description'] || 'plain'" />

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
                :data-testid="isLastStep ? 'onboarding-done-btn' : 'onboarding-next-btn'"
                class="px-4 py-1.5 text-xs font-medium text-white bg-primary rounded-lg
                       hover:bg-primary-strong transition-colors shadow-sm pointer-events-auto"
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

const STORAGE_KEY = 'proposal_onboarding_seen';
const TOOLTIP_W = 296;
const TOOLTIP_H_EST = 190;
const GAP = 14;
const ARROW_SIZE = 6;
const VIEWPORT_PAD = 12;


const { isDark } = useProposalDarkMode();

const props = defineProps({
  language: { type: String, default: 'es' },
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
    { target: '.dark-mode-toggle', title: 'Modo claro y oscuro', description: 'Cambia entre modo claro y oscuro para leer la propuesta como prefieras. Tu preferencia se guarda automáticamente.', prefer: 'right' },
    { target: '.index-toggle', title: 'Índice de secciones', description: 'Abre el índice para navegar entre las secciones de la propuesta. Puedes saltar directamente a cualquier parte.', prefer: 'right' },
    { target: '.nav-side--right', title: 'Navegar entre secciones', description: 'Usa las flechas laterales para avanzar o retroceder. También puedes usar las flechas del teclado o deslizar en móvil.', prefer: 'left' },
    { target: '.section-counter', title: 'Progreso', description: 'Aquí puedes ver en qué sección estás y cuántas hay en total.', prefer: 'bottom' },
    { target: '.expiration-badge', title: 'Vigencia de la propuesta', description: 'Esta propuesta tiene fecha de expiración. Aquí verás el tiempo restante para revisarla y tomar una decisión.', prefer: 'bottom', optional: true },
    { target: '.share-btn', title: 'Compartir propuesta', description: 'Comparte el enlace de esta propuesta con tu equipo o socios para que puedan revisarla juntos.', prefer: 'top' },
    { target: '.pdf-download', title: 'Descargar como PDF', description: 'Puedes descargar toda la propuesta en formato PDF para revisarla offline o compartirla con tu equipo.', prefer: 'top' },
    { target: '.restart-tutorial-btn', title: 'Repetir tutorial', description: 'Si necesitas recordar cómo navegar la propuesta, puedes reiniciar este tutorial en cualquier momento desde este botón.', prefer: 'right' },
  ],
  en: [
    { target: '.dark-mode-toggle', title: 'Light & Dark Mode', description: 'Switch between light and dark mode to read the proposal however you prefer. Your preference is saved automatically.', prefer: 'right' },
    { target: '.index-toggle', title: 'Section Index', description: 'Open the index to navigate between proposal sections. You can jump directly to any part.', prefer: 'right' },
    { target: '.nav-side--right', title: 'Navigate Sections', description: 'Use the side arrows to go forward or back. You can also use keyboard arrows or swipe on mobile.', prefer: 'left' },
    { target: '.section-counter', title: 'Progress', description: 'See which section you are on and how many there are in total.', prefer: 'bottom' },
    { target: '.expiration-badge', title: 'Proposal Validity', description: 'This proposal has an expiration date. Here you can see the remaining time to review and decide.', prefer: 'bottom', optional: true },
    { target: '.share-btn', title: 'Share Proposal', description: 'Share the proposal link with your team or partners so they can review it together.', prefer: 'top' },
    { target: '.pdf-download', title: 'Download as PDF', description: 'Download the entire proposal as a PDF to review offline or share with your team.', prefer: 'top' },
    { target: '.restart-tutorial-btn', title: 'Restart Tutorial', description: 'If you need a reminder on how to navigate the proposal, you can restart this tutorial anytime from this button.', prefer: 'right' },
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
  // Copy computed styles but strip positioning/transform
  // getBoundingClientRect already accounts for transforms
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

  // Try preferred side first, then fallback order
  const sides = [prefer, 'bottom', 'right', 'left', 'top'].filter((v, i, a) => a.indexOf(v) === i);

  for (const side of sides) {
    const pos = calcSidePosition(side, rect, vw, vh, cx, cy);
    if (pos) return pos;
  }
  // Absolute fallback: center of screen
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
  nextTick(positionAll);
}

function prev() {
  if (currentStep.value > 0) {
    currentStep.value--;
    nextTick(positionAll);
  }
}

function dismiss() {
  if (cloneContainerRef.value) cloneContainerRef.value.innerHTML = '';
  spotlightRect.value = null;
  cloneStyle.value = { display: 'none' };
  tooltipStyle.value = { display: 'none' };
  visible.value = false;
  try { localStorage.setItem(STORAGE_KEY, 'true'); } catch { /* noop */ }
  emit('complete');
}

function start() {
  try { if (localStorage.getItem(STORAGE_KEY)) return; } catch { /* noop */ }

  setTimeout(() => {
    // Compute active steps at runtime (some elements may not exist)
    activeSteps.value = steps.value.filter((s) => !s.optional || document.querySelector(s.target));
    if (!activeSteps.value.length) return;
    currentStep.value = 0;
    visible.value = true;
    nextTick(positionAll);
  }, 800);
}

function forceStart() {
  try { localStorage.removeItem(STORAGE_KEY); } catch { /* noop */ }
  setTimeout(() => {
    activeSteps.value = steps.value.filter((s) => !s.optional || document.querySelector(s.target));
    if (!activeSteps.value.length) return;
    currentStep.value = 0;
    visible.value = true;
    nextTick(positionAll);
  }, 300);
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

defineExpose({ start, forceStart });
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.tooltip-pop-enter-active {
  transition: opacity 0.3s ease, transform 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.tooltip-pop-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.tooltip-pop-enter-from {
  opacity: 0;
  transform: scale(0.92);
}
.tooltip-pop-leave-to {
  opacity: 0;
  transform: scale(0.96);
}

.tooltip-arrow {
  z-index: -1;
}
</style>
