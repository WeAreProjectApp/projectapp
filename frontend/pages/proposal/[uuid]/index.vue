<template>
  <div class="business-proposal" :class="(proposalDarkMode && viewMode) ? 'bg-[#0a1f1c]' : 'bg-surface'">
    <!-- Loading state -->
    <PreloaderAnimation
      v-if="!showContent && !loadError"
      :active="true"
      :clientName="proposal?.client_name || ''"
      :language="pLang"
      @animationComplete="onAnimationComplete"
    />

    <!-- Error state -->
    <div v-else-if="loadError === 'not_found'" class="min-h-screen flex items-center justify-center">
      <div class="text-center">
        <h1 class="text-4xl font-light text-text-subtle mb-4">404</h1>
        <p class="text-text-muted">{{ browserLang === 'es' ? 'Esta propuesta no fue encontrada.' : 'This proposal was not found.' }}</p>
      </div>
    </div>

    <!-- Expired state (legacy 410 fallback — no full data available) -->
    <ProposalExpired v-else-if="loadError === 'expired'" :proposal="proposal" />

    <!-- Main proposal view -->
    <div
      v-else-if="showContent && proposal"
      ref="proposalContainer"
      class="proposal-wrapper"
      data-proposal-wrapper
      @touchstart.passive="onTouchStart"
      @touchend.passive="onTouchEnd"
    >
      <!-- Expired proposal banner — persistent, shown over full proposal -->
      <div v-if="isExpired" class="fixed top-0 left-0 right-0 z-[9998] bg-gradient-to-r from-amber-500 to-orange-500 text-white shadow-lg">
        <div class="max-w-4xl mx-auto px-4 py-3 flex flex-col sm:flex-row items-center justify-between gap-2 text-center sm:text-left">
          <div class="flex items-center gap-2">
            <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            <span class="text-sm font-medium">
              {{ pLang === 'es'
                ? `Esta propuesta expiró${expiredAtFormatted ? ' el ' + expiredAtFormatted : ''}. ¿Quieres que ${expiredSellerName} te envíe una versión actualizada?`
                : `This proposal expired${expiredAtFormatted ? ' on ' + expiredAtFormatted : ''}. Want ${expiredSellerName} to send you an updated version?`
              }}
            </span>
          </div>
          <a
            v-if="expiredWhatsappUrl"
            :href="expiredWhatsappUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex items-center gap-1.5 px-4 py-1.5 bg-surface text-amber-700 rounded-lg text-sm font-semibold hover:bg-amber-50 transition-colors flex-shrink-0"
          >
            <svg class="w-4 h-4" viewBox="0 0 448 512" fill="currentColor"><path d="M380.9 97.1C339 55.1 283.2 32 223.9 32c-122.4 0-222 99.6-222 222 0 39.1 10.2 77.3 29.6 111L0 480l117.7-30.9c32.4 17.7 68.9 27 106.1 27h.1c122.3 0 224.1-99.6 224.1-222 0-59.3-25.2-115-67.1-157"/></svg>
            {{ pLang === 'es' ? 'Contactar por WhatsApp' : 'Contact via WhatsApp' }}
          </a>
        </div>
      </div>

      <!-- Preview mode banner -->
      <div v-if="isPreviewMode" class="fixed top-0 left-0 right-0 z-[9999] bg-amber-500 text-white text-center py-2 text-xs font-semibold tracking-wide shadow-md">
        👁 {{ pLang === 'es' ? 'MODO PREVIEW — El cliente no ve este banner' : 'PREVIEW MODE — The client does not see this banner' }}
        <button class="ml-4 underline text-white/80 hover:text-white" @click="exitPreview">{{ pLang === 'es' ? 'Volver al panel' : 'Back to panel' }}</button>
      </div>

      <!-- View mode gateway: shown when user hasn't chosen a view yet -->
      <Transition name="gateway-reveal">
        <ProposalViewGateway
          v-if="!viewMode"
          :language="pLang"
          :clientName="proposal.client_name || ''"
          :show-technical="hasTechnicalDocument"
          :show-legal="hasContractTerms"
          :show-explainer-video="proposal.show_explainer_video === true"
          :explainer-resource="proposal.explainer_video"
          @select="handleViewModeSelect"
        />
      </Transition>

      <GatewayGuide v-if="!viewMode" :language="pLang" />

      <!-- Proposal sections: shown after view mode is chosen -->
      <template v-if="viewMode">
        <!-- UX overlay elements -->
        <ProposalIndex
          :sections="displayPanels"
          :currentIndex="currentIndex"
          :visitedPanelIds="visitedPanelIds"
          :viewMode="viewMode"
          :language="pLang"
          :bannerActive="isExpired"
          @navigate="handleNavigate"
          @update:open="(val) => indexOpen = val"
          @switchToDetailed="handleSwitchToDetailed"
          @backToGateway="handleBackToGateway"
        />
        <SectionCounter :current="currentIndex + 1" :total="totalSections" />
        <ExpirationBadge v-if="proposal.expires_at && !isProposalResolved" :expiresAt="proposal.expires_at" />

        <!-- PDF download + Share -->
        <PdfDownloadButton
          :view-mode="viewMode"
        />
        <ShareProposalButton
          v-if="proposal?.uuid"
          :proposalUuid="proposal.uuid"
          :language="proposal?.language || 'es'"
        />

        <!-- Restart tutorial button -->
        <BaseButton
          unstyled
          icon-only
          v-if="viewMode && !isDocumentView"
          :aria-label="pLang === 'es' ? 'Reiniciar tutorial' : 'Restart tutorial'"
          class="restart-tutorial-btn fixed bottom-[72px] left-4 z-[9990] flex h-11 w-11 items-center justify-center rounded-full border border-border-default bg-surface text-text-brand shadow-raised transition-all hover:scale-110 hover:bg-surface-muted sm:left-6"
          :title="pLang === 'es' ? 'Reiniciar tutorial' : 'Restart tutorial'"
          @click="onboardingRef?.forceStart()"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </BaseButton>

        <!-- Dark mode toggle -->
        <BaseButton
          unstyled
          icon-only
          v-if="viewMode"
          :aria-label="pLang === 'es' ? 'Cambiar tema' : 'Toggle theme'"
          class="dark-mode-toggle fixed bottom-4 left-4 z-[9990] flex h-11 w-11 items-center justify-center rounded-full border border-border-default bg-surface text-lg text-text-muted shadow-raised transition-all hover:scale-110 hover:bg-surface-muted sm:bottom-6 sm:left-6"
          :title="pLang === 'es' ? 'Cambiar tema' : 'Toggle theme'"
          @click="toggleProposalDarkMode"
        >
          {{ proposalDarkMode ? '&#9728;&#65039;' : '&#127769;' }}
        </BaseButton>

        <!-- Onboarding tutorial tooltips -->
        <ProposalOnboarding
          v-if="!isDocumentView"
          ref="onboardingRef"
          :language="pLang"
          @complete="showReadingTimePopup"
        />

        <!-- Investment section onboarding (customize button tutorial) -->
        <InvestmentOnboarding
          v-if="viewMode === 'detailed'"
          ref="investmentOnboardingRef"
          :language="pLang"
          :proposalUuid="proposal?.uuid || ''"
          :hasModules="investmentHasModules"
        />

        <!-- Executive mode: teaser button onboarding -->
        <ExecutiveInvestmentOnboarding
          v-if="viewMode === 'executive'"
          ref="executiveInvestmentOnboardingRef"
          :language="pLang"
          :proposalUuid="proposal?.uuid || ''"
        />

        <!-- Functional requirements onboarding (click cards tutorial) -->
        <RequirementsOnboarding
          v-if="!isDocumentView"
          ref="requirementsOnboardingRef"
          :language="pLang"
          :proposalUuid="proposal?.uuid || ''"
        />



      <!-- View mode transition overlay (used for gateway selection + switch-to-detailed) -->
      <Teleport to="body">
        <Transition name="switch-mode-overlay">
          <div v-if="switchOverlayVisible" class="fixed inset-0 z-[10001] flex items-center justify-center bg-primary">
            <div class="text-center px-6">
              <div class="w-16 h-16 bg-accent rounded-2xl flex items-center justify-center mx-auto mb-6 animate-bounce">
                <svg v-if="switchOverlayMode === 'executive'" class="w-8 h-8 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                <svg v-else-if="switchOverlayMode === 'technical'" class="w-8 h-8 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                </svg>
                <svg v-else-if="switchOverlayMode === 'legal'" class="w-8 h-8 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <svg v-else-if="switchOverlayMode === 'gateway'" class="w-8 h-8 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
                </svg>
                <svg v-else class="w-8 h-8 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <h2 class="text-2xl sm:text-3xl font-bold text-accent mb-3">
                {{ switchOverlayMode === 'executive'
                  ? (pLang === 'es' ? 'Vista Ejecutiva' : 'Executive View')
                  : switchOverlayMode === 'technical'
                    ? (pLang === 'es' ? 'Detalle técnico' : 'Technical detail')
                    : switchOverlayMode === 'legal'
                      ? (pLang === 'es' ? 'Contrato y condiciones' : 'Contract and terms')
                    : switchOverlayMode === 'gateway'
                      ? (pLang === 'es' ? 'Seleccionar vista' : 'Select view')
                      : (pLang === 'es' ? 'Propuesta Completa' : 'Full Proposal') }}
              </h2>
              <p class="text-sm text-accent/70 font-light max-w-xs mx-auto">
                {{ switchOverlayMode === 'executive'
                  ? (pLang === 'es' ? 'Lo esencial de tu proyecto en un vistazo' : 'The essentials of your project at a glance')
                  : switchOverlayMode === 'technical'
                    ? (pLang === 'es' ? 'Arquitectura, stack y requerimientos técnicos' : 'Architecture, stack, and technical requirements')
                    : switchOverlayMode === 'legal'
                      ? (pLang === 'es' ? 'Revisa el borrador y sus cláusulas con transparencia' : 'Review the draft and its clauses transparently')
                    : switchOverlayMode === 'gateway'
                      ? (pLang === 'es' ? 'Elige cómo quieres ver la propuesta' : 'Choose how to view the proposal')
                      : (pLang === 'es' ? 'Ahora verás todos los detalles de tu proyecto' : 'Now you\'ll see all the details of your project') }}
              </p>
            </div>
          </div>
        </Transition>
      </Teleport>

      <!-- Welcome-back toast (non-blocking) -->
      <Teleport to="body">
        <Transition name="fade-popup">
          <div v-if="welcomeBack" class="fixed bottom-6 right-6 z-[10000] max-w-xs w-full">
            <div class="bg-surface rounded-2xl shadow-2xl border border-border-muted p-5 relative">
              <BaseButton
                unstyled
                icon-only
                class="absolute top-3 right-3 w-6 h-6 rounded-full bg-surface-raised flex items-center justify-center text-text-subtle hover:text-text-muted hover:bg-border-muted transition-colors text-xs"
                :aria-label="pLang === 'es' ? 'Cerrar bienvenida' : 'Close welcome message'"
                @click="welcomeBack = null"
              >✕</BaseButton>
              <div class="flex items-center gap-3 mb-3">
                <div class="w-10 h-10 bg-primary-soft rounded-xl flex items-center justify-center flex-shrink-0">
                  <span class="text-xl">👋</span>
                </div>
                <h3 class="text-sm font-bold text-primary leading-tight">
                  {{ pLang === 'es' ? 'Bienvenido de nuevo' : 'Welcome back' }}{{ welcomeBack.clientName ? ', ' + welcomeBack.clientName : '' }}
                </h3>
              </div>
              <p class="text-xs text-primary/70 font-light leading-relaxed mb-4">
                <span v-if="welcomeBack.lastVisitTimestamp" class="block text-[10px] text-text-subtle mb-1">
                  {{ formatRelativeTime(welcomeBack.lastVisitTimestamp, pLang) }}
                </span>
                {{ pLang === 'es' ? 'La última vez llegaste hasta' : 'Last time you reached' }} <strong>{{ welcomeBack.sectionTitle }}</strong>.
              </p>
              <button
                class="w-full px-4 py-2.5 bg-primary text-accent rounded-xl font-bold text-xs
                       hover:bg-primary/90 transition-colors shadow-sm"
                @click="navigateTo(welcomeBack.sectionIndex); welcomeBack = null"
              >
                {{ pLang === 'es' ? 'Continuar donde lo dejé' : 'Continue where I left off' }}
              </button>
              <button
                class="w-full mt-2 px-4 py-2 text-xs text-text-subtle hover:text-text-muted transition-colors"
                @click="navigateTo(0); welcomeBack = null"
              >
                {{ pLang === 'es' ? 'Ver desde el inicio' : 'Start from the beginning' }}
              </button>
            </div>
          </div>
        </Transition>
      </Teleport>

      <!-- Reading time popup -->
      <Teleport to="body">
        <Transition name="fade-popup">
          <div v-if="readingPopupVisible" class="fixed inset-0 z-[10000] flex items-center justify-center p-6">
            <div class="absolute inset-0 bg-white/60 backdrop-blur-[3px]" />
            <div class="relative bg-surface rounded-3xl shadow-2xl border border-border-muted p-6 sm:p-8 max-w-sm w-full text-center">
              <div class="w-14 h-14 bg-primary rounded-2xl flex items-center justify-center mx-auto mb-5">
                <svg class="w-7 h-7 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h3 class="text-lg font-bold text-primary mb-2">{{ pLang === 'es' ? `Tiempo de lectura: ~${readMinutesEstimate} minutos` : `Reading time: ~${readMinutesEstimate} minutes` }}</h3>
              <p class="text-sm text-primary/70 font-light leading-relaxed mb-6">
                {{ pLang === 'es' ? 'Por favor lee el contenido de todas las secciones. Cada una aborda un punto importante y diferente de la propuesta.' : 'Please read through all sections. Each one covers an important and different aspect of the proposal.' }}
              </p>
              <button
                class="w-full px-6 py-3 bg-primary text-accent rounded-xl font-bold text-sm
                       hover:bg-primary/90 transition-colors shadow-sm"
                @click="readingPopupVisible = false"
              >
                {{ pLang === 'es' ? 'Entendido' : 'Got it' }}
              </button>
            </div>
          </div>
        </Transition>
      </Teleport>

      <!-- Side navigation arrows (fixed, outside transition) -->
      <SectionNavButtons
        :prevTitle="prevPanelTitle"
        :nextTitle="nextPanelTitle"
        :isFirst="currentIndex === 0"
        :isLast="currentIndex === totalSections - 1"
        :hideLeft="indexOpen"
        :blinkNext="navBlinkNext"
        :blinkPrev="navBlinkPrev"
        @prev="goPrev"
        @next="goNext"
      />

      <!-- Single-panel view with transition -->
      <Transition :name="transitionName" mode="out-in">
        <div v-if="currentPanel" :key="currentPanel.id" class="panel-container" :data-section-type="currentPanel.section_type">
          <RawContentSection
            v-if="isPastePanel(currentPanel)"
            :title="getPastePanelTitle(currentPanel)"
            :index="paddedDisplayIndex"
            :rawText="getPastePanelRawText(currentPanel)"
          />
          <component
            v-else
            :is="sectionComponentMap[currentPanel.section_type]"
            v-bind="getSectionProps(currentPanel, currentIndex)"
            v-on="getSectionListeners(currentPanel)"
          />
        </div>
      </Transition>
    </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onBeforeUnmount, onMounted, toRef, watch } from 'vue';
import { useProposalTracking } from '~/composables/useProposalTracking';
import PreloaderAnimation from '~/components/animations/PreloaderAnimation.vue';
import {
  Greeting,
  ExecutiveSummary,
  ContextDiagnostic,
  ConversionStrategy,
  DesignUX,
  CreativeSupport,
  DevelopmentStages,
  FunctionalRequirements,
  FunctionalRequirementsGroup,
  Timeline,
  Investment,
  FinalNote,
  NextSteps,
  ProposalSummary,
  ProcessMethodology,
  ValueAddedModules,
  RoiProjection,
} from '~/components/BusinessProposal';
import GatewayGuide from '~/components/BusinessProposal/GatewayGuide.vue';
import PersonalizedVideo from '~/components/BusinessProposal/PersonalizedVideo.vue';
import ProposalIndex from '~/components/BusinessProposal/ProposalIndex.vue';
import SectionCounter from '~/components/BusinessProposal/SectionCounter.vue';
import ExpirationBadge from '~/components/BusinessProposal/ExpirationBadge.vue';
import ProposalExpired from '~/components/BusinessProposal/ProposalExpired.vue';
import PdfDownloadButton from '~/components/BusinessProposal/PdfDownloadButton.vue';
import RawContentSection from '~/components/BusinessProposal/RawContentSection.vue';
import ProposalClosing from '~/components/BusinessProposal/ProposalClosing.vue';
import SectionNavButtons from '~/components/BusinessProposal/SectionNavButtons.vue';
import ProposalOnboarding from '~/components/BusinessProposal/ProposalOnboarding.vue';
import InvestmentOnboarding from '~/components/BusinessProposal/InvestmentOnboarding.vue';
import ExecutiveInvestmentOnboarding from '~/components/BusinessProposal/ExecutiveInvestmentOnboarding.vue';
import RequirementsOnboarding from '~/components/BusinessProposal/RequirementsOnboarding.vue';
import ShareProposalButton from '~/components/BusinessProposal/ShareProposalButton.vue';
import WhatsAppFloatingButton from '~/components/BusinessProposal/WhatsAppFloatingButton.vue';
import ProposalViewGateway from '~/components/BusinessProposal/ProposalViewGateway.vue';
import TechnicalDocumentPublicPanel from '~/components/BusinessProposal/TechnicalDocumentPublicPanel.vue';
import ContractTermsOverview from '~/components/BusinessProposal/ContractTermsOverview.vue';
import ContractTermsDocument from '~/components/BusinessProposal/ContractTermsDocument.vue';
import { buildSyntheticTechnicalPanels } from '~/utils/technicalProposalPanels';
import {
  buildProposalModuleLinkCatalog,
  normalizeTechnicalDocumentModuleLinks,
} from '~/utils/proposalModuleLinkOptions';
import { filterTechnicalDocumentByModules } from '~/utils/filterTechnicalDocumentByModules';
import { buildItemRequirementsMap } from '~/utils/itemRequirementLinks';
import { useProposalDarkMode } from '~/composables/useProposalDarkMode';
import { normalizePersistedSelectedIds } from '~/utils/proposalModuleSelectionStorage';
import { RESOLVED_PROPOSAL_STATUSES, DEFAULT_HOSTING_PERCENT } from '~/stores/proposals_constants';

definePageMeta({ layout: false });

const route = useRoute();
const router = useRouter();
const proposalStore = useProposalStore();

const isPreviewMode = computed(() => route.query.preview === '1' || route.query.preview === 'true');
function exitPreview() {
  router.back();
}

const { isDark: proposalDarkMode, toggle: toggleProposalDarkMode, applyTheme: applyProposalTheme } = useProposalDarkMode();

const pLang = computed(() => proposal.value?.language || 'es');
const browserLang = computed(() => {
  if (import.meta.server) return 'en';
  return (navigator.language || '').startsWith('es') ? 'es' : 'en';
});

const sectionComponentMap = {
  personalized_video: PersonalizedVideo,
  greeting: Greeting,
  executive_summary: ExecutiveSummary,
  context_diagnostic: ContextDiagnostic,
  conversion_strategy: ConversionStrategy,
  design_ux: DesignUX,
  creative_support: CreativeSupport,
  development_stages: DevelopmentStages,
  process_methodology: ProcessMethodology,
  functional_requirements: FunctionalRequirements,
  functional_requirements_group: FunctionalRequirementsGroup,
  value_added_modules: ValueAddedModules,
  timeline: Timeline,
  investment: Investment,
  final_note: FinalNote,
  next_steps: NextSteps,
  proposal_summary: ProposalSummary,
  roi_projection: RoiProjection,
  proposal_closing: ProposalClosing,
  technical_document_public: TechnicalDocumentPublicPanel,
  contract_terms_overview: ContractTermsOverview,
  contract_terms_document: ContractTermsDocument,
};

const proposal = computed(() => proposalStore.currentProposal);
const enabledSections = computed(() => proposalStore.enabledSections);

// Once the client's decision is settled (accepted/rejected/finished), urgency
// notices (expiration countdown, limited-time discount) no longer make sense.
const isProposalResolved = computed(() =>
  RESOLVED_PROPOSAL_STATUSES.includes(proposal.value?.status));

// Expired proposal banner data (from expired_meta returned by backend)
const expiredAtFormatted = computed(() => {
  const raw = proposal.value?.expired_meta?.expired_at;
  if (!raw) return '';
  try {
    const lang = pLang.value === 'es' ? 'es-CO' : 'en-US';
    return new Date(raw).toLocaleDateString(lang, { day: 'numeric', month: 'long', year: 'numeric' });
  } catch { return ''; }
});
const expiredSellerName = computed(() => {
  return proposal.value?.expired_meta?.seller_name || (pLang.value === 'es' ? 'nuestro equipo' : 'our team');
});
const expiredWhatsappUrl = computed(() => {
  return proposal.value?.expired_meta?.whatsapp_url || '';
});

// 4.5 — Personalized OG meta tags for WhatsApp sharing
useHead({
  title: computed(() => proposal.value ? `Propuesta para ${proposal.value.client_name}` : 'Propuesta'),
  meta: computed(() => {
    if (!proposal.value) return [];
    const p = proposal.value;
    const lang = p.language || 'es';
    const title = lang === 'en'
      ? `Proposal for ${p.client_name}`
      : `Propuesta para ${p.client_name}`;
    const desc = lang === 'en'
      ? `${p.client_name}, here is your custom proposal: ${p.title}`
      : `${p.client_name}, aquí está tu propuesta personalizada: ${p.title}`;
    return [
      { property: 'og:title', content: title },
      { property: 'og:description', content: desc },
      { property: 'og:type', content: 'website' },
      { name: 'description', content: desc },
    ];
  }),
});

const viewMode = ref(null); // null = gateway, 'executive', 'detailed', 'technical', 'legal'
const EXECUTIVE_SECTION_TYPES = new Set([
  'greeting', 'executive_summary', 'proposal_summary', 'value_added_modules', 'functional_requirements', 'investment', 'timeline', 'proposal_closing',
]);

const hasTechnicalDocument = computed(() =>
  enabledSections.value.some((s) => s.section_type === 'technical_document'),
);
const hasContractTerms = computed(() => (
  proposal.value?.language === 'es'
  && proposal.value?.show_contract_terms !== false
));
const isDocumentView = computed(() => (
  viewMode.value === 'technical' || viewMode.value === 'legal'
));

const technicalModuleLinkCatalog = computed(() =>
  buildProposalModuleLinkCatalog(enabledSections.value),
);

const hasConfirmedModuleSelection = ref(false);

function effectiveSelectedModuleIdsForTechnical() {
  if (!hasConfirmedModuleSelection.value) return null;
  const fromUi = [...selectedScopeModuleIds.value];
  if (fromUi.length) return fromUi;
  const persisted = proposal.value?.selected_modules;
  if (Array.isArray(persisted)) return [...persisted];
  return [];
}

// Technical document as the client should see it, in two layers so the
// (deep-copying) normalization only re-runs when the section content
// changes, while the filter reflects persisted contracted scope.
const normalizedTechnicalDocument = computed(() => {
  const tech = enabledSections.value.find((s) => s.section_type === 'technical_document');
  if (!tech || !tech.content_json || typeof tech.content_json !== 'object') return null;
  return normalizeTechnicalDocumentModuleLinks(
    tech.content_json,
    technicalModuleLinkCatalog.value.aliasMap,
  );
});

const filteredTechnicalDocument = computed(() => {
  if (!normalizedTechnicalDocument.value) return null;
  return filterTechnicalDocumentByModules(
    normalizedTechnicalDocument.value,
    effectiveSelectedModuleIdsForTechnical(),
    technicalModuleLinkCatalog.value.alwaysIncludedIds,
  );
});

// Item → technical requirements map for the commercial nested modal.
// Filtered by contracted scope so excluded modules do not add requirements.
const itemRequirementsMap = computed(() => (
  filteredTechnicalDocument.value
    ? buildItemRequirementsMap(filteredTechnicalDocument.value)
    : {}
));

const readMinutesEstimate = computed(() => {
  if (viewMode.value === 'executive') return 2;
  if (viewMode.value === 'technical') return 12;
  if (viewMode.value === 'legal') return 10;
  return 8;
});
const activeContractClauseId = ref('');

const nextStepsContent = computed(() => (
  enabledSections.value.find((section) => section.section_type === 'next_steps')?.content_json || {}
));

// Build display panels: skip next_steps (merged into final_note), no FR sub-panels
// When viewMode is 'executive', filter to only executive section types
// When 'technical', synthetic panels from technical_document + closing
const displayPanels = computed(() => {
  const lang = pLang.value === 'en' ? 'en' : 'es';

  if (viewMode.value === 'technical') {
    const tech = enabledSections.value.find((s) => s.section_type === 'technical_document');
    if (!tech) return [];
    const docForPanels = filteredTechnicalDocument.value || {};
    const panels = buildSyntheticTechnicalPanels({ ...tech, content_json: docForPanels }, lang);
    if (enabledSections.value.length > 0) {
      const finalNote = enabledSections.value.find((s) => s.section_type === 'final_note');
      const fnContent = finalNote?.content_json || {};
      const nsContent = nextStepsContent.value;
      panels.push({
        id: 'proposal_closing',
        section_type: 'proposal_closing',
        title: lang === 'en' ? '🤝 Next Steps' : '🤝 Próximos pasos',
        _validityMessage: fnContent.validityMessage || '',
        _thankYouMessage: fnContent.thankYouMessage || '',
        _expiresAt: proposal.value?.expires_at || '',
        _ctaMessage: nsContent.ctaMessage || '',
        _primaryCTA: nsContent.primaryCTA || {},
        _secondaryCTA: nsContent.secondaryCTA || {},
        _contactMethods: nsContent.contactMethods || [],
      });
    }
    return panels;
  }

  if (viewMode.value === 'legal') {
    return [
      {
        id: 'contract_terms_overview',
        section_type: 'contract_terms_overview',
        title: '⚖️ Contrato y condiciones',
      },
      {
        id: 'contract_terms_document',
        section_type: 'contract_terms_document',
        title: '📄 Borrador del contrato',
        _contractClause: activeContractClauseId.value,
      },
    ];
  }

  const panels = [];
  const isExecutive = viewMode.value === 'executive';

  const frSection = enabledSections.value.find((s) => s.section_type === 'functional_requirements');
  const frGroupIds = new Set(
    (frSection?.content_json?.groups || [])
      .map((g) => g && g.id)
      .filter(Boolean),
  );

  for (const section of enabledSections.value) {
    // Skip next_steps — its content is merged into final_note
    if (section.section_type === 'next_steps') continue;
    if (section.section_type === 'technical_document') continue;
    // commercial_conditions is a PDF-only section (no web component)
    if (section.section_type === 'commercial_conditions') continue;
    // In executive mode, skip sections not in the executive set
    if (isExecutive && !EXECUTIVE_SECTION_TYPES.has(section.section_type)) continue;
    // Hide value_added_modules when no ids resolve against FR groups
    if (section.section_type === 'value_added_modules') {
      const ids = section.content_json?.module_ids || [];
      const resolvable = ids.some((id) => frGroupIds.has(id));
      if (!resolvable) continue;
    }
    panels.push(section);
  }

  if (proposal.value?.personalized_video) {
    const greetingIndex = panels.findIndex(panel => panel.section_type === 'greeting');
    panels.splice(greetingIndex < 0 ? 0 : greetingIndex + 1, 0, {
      id: 'personalized_video', section_type: 'personalized_video',
      title: lang === 'en' ? 'Your proposal on video' : 'Tu propuesta en video',
    });
  }

  // Add closing panel (validity, thank-you, accept/reject) after all sections
  // Only add when sections are loaded to prevent marking it as visited on first render
  if (enabledSections.value.length > 0) {
    const finalNote = enabledSections.value.find(s => s.section_type === 'final_note');
    const fnContent = finalNote?.content_json || {};
    const nsContent = nextStepsContent.value;
    panels.push({
      id: 'proposal_closing',
      section_type: 'proposal_closing',
      title: lang === 'es' ? '🤝 Próximos pasos' : '🤝 Next Steps',
      _validityMessage: fnContent.validityMessage || '',
      _thankYouMessage: fnContent.thankYouMessage || '',
      _expiresAt: proposal.value?.expires_at || '',
      _ctaMessage: nsContent.ctaMessage || '',
      _primaryCTA: nsContent.primaryCTA || {},
      _secondaryCTA: nsContent.secondaryCTA || {},
      _contactMethods: nsContent.contactMethods || [],
    });
  }

  return panels;
});

const totalSections = computed(() => displayPanels.value.length);

const showContent = ref(false);
const loadError = ref(null);
const proposalContainer = ref(null);
const currentIndex = ref(0);
const visitedPanelIds = ref(new Set());
const transitionName = ref('slide-left');
const indexOpen = ref(false);
const navBlinkNext = ref(false);
const navBlinkPrev = ref(false);
let blinkTimer = null;
const onboardingRef = ref(null);
const investmentOnboardingRef = ref(null);
const executiveInvestmentOnboardingRef = ref(null);
const requirementsOnboardingRef = ref(null);
const readingPopupVisible = ref(false);
const switchOverlayVisible = ref(false);
const switchOverlayMode = ref('detailed');
const welcomeBack = ref(null);
const contractTerms = ref(null);
const contractTermsLoading = ref(false);
const contractTermsError = ref('');
const pendingContractClauseId = ref('');

// Current panel and neighbors
const currentPanel = computed(() => displayPanels.value[currentIndex.value] || displayPanels.value[0]);
const paddedDisplayIndex = computed(() => String(currentIndex.value + 1).padStart(2, '0'));

// Track visited panels whenever currentIndex changes
watch(currentPanel, (panel) => {
  if (panel?.id !== undefined) {
    visitedPanelIds.value = new Set([...visitedPanelIds.value, panel.id]);
  }
  // Persist progress for welcome-back
  if (panel && proposal.value?.uuid && !isPreviewMode.value) {
    try {
      const key = `proposal-${proposal.value.uuid}-progress`;
      localStorage.setItem(key, JSON.stringify({
        sectionIndex: currentIndex.value,
        sectionTitle: panel.title || '',
        clientName: proposal.value.client_name || '',
        lastVisitTimestamp: Date.now(),
      }));
    } catch (_e) { /* ignore */ }
  }
}, { immediate: true });

// Investment onboarding: detect if investment section has modules (customize button)
const investmentHasModules = computed(() => Boolean(proposal.value?.uuid));

// Trigger investment onboarding when user navigates to investment section
let investmentOnboardingTriggered = false;
let executiveInvestmentOnboardingTriggered = false;
let requirementsOnboardingTriggered = false;
watch(currentPanel, (panel) => {
  if (
    panel?.section_type === 'investment' &&
    !investmentOnboardingTriggered &&
    investmentHasModules.value &&
    viewMode.value === 'detailed'
  ) {
    investmentOnboardingTriggered = true;
    setTimeout(() => {
      investmentOnboardingRef.value?.start();
    }, 800);
  }
  // Trigger executive investment onboarding (teaser button) in executive mode
  if (
    panel?.section_type === 'investment' &&
    !executiveInvestmentOnboardingTriggered &&
    viewMode.value === 'executive'
  ) {
    executiveInvestmentOnboardingTriggered = true;
    setTimeout(() => {
      executiveInvestmentOnboardingRef.value?.start();
    }, 800);
  }
  // Trigger requirements onboarding when user reaches functional_requirements section
  if (
    panel?.section_type === 'functional_requirements' &&
    !requirementsOnboardingTriggered &&
    !isDocumentView.value
  ) {
    requirementsOnboardingTriggered = true;
    setTimeout(() => {
      requirementsOnboardingRef.value?.start();
    }, 800);
  }
});

// Section engagement tracking
const proposalUuidRef = computed(() => proposal.value?.uuid || route.params.uuid);
const { flush: flushTracking } = useProposalTracking(proposalUuidRef, currentPanel, viewMode);

function showReadingTimePopup() {
  readingPopupVisible.value = true;
}

function formatRelativeTime(timestamp, lang) {
  const diff = Date.now() - timestamp;
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);
  if (lang === 'es') {
    if (minutes < 60) return `Hace ${minutes} ${minutes === 1 ? 'minuto' : 'minutos'}`;
    if (hours < 24) return `Hace ${hours} ${hours === 1 ? 'hora' : 'horas'}`;
    return `Hace ${days} ${days === 1 ? 'día' : 'días'}`;
  }
  if (minutes < 60) return `${minutes} ${minutes === 1 ? 'minute' : 'minutes'} ago`;
  if (hours < 24) return `${hours} ${hours === 1 ? 'hour' : 'hours'} ago`;
  return `${days} ${days === 1 ? 'day' : 'days'} ago`;
}
// Extract WhatsApp link from next_steps section primaryCTA if it contains wa.me
const extractedWhatsappLink = computed(() => {
  const nextSteps = enabledSections.value.find(s => s.section_type === 'next_steps');
  const cta = nextSteps?.content_json?.primaryCTA;
  if (cta?.link && cta.link.includes('wa.me')) return cta.link;
  return '';
});

// Contracted scope is owned by the seller; legacy selections remain readable.
const optionalScopeModules = computed(() => {
  const content = enabledSections.value.find(s => s.section_type === 'functional_requirements')?.content_json || {};
  return [...(content.groups || []), ...(content.additionalModules || [])]
    .filter(group => group.is_visible !== false && group.is_calculator_module === true)
    .map(group => ({
      id: `module-${group.id}`, groupId: group.id,
      default_selected: group.selected ?? group.default_selected ?? false,
      pinned: group.selected === true,
    }));
});

const selectedScopeModuleIds = ref(new Set());
const resolvedInvestmentTotal = computed(() => Number(proposal.value?.total_investment || 0));

const confirmedModuleCount = computed(() =>
  hasConfirmedModuleSelection.value ? selectedScopeModuleIds.value.size : null,
);

// Mirror of Investment.vue computedPaymentOptions: derive each amount from
// the label percentage × the current displayed total.
function recomputePaymentOptions(paymentOptions, agreedTotal) {
  if (agreedTotal == null || !paymentOptions?.length) return paymentOptions;
  const target = Number(agreedTotal) || 0;
  if (target <= 0) return paymentOptions;
  return paymentOptions.map(opt => {
    const pctMatch = String(opt.label || '').match(/(\d+)\s*%/);
    if (!pctMatch) return opt;
    const pct = Number(pctMatch[1]) / 100;
    const newAmount = Math.round(target * pct);
    const formatted = newAmount.toLocaleString('es-CO', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
    const desc = opt.description || '';
    const newDesc = desc
      ? desc.replace(/[\$]?[\d.,]+/, formatted)
      : `$${formatted}`;
    return { ...opt, description: newDesc.startsWith('$') ? newDesc : '$' + newDesc };
  });
}

const prevPanelTitle = computed(() => {
  const prev = displayPanels.value[currentIndex.value - 1];
  return prev?.title || '';
});
const nextPanelTitle = computed(() => {
  const next = displayPanels.value[currentIndex.value + 1];
  return next?.title || '';
});

// Preserve previously contracted selections; new client interests live separately.
function computeInitialSelection() {
  if (!proposal.value) return;

  const calcItems = optionalScopeModules.value;
  const investmentSection = enabledSections.value.find(s => s.section_type === 'investment');
  const investmentModules = investmentSection?.content_json?.modules || [];

  const hasConfirmed = proposal.value.has_confirmed_module_selection === true;
  const persistedRaw = Array.isArray(proposal.value.selected_modules)
    ? proposal.value.selected_modules
    : [];
  const persisted = normalizePersistedSelectedIds(persistedRaw, calcItems);
  // Optional modules the admin included explicitly ("selected" in the panel)
  // are always part of the initial selection, even over a prior confirmation.
  const adminPinnedIds = calcItems.filter(m => m.pinned === true).map(m => m.id);

  let selectedIds;
  if (hasConfirmed) {
    // Client confirmed a selection — honor it, but union in the admin's
    // explicit pins so panel changes always reach the client.
    selectedIds = new Set([...persisted, ...adminPinnedIds]);
  } else {
    const derived = [];
    for (const m of investmentModules) {
      if (m.is_required === true || m.default_selected !== false) derived.push(m.id);
    }
    for (const m of calcItems) {
      if (m.default_selected === true) derived.push(m.id);
    }
    selectedIds = new Set(derived);
  }

  selectedScopeModuleIds.value = new Set(selectedIds);
  hasConfirmedModuleSelection.value = hasConfirmed;


}

// --- Fetch proposal on mount ---
const isExpired = ref(false);

onMounted(async () => {
  const uuid = route.params.uuid;
  const result = await proposalStore.fetchPublicProposal(uuid);
  if (!result.success) {
    loadError.value = result.error;
  } else if (result.expired) {
    isExpired.value = true;
  } else {
    computeInitialSelection();
  }
});

// --- Section props transformer ---
function getSectionProps(section, displayIndex) {
  if (section.section_type === 'personalized_video') {
    return { video: proposal.value.personalized_video, language: pLang.value };
  }
  const content = section.content_json || {};
  const idx = typeof displayIndex === 'number' ? displayIndex : (displayIndex?.value ?? 0);
  const paddedIndex = String(idx + 1).padStart(2, '0');

  if (section.section_type === 'contract_terms_overview') {
    return {
      terms: contractTerms.value,
      loading: contractTermsLoading.value,
      error: contractTermsError.value,
      language: proposal.value?.language || 'es',
    };
  }

  if (section.section_type === 'contract_terms_document') {
    return {
      terms: contractTerms.value,
      loading: contractTermsLoading.value,
      error: contractTermsError.value,
      language: proposal.value?.language || 'es',
    };
  }

  if (section.section_type === 'proposal_closing') {
    const investmentSection = enabledSections.value.find(s => s.section_type === 'investment');
    const investContent = investmentSection?.content_json || {};
    const rawPaymentOptions = investContent.paymentOptions || [];
    const displayTotal = resolvedInvestmentTotal.value;
    return {
      proposal: proposal.value,
      validityMessage: section._validityMessage || '',
      thankYouMessage: section._thankYouMessage || '',
      expiresAt: section._expiresAt || '',
      language: proposal.value?.language || 'es',
      whatsappLink: extractedWhatsappLink.value,
      paymentOptions: recomputePaymentOptions(rawPaymentOptions, displayTotal),
      investmentTotal: displayTotal,
      viewMode: viewMode.value || 'detailed',
      ctaMessage: section._ctaMessage || '',
      primaryCTA: section._primaryCTA || {},
      secondaryCTA: section._secondaryCTA || {},
      contactMethods: section._contactMethods || [],
    };
  }

  if (section.section_type === 'technical_document_public') {
    return {
      fragment: section._technicalFragment || 'intro',
      contentJson: section.content_json || {},
      language: proposal.value?.language || 'es',
      index: paddedIndex,
    };
  }

  if (section.section_type === 'greeting') {
    return {
      proposalTitle: content.proposalTitle || proposal.value?.title || '',
      clientName: content.clientName || proposal.value?.client_name || '',
      inspirationalQuote: content.inspirationalQuote,
    };
  }

  if (section.section_type === 'value_added_modules') {
    return {
      section: { ...section, content_json: { ...content, index: paddedIndex } },
      proposal: proposal.value || { sections: enabledSections.value },
      proposalUuid: proposal.value?.uuid || '',
      itemRequirementsMap: itemRequirementsMap.value,
      effectiveTotal: resolvedInvestmentTotal.value,
    };
  }

  if ([
    'executive_summary', 'context_diagnostic', 'conversion_strategy',
    'design_ux', 'creative_support',
  ].includes(section.section_type)) {
    return { content: { ...content, index: paddedIndex } };
  }

  if (section.section_type === 'functional_requirements') {
    // content_json is the only source: the legacy requirement_groups tables
    // were dropped after shipping zero rows in production.
    const groups = content.groups || [];
    // Persisted scope selections remain independent of commercial interests.
    const allSelectedIds = [...selectedScopeModuleIds.value];
    // Hide groups already showcased in the value_added_modules section (when enabled)
    // to avoid visual duplication. Their canonical data stays in FR.groups[] as catalog.
    const vamSection = enabledSections.value.find(
      (s) => s.section_type === 'value_added_modules' && s.is_enabled !== false,
    );
    const valueAddedModuleIds = Array.isArray(vamSection?.content_json?.module_ids)
      ? vamSection.content_json.module_ids
      : [];
    return {
      data: {
        ...content,
        groups,
        additionalModules: content.additionalModules || [],
        index: paddedIndex,
      },
      language: proposal.value?.language || 'es',
      selectedCalculatorModules: allSelectedIds,
      currency: proposal.value?.currency || 'COP',
      proposalUuid: proposal.value?.uuid || '',
      valueAddedModuleIds,
      itemRequirementsMap: itemRequirementsMap.value,
    };
  }

  // For investment: inject discount data from proposal
  if (section.section_type === 'investment') {
    // Always use proposal.total_investment as the source of truth for display
    const proposalTotal = Number(proposal.value?.total_investment || 0);
    const proposalCurrency = proposal.value?.currency || content.currency || 'COP';
    const formattedTotal = proposalTotal > 0
      ? '$' + proposalTotal.toLocaleString('es-CO', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
      : content.totalInvestment || '';
    // The public serializer resolves the canonical hosting terms, including
    // preserving the stored snapshot for closed historical proposals.
    const hostingPlan = content.hostingPlan || {
      hostingPercent: DEFAULT_HOSTING_PERCENT,
    };
    return {
      ...content,
      index: paddedIndex,
      hostingPlan,
      totalInvestment: formattedTotal,
      currency: proposalCurrency,
      language: proposal.value?.language || 'es',
      discountPercent: proposal.value?.discount_percent || 0,
      discountedInvestment: proposal.value?.discounted_investment || '',
      discountOriginalInvestment: proposal.value?.discount_original_investment || '',
      expiresAt: proposal.value?.expires_at || '',
      proposalStatus: proposal.value?.status || '',
      preview: isPreviewMode.value,
      proposalUuid: proposal.value?.uuid || '',
      whatsappLink: extractedWhatsappLink.value,
      viewMode: viewMode.value || 'detailed',
      effectiveTotal: resolvedInvestmentTotal.value,
    };
  }

  // For roi_projection: pass content_json as a single ``content`` prop
  // (component expects ``content``, not flat-spread fields).
  if (section.section_type === 'roi_projection') {
    return {
      content: { ...content, index: paddedIndex },
    };
  }

  // For proposal_summary: inject the agreed investment and contracted scope.
  if (section.section_type === 'proposal_summary') {
    const timelineSection = enabledSections.value.find(s => s.section_type === 'timeline');
    const timelineDuration = timelineSection?.content_json?.totalDuration || '';
    const investmentSection = enabledSections.value.find(s => s.section_type === 'investment');
    const investContent = investmentSection?.content_json || {};
    const investmentModules = (investContent.modules || []).map(m => ({ ...m, _source: 'investment' }));
    const contractedModules = [...investmentModules, ...optionalScopeModules.value];
    const effectiveTotal = resolvedInvestmentTotal.value;
    const rawPaymentOptions = investContent.paymentOptions || [];
    return {
      content: { ...content, index: paddedIndex },
      proposal: proposal.value,
      timelineDuration,
      language: proposal.value?.language || 'es',
      investmentModules: contractedModules,
      paymentOptions: recomputePaymentOptions(rawPaymentOptions, effectiveTotal),
      investmentTotal: effectiveTotal,
      selectedModuleCount: confirmedModuleCount.value,
    };
  }

  // For final_note: merge next_steps data as additional props
  if (section.section_type === 'final_note') {
    const nextStepsSection = enabledSections.value.find(s => s.section_type === 'next_steps');
    const nsContent = nextStepsSection?.content_json || {};
    const lang = proposal.value?.language || 'es';
    const defaultKickoff = lang === 'en'
      ? [
          { day: 'D1', title: 'Contract signing', description: 'We formalize the agreement and send you access credentials.' },
          { day: 'D2', title: 'Onboarding call', description: 'Your Project Manager contacts you to align expectations and priorities.' },
          { day: 'D3', title: 'Access & setup', description: 'We configure the technical environment and shared tools.' },
          { day: 'D4', title: 'Technical kickoff', description: 'The development team reviews the architecture and starts the first tasks.' },
          { day: 'D5', title: 'Sprint planning', description: 'We define the first sprint goals and deliverables together.' },
        ]
      : [
          { day: 'D1', title: 'Firma de contrato', description: 'Formalizamos el acuerdo y te enviamos credenciales de acceso.' },
          { day: 'D2', title: 'Llamada de onboarding', description: 'Tu Project Manager te contacta para alinear expectativas y prioridades.' },
          { day: 'D3', title: 'Accesos y setup', description: 'Configuramos el entorno técnico y herramientas compartidas.' },
          { day: 'D4', title: 'Kickoff técnico', description: 'El equipo de desarrollo revisa la arquitectura e inicia las primeras tareas.' },
          { day: 'D5', title: 'Sprint planning', description: 'Definimos juntos los objetivos y entregables del primer sprint.' },
        ];
    return {
      ...content,
      index: paddedIndex,
      language: lang,
      kickoffPlan: content.kickoffPlan || defaultKickoff,
      nextSteps: nsContent.steps || [],
      nextStepsIntro: nsContent.introMessage || '',
    };
  }

  // For development_stages, timeline, process_methodology, etc.
  // Spread content_json as individual props
  return { ...content, index: paddedIndex };
}

function getSectionListeners(section) {
  const type = section.section_type;
  const listeners = {};
  if (type === 'investment') {
    listeners.navigateToRequirements = handleNavigateToRequirements;
    listeners.switchToDetailed = handleSwitchToDetailed;
  }
  if (type === 'technical_document_public') {
    listeners.navigate = handleNavigateToFragment;
  }
  if (type === 'contract_terms_overview') {
    listeners.navigate = handleNavigateToContractClause;
    listeners.retry = retryContractTerms;
  }
  if (type === 'contract_terms_document') {
    listeners.ready = handleContractDocumentReady;
    listeners.retry = retryContractTerms;
  }
  return listeners;
}

function isPastePanel(panel) {
  return panel.content_json?._editMode === 'paste' && panel.content_json?.rawText;
}

function getPastePanelTitle(panel) {
  return panel.content_json?.title || panel.title;
}

function getPastePanelIndex(panel) {
  return panel.content_json?.index || '';
}

function getPastePanelRawText(panel) {
  return panel.content_json?.rawText || '';
}

// --- Navigation ---
function triggerNavBlink() {
  if (blinkTimer) clearTimeout(blinkTimer);
  navBlinkNext.value = false;
  navBlinkPrev.value = false;
  // Use nextTick to re-trigger animation even if same prop value
  setTimeout(() => {
    const isLast = currentIndex.value === totalSections.value - 1;
    if (isLast) {
      navBlinkPrev.value = true;
    } else {
      navBlinkNext.value = true;
    }
    blinkTimer = setTimeout(() => {
      navBlinkNext.value = false;
      navBlinkPrev.value = false;
    }, 4000);
  }, 100);
}

function navigateTo(index) {
  if (index < 0 || index >= totalSections.value) return;
  transitionName.value = index > currentIndex.value ? 'slide-left' : 'slide-right';
  currentIndex.value = index;
  window.scrollTo({ top: 0, behavior: 'auto' });
  triggerNavBlink();
}

function handleNavigate(index) {
  navigateTo(index);
}

function handleNavigateToRequirements() {
  const idx = displayPanels.value.findIndex(p => p.section_type === 'functional_requirements');
  if (idx !== -1) navigateTo(idx);
}

// Jumps from the technical cover index. Resolved by fragment key rather than by
// position, so the jump stays correct when filterTechnicalDocumentByModules
// omits fragments outside the persisted contracted scope.
function handleNavigateToFragment(fragment) {
  const idx = displayPanels.value.findIndex(p => p._technicalFragment === fragment);
  if (idx !== -1) navigateTo(idx);
}

async function loadContractTerms({ force = false } = {}) {
  if (!hasContractTerms.value || contractTermsLoading.value) return;
  if (contractTerms.value && !force) return;
  const proposalUuid = proposal.value?.uuid || '';
  if (!proposalUuid) return;

  contractTermsLoading.value = true;
  contractTermsError.value = '';
  const result = await proposalStore.fetchContractTerms(proposalUuid);
  if (result.success) {
    contractTerms.value = result.data;
  } else {
    contractTermsError.value = result.error || 'contract_terms_unavailable';
  }
  contractTermsLoading.value = false;
}

function retryContractTerms() {
  contractTerms.value = null;
  loadContractTerms({ force: true });
}

function handleNavigateToContractClause(clauseId) {
  const idx = displayPanels.value.findIndex(
    panel => panel.section_type === 'contract_terms_document',
  );
  if (idx === -1) return;
  pendingContractClauseId.value = clauseId;
  activeContractClauseId.value = clauseId;
  navigateTo(idx);
}

async function handleContractDocumentReady() {
  if (!pendingContractClauseId.value) return;
  await nextTick();
  const clause = document.getElementById(pendingContractClauseId.value);
  clause?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  pendingContractClauseId.value = '';
}


const OVERLAY_TRANSITION_MS = 1000;

function switchMode(overlayMode, newViewMode, { scrollToTop = false, beforeSwitch = null, startOnboarding = false } = {}) {
  switchOverlayMode.value = overlayMode;
  switchOverlayVisible.value = true;
  setTimeout(() => {
    if (beforeSwitch) beforeSwitch();
    viewMode.value = newViewMode;
    currentIndex.value = 0;
    if (scrollToTop) window.scrollTo({ top: 0, behavior: 'auto' });
    switchOverlayVisible.value = false;
    if (startOnboarding && !welcomeBack.value) nextTick(() => onboardingRef.value?.start());
  }, OVERLAY_TRANSITION_MS);
}

function handleViewModeSelect(mode) {
  if (mode === 'legal') loadContractTerms();
  const startsOnboarding = mode !== 'technical' && mode !== 'legal';
  switchMode(mode, mode, { startOnboarding: startsOnboarding });
}

function handleSwitchToDetailed() {
  switchMode('detailed', 'detailed', { scrollToTop: true });
}

function handleBackToGateway() {
  switchMode('gateway', null, { scrollToTop: true, beforeSwitch: flushTracking });
}

function goNext() {
  navigateTo(currentIndex.value + 1);
}

function goPrev() {
  navigateTo(currentIndex.value - 1);
}

// --- Keyboard navigation ---
function handleKeydown(e) {
  if (document.querySelector('[aria-modal="true"]')) return;
  const tag = document.activeElement?.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
  if (e.key === 'ArrowRight') { e.preventDefault(); goNext(); }
  if (e.key === 'ArrowLeft') { e.preventDefault(); goPrev(); }
}

// --- Swipe gesture detection ---
let touchStartX = 0;
let touchStartY = 0;

function onTouchStart(e) {
  const touch = e.touches?.[0];
  if (!touch) return;
  touchStartX = touch.clientX;
  touchStartY = touch.clientY;
}

function onTouchEnd(e) {
  const touch = e.changedTouches?.[0];
  if (!touch) return;
  const deltaX = touch.clientX - touchStartX;
  const deltaY = touch.clientY - touchStartY;

  // Only trigger if horizontal swipe is dominant and long enough
  if (Math.abs(deltaX) > 50 && Math.abs(deltaX) > Math.abs(deltaY) * 1.5) {
    if (deltaX < 0) goNext();   // swipe left → next
    else goPrev();              // swipe right → previous
  }
}

// --- Lifecycle ---
const onAnimationComplete = () => {
  if (loadError.value) return;
  showContent.value = true;
  nextTick(() => applyProposalTheme(false));
  window.addEventListener('keydown', handleKeydown);

  // Allow bypassing gateway via URL query param (used by E2E tests and direct links)
  const queryMode = typeof route.query.mode === 'string' ? route.query.mode : '';
  if (['executive', 'detailed', 'technical', 'legal'].includes(queryMode)) {
    const canOpenTechnical = queryMode !== 'technical' || hasTechnicalDocument.value;
    const canOpenLegal = queryMode !== 'legal' || hasContractTerms.value;
    if (canOpenTechnical && canOpenLegal) {
      viewMode.value = queryMode;
      if (queryMode === 'legal') loadContractTerms();
    }
  }

  // Check for returning client (welcome-back) — viewMode is null here so gateway always shows first
  // The welcome-back data is stored so we can show it after the user picks a view mode
  if (!isPreviewMode.value && proposal.value?.uuid) {
    try {
      const key = `proposal-${proposal.value.uuid}-progress`;
      const saved = localStorage.getItem(key);
      if (saved) {
        const data = JSON.parse(saved);
        if (data.sectionIndex > 0 && data.sectionIndex < totalSections.value) {
          welcomeBack.value = data;
          return; // Skip onboarding — show welcome-back instead
        }
      }
    } catch (_e) { /* ignore */ }
  }

  // If viewMode is set (returning visitor), start onboarding; otherwise gateway is shown
  if (viewMode.value && !isDocumentView.value) {
    nextTick(() => {
      onboardingRef.value?.start();
    });
  }
};

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeydown);
});
</script>

<style scoped>
.business-proposal {
  overflow-x: hidden;
}

.proposal-wrapper {
  opacity: 0;
  animation: fadeIn 0.8s ease-in forwards;
}

.panel-container {
  width: 100%;
  min-height: 100vh;
}

.panel-container :deep(section:not(.greeting-section)) {
  scroll-margin-top: 40px;
}

.panel-container :deep(.min-h-screen:not(.greeting-section)) {
  padding-top: 48px;
}

.panel-container :deep(.greeting-section) {
  padding-top: 0;
}

/* On mobile: scrollable sections get bottom padding so PDF/WhatsApp buttons
   don't cover content. Greeting stays untouched. */
@media (max-width: 639px) {
  .panel-container :deep(.min-h-screen:not(.greeting-section)) {
    padding-top: 48px;
  }
  .panel-container :deep(section:not(.greeting-section):not(.min-h-screen)) {
    padding-top: 80px;
    padding-bottom: 100px;
  }
  .panel-container :deep(.greeting-section) {
    padding-top: 0;
  }
}

/* Slide left (navigating forward) */
.slide-left-enter-active,
.slide-left-leave-active {
  transition: transform 0.65s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.65s cubic-bezier(0.4, 0, 0.2, 1);
}
.slide-left-enter-from {
  opacity: 0;
  transform: translateX(30px);
}
.slide-left-leave-to {
  opacity: 0;
  transform: translateX(-30px);
}

/* Slide right (navigating backward) */
.slide-right-enter-active,
.slide-right-leave-active {
  transition: transform 0.65s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.65s cubic-bezier(0.4, 0, 0.2, 1);
}
.slide-right-enter-from {
  opacity: 0;
  transform: translateX(-30px);
}
.slide-right-leave-to {
  opacity: 0;
  transform: translateX(30px);
}

@keyframes fadeIn {
  to {
    opacity: 1;
  }
}

.fade-popup-enter-active {
  transition: opacity 0.3s ease;
}
.fade-popup-leave-active {
  transition: opacity 0.2s ease;
}
.fade-popup-enter-from,
.fade-popup-leave-to {
  opacity: 0;
}

/* Gateway reveal — enters while overlay fades out, creating a crossfade.
   transition-delay staggers the reveal slightly behind the overlay fade-out start. */
.gateway-reveal-enter-active {
  transition: opacity 0.7s ease-out, transform 0.7s cubic-bezier(0.22, 1, 0.36, 1);
  transition-delay: 0.15s;
}
.gateway-reveal-leave-active {
  transition: opacity 0.25s ease-in;
}
.gateway-reveal-enter-from {
  opacity: 0;
  transform: translateY(28px);
}
.gateway-reveal-leave-to {
  opacity: 0;
}

/* Mode switch overlay — clean scale+fade in, slow fade-out to crossfade with incoming content */
.switch-mode-overlay-enter-active {
  transition: opacity 0.35s ease-out, transform 0.4s cubic-bezier(0.22, 1, 0.36, 1);
}
.switch-mode-overlay-leave-active {
  transition: opacity 0.55s ease-in-out;
}
.switch-mode-overlay-enter-from {
  opacity: 0;
  transform: scale(1.04);
}
.switch-mode-overlay-leave-to {
  opacity: 0;
}

/* ── Proposal Dark Mode Overrides ── */
/* All selectors use :deep() to penetrate into child section components */

[data-theme="dark"] {
  background-color: #0a1f1c;
  background-image:
    radial-gradient(ellipse 80% 60% at 50% 0%, rgba(16, 185, 129, 0.07) 0%, transparent 60%),
    radial-gradient(ellipse 60% 50% at 80% 100%, rgba(16, 185, 129, 0.04) 0%, transparent 50%);
  background-attachment: fixed;

  /* Page-level art direction: retune the semantic tokens to the proposal's
     dark-teal palette. Custom properties inherit into child components, so
     token-based markup follows this look automatically — no per-class
     :deep allow-list needed for token consumers. */
  --color-surface-muted: #112e29;
  --color-surface-muted-rgb: 17 46 41;
  --color-surface-raised: rgba(230, 239, 239, 0.12);
  --color-border: rgba(230, 239, 239, 0.25);
  --color-border-muted: rgba(230, 239, 239, 0.20);
  --color-primary-soft: rgba(16, 185, 129, 0.25);
  --color-primary-soft-rgb: 16 185 129;
}

[data-theme="dark"] :deep(section),
[data-theme="dark"] :deep(.proposal-summary),
[data-theme="dark"] :deep(.process-methodology),
[data-theme="dark"] :deep(.proposal-closing) {
  background-color: transparent !important;
  box-shadow: none !important;
}

/* Yellow notice backgrounds (validity notice in ProposalClosing) */
[data-theme="dark"] :deep(.bg-yellow-50) {
  background-color: rgba(202, 138, 4, 0.28) !important;
}
[data-theme="dark"] :deep(.border-yellow-200) {
  border-color: rgba(202, 138, 4, 0.45) !important;
}
[data-theme="dark"] :deep(.text-yellow-600) {
  color: #fbbf24 !important;
}

/* Amber backgrounds (discount banners) */
[data-theme="dark"] :deep(.bg-amber-50),
[data-theme="dark"] :deep(.from-amber-50),
[data-theme="dark"] :deep(.to-orange-50) {
  background-color: rgba(217, 119, 6, 0.28) !important;
}
[data-theme="dark"] :deep(.border-amber-300) {
  border-color: rgba(217, 119, 6, 0.50) !important;
}

/* Green notice backgrounds (accepted state, recovery) */
[data-theme="dark"] :deep(.bg-green-50) {
  background-color: rgba(16, 185, 129, 0.22) !important;
}
[data-theme="dark"] :deep(.border-green-200) {
  border-color: rgba(16, 185, 129, 0.30) !important;
}



/* Green-light text */
[data-theme="dark"] :deep(.text-green-light) {
  color: #a0b8b2 !important;
}



/* Borders — emerald shades (stages, methodology, timeline) */
[data-theme="dark"] :deep(.border-emerald-100) {
  border-color: rgba(16, 185, 129, 0.30) !important;
}
[data-theme="dark"] :deep(.border-emerald-200) {
  border-color: rgba(16, 185, 129, 0.40) !important;
}

/* Cards and surfaces — elevated with shadow + emerald glow */
[data-theme="dark"] :deep(.summary-card),
[data-theme="dark"] :deep(.gateway-card) {
  background-color: #16423a !important;
  border-color: rgba(16, 185, 129, 0.25) !important;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.6), 0 0 18px rgba(16, 185, 129, 0.14), inset 0 1px 0 rgba(16, 185, 129, 0.08) !important;
}



/* Client-action badges (ProcessMethodology "Tu aporte" pills) */
[data-theme="dark"] :deep(.bg-primary-soft.text-text-brand) {
  background-color: rgba(16, 185, 129, 0.18) !important;
  color: #6ee7b7 !important;
  border: 1px solid rgba(16, 185, 129, 0.30);
}

/* Timeline, stages connectors */
[data-theme="dark"] :deep(.bg-emerald-200) {
  background-color: rgba(16, 185, 129, 0.40) !important;
}


/* Welcome-back & reading-time popups */
[data-theme="dark"] :deep(.shadow-2xl.border.border-border-muted) {
  background-color: #16423a !important;
  border-color: rgba(16, 185, 129, 0.22) !important;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.65), 0 0 24px rgba(16, 185, 129, 0.15) !important;
}


/* Nav buttons (SectionNavButtons uses scoped CSS with inline rgba) */
[data-theme="dark"] :deep(.nav-side) {
  background: rgba(15, 43, 38, 0.92) !important;
  color: #a0b8b2 !important;
  border-color: rgba(16, 185, 129, 0.3) !important;
}
[data-theme="dark"] :deep(.nav-side:hover) {
  background: rgba(15, 43, 38, 1) !important;
  color: #6ee7b7 !important;
}

/* Index panel in dark */
[data-theme="dark"] :deep(.index-panel) {
  background-color: rgba(10, 31, 28, 0.95) !important;
}
[data-theme="dark"] :deep(.index-toggle) {
  background-color: rgba(15, 43, 38, 0.9) !important;
}

/* Expiration badge dark variants */
[data-theme="dark"] :deep(.bg-primary-soft\/90) {
  background-color: rgba(16, 185, 129, 0.28) !important;
}
[data-theme="dark"] :deep(.bg-yellow-50\/90) {
  background-color: rgba(202, 138, 4, 0.28) !important;
}
[data-theme="dark"] :deep(.bg-orange-50\/90) {
  background-color: rgba(234, 88, 12, 0.28) !important;
}
[data-theme="dark"] :deep(.bg-red-50\/90) {
  background-color: rgba(220, 38, 38, 0.28) !important;
}

/* Share & PDF buttons */
[data-theme="dark"] :deep(.share-btn) {
  background-color: rgba(15, 43, 38, 0.9) !important;
  border-color: rgba(230, 239, 239, 0.15) !important;
}
[data-theme="dark"] :deep(.pdf-download) {
  background-color: rgba(15, 43, 38, 0.9) !important;
  border-color: rgba(230, 239, 239, 0.15) !important;
}

/* RawContentSection prose overrides */
[data-theme="dark"] :deep(.raw-content-card) {
  background-color: #143d35 !important;
  border-color: rgba(16, 185, 129, 0.22) !important;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.6), 0 0 18px rgba(16, 185, 129, 0.14), inset 0 1px 0 rgba(16, 185, 129, 0.08) !important;
}
[data-theme="dark"] :deep(.prose h1),
[data-theme="dark"] :deep(.prose h2),
[data-theme="dark"] :deep(.prose h3),
[data-theme="dark"] :deep(.prose h4) {
  color: #E6EFEF !important;
}
[data-theme="dark"] :deep(.prose p),
[data-theme="dark"] :deep(.prose ul),
[data-theme="dark"] :deep(.prose ol) {
  color: rgba(230, 239, 239, 0.7) !important;
}
[data-theme="dark"] :deep(.prose strong) {
  color: #E6EFEF !important;
}
[data-theme="dark"] :deep(.prose a) {
  color: #6ee7b7 !important;
}

/* FinalNote badge-card and note-content */
[data-theme="dark"] :deep(.badge-card) {
  background-color: #143d35 !important;
  border-color: rgba(16, 185, 129, 0.20) !important;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.6), 0 0 18px rgba(16, 185, 129, 0.14), inset 0 1px 0 rgba(16, 185, 129, 0.08) !important;
}
[data-theme="dark"] :deep(.note-content) {
  background-color: #143d35 !important;
  border-color: rgba(16, 185, 129, 0.20) !important;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.6), 0 0 18px rgba(16, 185, 129, 0.14), inset 0 1px 0 rgba(16, 185, 129, 0.08) !important;
}

[data-theme="dark"] :deep(.hover\:bg-surface-muted:hover) {
  background-color: rgba(230, 239, 239, 0.08) !important;
}

/* Box-shadows on interactive cards — dual layer: depth + emerald glow */
[data-theme="dark"] :deep(.overview-card),
[data-theme="dark"] :deep(.payment-option-card),
[data-theme="dark"] :deep(.step-card),
[data-theme="dark"] :deep(.contact-card) {
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.6), 0 0 18px rgba(16, 185, 129, 0.15), inset 0 1px 0 rgba(16, 185, 129, 0.08) !important;
}
[data-theme="dark"] :deep(.overview-card:hover),
[data-theme="dark"] :deep(.payment-option-card:hover),
[data-theme="dark"] :deep(.step-card:hover),
[data-theme="dark"] :deep(.contact-card:hover) {
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.7), 0 0 28px rgba(16, 185, 129, 0.20), inset 0 1px 0 rgba(16, 185, 129, 0.12) !important;
  border-color: rgba(16, 185, 129, 0.35) !important;
}


/* DevelopmentStages cards */
[data-theme="dark"] :deep(.development-stages .border-emerald-100) {
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.55), 0 0 16px rgba(16, 185, 129, 0.12), inset 0 1px 0 rgba(16, 185, 129, 0.06) !important;
}

/* ProposalClosing recovery/notice cards */
[data-theme="dark"] :deep(.validity-notice) {
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.55), 0 0 16px rgba(16, 185, 129, 0.12) !important;
}

/* Blue recovery cards (ProposalClosing — "not the right time") */
[data-theme="dark"] :deep(.bg-blue-50) {
  background-color: rgba(59, 130, 246, 0.15) !important;
}
[data-theme="dark"] :deep(.border-blue-200) {
  border-color: rgba(59, 130, 246, 0.30) !important;
}

/* Purple recovery cards (ProposalClosing — "does not meet expectations") */
[data-theme="dark"] :deep(.bg-purple-50) {
  background-color: rgba(139, 92, 246, 0.15) !important;
}
[data-theme="dark"] :deep(.border-purple-200) {
  border-color: rgba(139, 92, 246, 0.30) !important;
}


/* Pricing card — intensify shadow for premium feel */
[data-theme="dark"] :deep(.pricing-card) {
  box-shadow: 0 12px 48px rgba(0, 0, 0, 0.7), 0 0 32px rgba(16, 185, 129, 0.18) !important;
}


/* Section dividers — subtle gradient line between sections */
[data-theme="dark"] :deep(section + section)::before {
  content: '';
  display: block;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(16, 185, 129, 0.20) 30%, rgba(16, 185, 129, 0.20) 70%, transparent);
  margin: 0 auto;
  width: 80%;
}

/* Nav buttons & overlays — stronger glass effect */
[data-theme="dark"] :deep(.nav-side) {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.5) !important;
}

/* Index panel — deeper backdrop */
[data-theme="dark"] :deep(.index-panel) {
  box-shadow: 4px 0 24px rgba(0, 0, 0, 0.6) !important;
}

/* Share & PDF buttons — subtle glow on hover */
[data-theme="dark"] :deep(.share-btn:hover),
[data-theme="dark"] :deep(.pdf-download:hover) {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.5), 0 0 12px rgba(16, 185, 129, 0.12) !important;
  border-color: rgba(16, 185, 129, 0.30) !important;
}

/* ── Legacy esmerald background/border tokens — brighten in dark ── */
/* Soft cards (bg-esmerald/5, /10, /12, /15, /20) */
[data-theme="dark"] :deep([class*="bg-esmerald/5"]),
[data-theme="dark"] :deep([class*="bg-esmerald/10"]),
[data-theme="dark"] :deep([class*="bg-esmerald/12"]),
[data-theme="dark"] :deep([class*="bg-esmerald/15"]) {
  background-color: rgba(16, 185, 129, 0.10) !important;
}
[data-theme="dark"] :deep([class*="bg-esmerald/20"]) {
  background-color: rgba(16, 185, 129, 0.15) !important;
}
[data-theme="dark"] :deep([class*="bg-esmerald/40"]) {
  background-color: rgba(16, 185, 129, 0.40) !important;
}
[data-theme="dark"] :deep([class*="bg-esmerald/70"]) {
  background-color: rgba(16, 185, 129, 0.65) !important;
}

/* Borders (border-esmerald/5, /10, /15, /20, /30, /40) */
[data-theme="dark"] :deep([class*="border-esmerald/5"]),
[data-theme="dark"] :deep([class*="border-esmerald/10"]),
[data-theme="dark"] :deep([class*="border-esmerald/15"]) {
  border-color: rgba(16, 185, 129, 0.20) !important;
}
[data-theme="dark"] :deep([class*="border-esmerald/20"]),
[data-theme="dark"] :deep([class*="border-esmerald/30"]),
[data-theme="dark"] :deep([class*="border-esmerald/40"]) {
  border-color: rgba(16, 185, 129, 0.35) !important;
}

/* Hover states */
[data-theme="dark"] :deep([class*="hover\:border-esmerald/20"]:hover),
[data-theme="dark"] :deep([class*="hover\:border-esmerald/30"]:hover) {
  border-color: rgba(16, 185, 129, 0.55) !important;
}
[data-theme="dark"] :deep([class*="hover\:bg-esmerald/10"]:hover) {
  background-color: rgba(16, 185, 129, 0.18) !important;
}
[data-theme="dark"] :deep([class*="hover\:bg-esmerald/90"]:hover) {
  background-color: rgba(16, 185, 129, 0.85) !important;
}

/* Hover on requirement cards that switch to bg-primary-soft */
[data-theme="dark"] :deep(.requirement-card:hover),
[data-theme="dark"] :deep(.task-item:hover) {
  background-color: rgba(16, 185, 129, 0.18) !important;
}

/* ── Teal accents (technical view CTAs and gateway technical card) ── */
[data-theme="dark"] :deep(.text-teal-700) {
  color: #5eead4 !important;
}
[data-theme="dark"] :deep(.hover\:text-teal-900:hover) {
  color: #99f6e4 !important;
}
[data-theme="dark"] :deep(.text-teal-600\/70) {
  color: rgba(94, 234, 212, 0.75) !important;
}
[data-theme="dark"] :deep(.border-teal-500\/25) {
  border-color: rgba(20, 184, 166, 0.45) !important;
}
[data-theme="dark"] :deep(.hover\:border-teal-600:hover) {
  border-color: rgba(20, 184, 166, 0.70) !important;
}
[data-theme="dark"] :deep(.bg-teal-500\/10) {
  background-color: rgba(20, 184, 166, 0.18) !important;
}
[data-theme="dark"] :deep(.decoration-teal-600\/40) {
  text-decoration-color: rgba(94, 234, 212, 0.55) !important;
}

/* ── Investment value-reasons & pricing card polish in dark ── */
/* The yellow check-icon square inside the green pill needs darker icon for legibility */
[data-theme="dark"] :deep(.value-proposition .text-text-brand) {
  color: #002921 !important;
}
/* Pricing card stays green; bump shadow already handled. Inner translucent rows: */
[data-theme="dark"] :deep(.pricing-card .bg-surface\/10) {
  background-color: rgba(255, 255, 255, 0.10) !important;
}

/* Teleported requirement and interest modals carry their local theme. */
</style>
