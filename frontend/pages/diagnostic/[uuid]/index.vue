<template>
  <div
    class="diagnostic-public min-h-screen py-16 px-4"
    :class="{ dark: isDark }"
    data-testid="diagnostic-public-wrapper"
  >
    <DiagnosticIndex
      v-if="sections.length > 1"
      :sections="sections"
      :current-index="activeIndex"
      :visited-ids="visitedIds"
      @navigate="selectSection"
    />

    <div class="max-w-4xl mx-auto">
      <div v-if="store.isLoading" class="diagnostic-card bg-surface rounded-3xl border border-input-border p-8 space-y-4" aria-busy="true">
        <div class="h-6 w-2/3 rounded bg-surface-raised motion-safe:animate-pulse" />
        <div class="h-3 w-full rounded bg-surface-raised motion-safe:animate-pulse" />
        <div class="h-3 w-5/6 rounded bg-surface-raised motion-safe:animate-pulse" />
        <div class="h-3 w-4/6 rounded bg-surface-raised motion-safe:animate-pulse" />
      </div>

      <div v-else-if="store.error === 'not_found'" class="text-center py-16">
        <p class="text-danger-strong">{{ chrome.notFound }}</p>
      </div>

      <div
        v-else-if="store.error"
        class="diagnostic-card bg-surface rounded-3xl border border-input-border p-8 text-center"
        data-testid="diagnostic-public-error"
      >
        <p class="text-text-default font-medium">{{ chrome.loadErrorTitle }}</p>
        <p class="text-sm text-text-muted mt-2">{{ chrome.loadErrorHint }}</p>
        <button
          type="button"
          class="mt-6 px-6 py-3 bg-primary text-white rounded-xl hover:bg-primary-strong font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:ring-offset-2"
          @click="reloadPublic"
        >{{ chrome.retry }}</button>
      </div>

      <template v-else-if="store.current">
        <!-- Cover: the "made for you" moment -->
        <article
          v-if="showCover"
          class="diagnostic-card bg-surface rounded-3xl shadow-[0_6px_30px_-12px_rgba(0,41,33,0.25)] dark:shadow-[0_6px_30px_-12px_rgba(0,0,0,0.5)] border border-input-border p-8 md:p-16 mb-6 text-center"
          data-testid="diagnostic-cover"
        >
          <p class="text-xs uppercase tracking-[0.25em] text-text-brand/70">{{ chrome.coverKicker }}</p>
          <h1 class="text-3xl md:text-4xl font-semibold text-text-default mt-4">
            {{ store.current.title || chrome.coverFallbackTitle }}
          </h1>
          <p v-if="store.current.client_name" class="mt-4 text-text-muted">
            {{ chrome.preparedFor }} <strong class="text-text-default">{{ store.current.client_name }}</strong>
          </p>
          <p v-if="coverDate" class="text-sm text-text-brand/60 mt-1">{{ coverDate }}</p>
          <button
            type="button"
            data-testid="diagnostic-start-journey"
            class="mt-10 px-8 py-3 bg-primary dark:bg-accent text-accent dark:text-primary rounded-xl hover:bg-primary-strong dark:hover:bg-accent/90 font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:ring-offset-2 motion-safe:transition-colors"
            @click="startJourney"
          >{{ chrome.start }} →</button>
          <p class="text-2xs text-text-brand/50 mt-8 uppercase tracking-widest">ProjectApp</p>
        </article>

        <article
          v-else-if="sections.length"
          class="diagnostic-card bg-surface rounded-3xl shadow-[0_6px_30px_-12px_rgba(0,41,33,0.25)] dark:shadow-[0_6px_30px_-12px_rgba(0,0,0,0.5)] border border-input-border dark:border-input-border p-6 md:p-12 mb-6 text-text-default overflow-hidden"
        >
          <Transition :name="navDirection === 'back' ? 'section-slide-back' : 'section-slide'" mode="out-in">
            <component
              :is="componentFor(activeSection.section_type)"
              :key="activeIndex"
              :content="activeContent"
              :diagnostic="store.current"
              :render-context="store.current.render_context || {}"
            />
          </Transition>
        </article>

        <div
          v-else
          class="diagnostic-card bg-surface rounded-3xl shadow-sm border border-input-border dark:border-input-border p-6 text-center"
        >
          <p class="text-text-default font-medium">{{ emptyStateCopy.title }}</p>
          <p class="text-sm text-text-brand/60 dark:text-text-brand/60 mt-2">{{ emptyStateCopy.hint }}</p>
        </div>

        <!-- Prev / next -->
        <div v-if="!showCover && sections.length > 1" class="section-nav flex justify-between items-center mb-8">
          <button
            class="px-4 py-2 text-sm rounded-lg border border-input-border dark:border-input-border text-text-brand/80 dark:text-text-brand/80 hover:bg-primary/5 dark:hover:bg-primary-soft disabled:opacity-30 focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
            :disabled="activeIndex === 0"
            @click="selectSection(activeIndex - 1)"
          >{{ chrome.prev }}</button>
          <span class="section-counter text-xs text-text-brand/60 dark:text-text-brand/60">{{ chrome.section }} {{ activeIndex + 1 }} {{ chrome.of }} {{ sections.length }}</span>
          <button
            class="px-4 py-2 text-sm rounded-lg border border-input-border dark:border-input-border text-text-brand/80 dark:text-text-brand/80 hover:bg-primary/5 dark:hover:bg-primary-soft disabled:opacity-30 focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
            :disabled="activeIndex === sections.length - 1"
            @click="selectSection(activeIndex + 1)"
          >{{ chrome.next }}</button>
        </div>

        <footer
          v-if="ctaVisible"
          class="diagnostic-card diagnostic-cta mt-8 bg-surface rounded-3xl border border-input-border dark:border-input-border p-6 text-center shadow-sm"
        >
          <p class="text-text-default mb-4">{{ chrome.ctaQuestion }}</p>
          <div class="flex justify-center gap-3 flex-wrap">
            <button
              class="px-6 py-3 bg-primary dark:bg-accent text-accent dark:text-primary rounded-xl hover:bg-primary-strong dark:hover:bg-accent/90 disabled:opacity-50 font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
              :disabled="store.isUpdating"
              @click="askConfirm('accept')"
            >{{ store.isUpdating && pendingDecision === 'accept' ? chrome.sending : chrome.accept }}</button>
            <button
              class="px-6 py-3 border border-danger-strong/30 text-danger-strong rounded-xl hover:bg-danger-soft disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
              :disabled="store.isUpdating"
              @click="askConfirm('reject')"
            >{{ store.isUpdating && pendingDecision === 'reject' ? chrome.sending : chrome.reject }}</button>
          </div>
          <p v-if="responseMsg" class="mt-4 text-sm text-danger-strong">{{ responseMsg }}</p>
        </footer>

        <!-- Respond confirmation -->
        <Teleport to="body">
          <div
            v-if="pendingDecision && !store.isUpdating"
            class="fixed inset-0 z-[9995] flex items-center justify-center p-4"
            :class="{ dark: isDark }"
            role="dialog"
            aria-modal="true"
            aria-labelledby="respond-confirm-title"
          >
            <div class="absolute inset-0 bg-black/50" @click="pendingDecision = null" />
            <div class="relative bg-surface rounded-2xl border border-input-border shadow-xl max-w-sm w-full p-6 text-center">
              <p id="respond-confirm-title" class="text-text-default font-medium">
                {{ pendingDecision === 'accept' ? chrome.confirmAccept : chrome.confirmReject }}
              </p>
              <div class="mt-5 flex justify-center gap-3">
                <button
                  type="button"
                  class="px-5 py-2.5 rounded-xl border border-input-border text-text-muted hover:bg-primary/5 focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
                  @click="pendingDecision = null"
                >{{ chrome.cancel }}</button>
                <button
                  type="button"
                  data-testid="diagnostic-respond-confirm"
                  class="px-5 py-2.5 rounded-xl bg-primary dark:bg-accent text-accent dark:text-primary font-medium hover:bg-primary-strong focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
                  @click="confirmRespond"
                >{{ chrome.confirm }}</button>
              </div>
            </div>
          </div>
        </Teleport>

        <footer
          v-if="store.current.status === DIAGNOSTIC_STATUS.ACCEPTED"
          class="diagnostic-card mt-8 bg-primary/5 dark:bg-primary-soft border border-input-border dark:border-input-border rounded-3xl p-6 text-center text-text-brand dark:text-text-brand"
        >
          ¡Gracias! Confirmamos tu aceptación. Te contactaremos para coordinar el inicio.
        </footer>

        <footer
          v-else-if="store.current.status === DIAGNOSTIC_STATUS.REJECTED"
          class="diagnostic-card mt-8 bg-rose-50 dark:bg-rose-900/20 border border-rose-200 dark:border-rose-400/20 rounded-3xl p-6 text-center text-rose-800 dark:text-rose-200"
        >
          Recibimos tu respuesta. Si cambias de opinión, contáctanos cuando quieras.
        </footer>

        <ShareDiagnosticButton
          v-if="store.current?.uuid"
          :diagnostic-uuid="store.current.uuid"
          :language="store.current.language || 'es'"
        />

        <DownloadDiagnosticPdfButton v-if="store.current?.uuid" />

        <BaseButton
          unstyled
          icon-only
          type="button"
          data-testid="diagnostic-restart-tutorial"
          class="restart-tutorial-btn fixed bottom-[76px] left-6 z-[9990] w-11 h-11 rounded-full
                 bg-surface shadow-lg
                 border border-input-border dark:border-input-border
                 text-text-default
                 flex items-center justify-center
                 hover:bg-primary/5 dark:hover:bg-primary/80
                 focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:ring-offset-2
                 motion-safe:transition-all motion-safe:hover:scale-110"
          :aria-label="restartTutorialLabel"
          :title="restartTutorialLabel"
          @click="onboardingRef?.forceStart()"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </BaseButton>

        <DiagnosticOnboarding
          ref="onboardingRef"
          :language="store.current?.language || 'es'"
        />

        <BaseButton
          unstyled
          icon-only
          type="button"
          data-testid="diagnostic-theme-toggle"
          class="theme-toggle fixed bottom-6 left-6 z-[9990] w-11 h-11 rounded-full
                 bg-surface/90 dark:bg-primary/90 backdrop-blur-sm shadow-lg
                 border border-input-border dark:border-input-border
                 text-text-default
                 flex items-center justify-center
                 hover:bg-primary/5 dark:hover:bg-primary-soft
                 focus:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:ring-offset-2
                 transition-colors"
          :aria-label="isDark ? 'Activar modo claro' : 'Activar modo oscuro'"
          :aria-pressed="isDark"
          @click="toggleDarkMode"
        >
          <!-- Moon (visible in light mode → tap to go dark) -->
          <svg
            v-if="!isDark"
            class="w-5 h-5"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            stroke-width="1.8"
            aria-hidden="true"
          >
            <path stroke-linecap="round" stroke-linejoin="round" d="M21 12.79A9 9 0 1111.21 3a7 7 0 009.79 9.79z" />
          </svg>
          <!-- Sun (visible in dark mode → tap to go light) -->
          <svg
            v-else
            class="w-5 h-5"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            stroke-width="1.8"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="4" stroke-linecap="round" stroke-linejoin="round" />
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 3v1.8M12 19.2V21M4.22 4.22l1.27 1.27M18.51 18.51l1.27 1.27M3 12h1.8M19.2 12H21M4.22 19.78l1.27-1.27M18.51 5.49l1.27-1.27" />
          </svg>
        </BaseButton>
      </template>
    </div>
  </div>
</template>

<script setup>
import { resolveEditorialContent } from '~/utils/editorialMetadata';
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue';
import { useDiagnosticsStore } from '~/stores/diagnostics';
import { DIAGNOSTIC_STATUS } from '~/stores/diagnostics_constants';
import { useDiagnosticDarkMode, DIAGNOSTIC_THEME_STORAGE_KEY } from '~/composables/useDiagnosticDarkMode';

import DiagnosticIndex from '~/components/WebAppDiagnostic/public/DiagnosticIndex.vue';
import PurposeSection from '~/components/WebAppDiagnostic/public/PurposeSection.vue';
import RadiographySection from '~/components/WebAppDiagnostic/public/RadiographySection.vue';
import CategoriesSection from '~/components/WebAppDiagnostic/public/CategoriesSection.vue';
import DeliveryStructureSection from '~/components/WebAppDiagnostic/public/DeliveryStructureSection.vue';
import ExecutiveSummarySection from '~/components/WebAppDiagnostic/public/ExecutiveSummarySection.vue';
import CostSection from '~/components/WebAppDiagnostic/public/CostSection.vue';
import TimelineSection from '~/components/WebAppDiagnostic/public/TimelineSection.vue';
import ScopeSection from '~/components/WebAppDiagnostic/public/ScopeSection.vue';
import ShareDiagnosticButton from '~/components/WebAppDiagnostic/public/ShareDiagnosticButton.vue';
import DownloadDiagnosticPdfButton from '~/components/WebAppDiagnostic/public/DownloadDiagnosticPdfButton.vue';
import DiagnosticOnboarding from '~/components/WebAppDiagnostic/public/DiagnosticOnboarding.vue';

definePageMeta({ layout: false });

// Inline early script: applies the `dark` class to the diagnostic wrapper
// before Vue hydration to prevent a flash of light theme for users who
// previously chose dark or whose system prefers dark. Storage key is shared
// with the composable so they cannot drift.
useHead({
  script: [
    {
      tagPosition: 'bodyClose',
      innerHTML: `(function(){try{var k=${JSON.stringify(DIAGNOSTIC_THEME_STORAGE_KEY)};var v=localStorage.getItem(k);var d=v==='dark'||(v!=='light'&&window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches);if(!d)return;var apply=function(el){if(el)el.classList.add('dark');};var found=document.querySelector('.diagnostic-public');if(found){apply(found);return;}var mo=new MutationObserver(function(){var el=document.querySelector('.diagnostic-public');if(el){apply(el);mo.disconnect();}});mo.observe(document.body,{childList:true});setTimeout(function(){mo.disconnect();},3000);}catch(e){}})();`,
    },
  ],
});

const COMPONENTS = {
  purpose: PurposeSection,
  radiography: RadiographySection,
  categories: CategoriesSection,
  delivery_structure: DeliveryStructureSection,
  executive_summary: ExecutiveSummarySection,
  cost: CostSection,
  timeline: TimelineSection,
  scope: ScopeSection,
};

const CHROME_TEXTS = {
  es: {
    prev: '← Anterior', next: 'Siguiente →', section: 'Sección', of: 'de',
    notFound: 'Diagnóstico no encontrado.',
    loadErrorTitle: 'No pudimos cargar tu diagnóstico.',
    loadErrorHint: 'Puede ser un problema temporal de conexión. Intenta de nuevo en unos segundos.',
    retry: 'Reintentar',
    coverKicker: 'Diagnóstico de aplicación web',
    coverFallbackTitle: 'Tu diagnóstico',
    preparedFor: 'Preparado para',
    start: 'Comenzar recorrido',
    ctaQuestion: '¿Quieres avanzar con el diagnóstico?',
    accept: 'Aceptar propuesta', reject: 'No por ahora', sending: 'Enviando…',
    confirmAccept: '¿Confirmas que quieres avanzar con la propuesta?',
    confirmReject: '¿Confirmas que prefieres no avanzar por ahora?',
    confirm: 'Confirmar', cancel: 'Cancelar',
    respondError: 'No pudimos registrar tu respuesta. Por favor inténtalo nuevamente.',
  },
  en: {
    prev: '← Previous', next: 'Next →', section: 'Section', of: 'of',
    notFound: 'Diagnostic not found.',
    loadErrorTitle: 'We could not load your diagnostic.',
    loadErrorHint: 'It may be a temporary connection issue. Please try again in a few seconds.',
    retry: 'Retry',
    coverKicker: 'Web application diagnostic',
    coverFallbackTitle: 'Your diagnostic',
    preparedFor: 'Prepared for',
    start: 'Start the tour',
    ctaQuestion: 'Would you like to move forward with the diagnostic?',
    accept: 'Accept proposal', reject: 'Not for now', sending: 'Sending…',
    confirmAccept: 'Do you confirm you want to move forward with the proposal?',
    confirmReject: 'Do you confirm you prefer not to move forward for now?',
    confirm: 'Confirm', cancel: 'Cancel',
    respondError: 'We could not register your response. Please try again.',
  },
};

const route = useRoute();
const store = useDiagnosticsStore();
const activeIndex = ref(0);
const responseMsg = ref('');
const coverDismissed = ref(false);
const pendingDecision = ref(null);
const navDirection = ref('forward');

const chrome = computed(() => CHROME_TEXTS[store.current?.language === 'en' ? 'en' : 'es']);

const showCover = computed(() =>
  !coverDismissed.value && sections.value.length > 0,
);

const coverDate = computed(() => {
  const iso = store.current?.final_sent_at || store.current?.initial_sent_at || store.current?.created_at;
  if (!iso) return '';
  const locale = store.current?.language === 'en' ? 'en-US' : 'es-CO';
  return new Date(iso).toLocaleDateString(locale, { day: 'numeric', month: 'long', year: 'numeric' });
});

function startJourney() {
  coverDismissed.value = true;
  sectionEnteredAt.value = Date.now();
  markSectionVisited(sections.value[activeIndex.value]?.id);
  if (!isPreview.value) nextTick(() => onboardingRef.value?.start());
}

async function reloadPublic() {
  await store.fetchPublic(route.params.uuid);
}
const sessionId = ref('');
const sectionEnteredAt = ref(0);
const visitedIds = ref(new Set());
const onboardingRef = ref(null);

const restartTutorialLabel = computed(() => (
  (store.current?.language || 'es') === 'en' ? 'Restart guide' : 'Reiniciar guía'
));

// Skip all tracking pings when an admin previews with ?preview=1.
const isPreview = computed(() => route.query?.preview === '1');

const { isDark, toggle: toggleDarkMode, hydrate: hydrateTheme } = useDiagnosticDarkMode();

const sections = computed(() => store.current?.sections || []);
const activeSection = computed(() => sections.value[activeIndex.value] || null);
const activeContent = computed(() => ({
  ...resolveEditorialContent(activeSection.value?.content_json, activeSection.value?.text_formats, '/content_json'),
  index: String(activeIndex.value + 1),
}));

const canRespond = computed(() => (
  store.current?.status === DIAGNOSTIC_STATUS.SENT
  && !!store.current?.final_sent_at
));

// The accept/reject moment belongs to the end of the story: show it once the
// reader is on the last section or has already visited the cost section.
const ctaVisible = computed(() => {
  if (!canRespond.value || showCover.value) return false;
  if (activeIndex.value === sections.value.length - 1) return true;
  const costSection = sections.value.find((s) => s.section_type === 'cost');
  return costSection ? visitedIds.value.has(costSection.id) : false;
});

const EMPTY_STATE_COPY = {
  [DIAGNOSTIC_STATUS.DRAFT]: {
    title: 'Este diagnóstico todavía no está publicado.',
    hint: 'Nuestro equipo está preparando el contenido. Te avisaremos cuando esté listo para revisar.',
  },
  [DIAGNOSTIC_STATUS.EXPIRED]: {
    title: 'Este diagnóstico ha expirado.',
    hint: 'Si todavía te interesa avanzar, contáctanos y lo reactivamos.',
  },
  [DIAGNOSTIC_STATUS.FINISHED]: {
    title: 'Este diagnóstico ya fue finalizado.',
    hint: 'Si necesitas consultar la información, escríbenos y te ayudamos.',
  },
};
const DEFAULT_EMPTY_STATE = {
  title: 'No hay secciones disponibles en este momento.',
  hint: 'Si crees que es un error, por favor contáctanos.',
};

const emptyStateCopy = computed(
  () => EMPTY_STATE_COPY[store.current?.status] || DEFAULT_EMPTY_STATE,
);

function componentFor(type) {
  return COMPONENTS[type] || null;
}

function markSectionVisited(id) {
  if (id == null) return;
  const next = new Set(visitedIds.value);
  next.add(id);
  visitedIds.value = next;
}

function selectSection(idx) {
  flushSectionTracking();
  navDirection.value = idx < activeIndex.value ? 'back' : 'forward';
  activeIndex.value = Math.max(0, Math.min(idx, sections.value.length - 1));
  sectionEnteredAt.value = Date.now();
  markSectionVisited(sections.value[activeIndex.value]?.id);
}

function flushSectionTracking({ beacon = false } = {}) {
  if (isPreview.value || showCover.value) return;
  if (!sessionId.value || !activeSection.value) return;
  const elapsed = (Date.now() - sectionEnteredAt.value) / 1000;
  if (elapsed < 1) return;
  const payload = {
    session_id: sessionId.value,
    section_type: activeSection.value.section_type,
    section_title: activeSection.value.title || '',
    time_spent_seconds: Math.round(elapsed * 10) / 10,
    entered_at: new Date(sectionEnteredAt.value).toISOString(),
  };
  if (beacon && typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
    try {
      const blob = new Blob([JSON.stringify(payload)], { type: 'application/json' });
      navigator.sendBeacon(
        `/api/diagnostics/public/${route.params.uuid}/track-section/`,
        blob,
      );
      return;
    } catch (_) { /* fall through to fetch */ }
  }
  store.trackSectionView(route.params.uuid, payload);
}

function askConfirm(decision) {
  responseMsg.value = '';
  pendingDecision.value = decision;
}

async function confirmRespond() {
  const decision = pendingDecision.value;
  if (!decision) return;
  responseMsg.value = '';
  const r = await store.respondPublic(route.params.uuid, decision);
  pendingDecision.value = null;
  if (!r.success) {
    responseMsg.value = chrome.value.respondError;
  }
}

function generateSessionId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return 'sess-' + crypto.randomUUID();
  }
  return 'sess-' + Math.random().toString(36).slice(2) + Date.now().toString(36);
}

onMounted(async () => {
  hydrateTheme();
  sessionId.value = generateSessionId();
  await Promise.all([
    store.fetchPublic(route.params.uuid),
    isPreview.value ? null : store.trackView(route.params.uuid, sessionId.value),
  ]);
  sectionEnteredAt.value = Date.now();
  markSectionVisited(sections.value[activeIndex.value]?.id);
});

onBeforeUnmount(() => flushSectionTracking({ beacon: true }));
</script>

<style scoped>
.diagnostic-public {
  background-color: #ffffff;
  background-image:
    radial-gradient(ellipse 80% 60% at 50% 0%, rgba(0, 41, 33, 0.04) 0%, transparent 60%),
    radial-gradient(ellipse 60% 50% at 80% 100%, rgba(0, 41, 33, 0.03) 0%, transparent 55%);
  background-attachment: fixed;
  transition: background-color 0.25s ease;
}

.diagnostic-public.dark {
  background-color: #001713;
  background-image:
    radial-gradient(ellipse 80% 60% at 50% 0%, rgba(240, 255, 61, 0.06) 0%, transparent 60%),
    radial-gradient(ellipse 60% 50% at 80% 100%, rgba(16, 185, 129, 0.05) 0%, transparent 50%);
}

.section-slide-enter-active,
.section-slide-leave-active,
.section-slide-back-enter-active,
.section-slide-back-leave-active {
  transition: opacity 0.25s cubic-bezier(0.22, 1, 0.36, 1), transform 0.25s cubic-bezier(0.22, 1, 0.36, 1);
}
.section-slide-enter-from { opacity: 0; transform: translateX(24px); }
.section-slide-leave-to { opacity: 0; transform: translateX(-24px); }
.section-slide-back-enter-from { opacity: 0; transform: translateX(-24px); }
.section-slide-back-leave-to { opacity: 0; transform: translateX(24px); }
@media (prefers-reduced-motion: reduce) {
  .section-slide-enter-active,
  .section-slide-leave-active,
  .section-slide-back-enter-active,
  .section-slide-back-leave-active {
    transition: none;
  }
}

.theme-toggle {
  transition: background-color 0.2s ease, transform 0.2s ease;
}
.theme-toggle:hover {
  transform: scale(1.05);
}
</style>
