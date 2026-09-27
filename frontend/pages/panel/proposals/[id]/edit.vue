<template>
  <div>
    <ConfirmModal
      v-model="confirmState.open"
      :title="confirmState.title"
      :message="confirmState.message"
      :confirm-text="confirmState.confirmText"
      :cancel-text="confirmState.cancelText"
      :variant="confirmState.variant"
      :require-type-text="confirmState.requireTypeText"
      :hide-cancel="confirmState.hideCancel"
      :secondary-text="confirmState.secondaryText"
      :secondary-variant="confirmState.secondaryVariant"
      :secondary-hint="confirmState.secondaryHint"
      :loading="confirmState.busy"
      @confirm="handleConfirmed"
      @secondary="handleSecondaryAction"
      @cancel="handleCancelled"
    />
    <ContractParamsModal
      :visible="showContractModal"
      :proposal="proposal"
      :initial-params="proposal?.contract_params || {}"
      :is-editing="contractModalEditing"
      :variant="contractModalVariant"
      @confirm="handleContractConfirm"
      @cancel="showContractModal = false"
    />
    <ProposalActionsModal
      :visible="showActionsModal"
      :proposal="proposal || {}"
      @close="showActionsModal = false"
      @send="handleSend"
      @send-multi="showMultiSendModal = true"
      @resend="handleResend"
      @negotiate="openContractModal(false)"
      @approve="handleStatusChange('accepted')"
      @launch="handleLaunchToPlatform"
      @finish="handleMarkAsFinished"
      @reject="handleStatusChange('rejected')"
      @discount-offer="openDiscountOfferModal"
      @change-status="onStatusSelect"
    />
    <ProposalMultiSendModal
      :visible="showMultiSendModal"
      :current-proposal="proposal || {}"
      @close="showMultiSendModal = false"
      @sent="handleMultiSendSent"
    />
    <ProposalResendModal
      :visible="showResendModal"
      :proposal="proposal || {}"
      @close="showResendModal = false"
      @resent="handleResendComplete"
    />
    <BusinessProposalAdminSyncPreviewModal
      :visible="syncPreviewVisible"
      :project-info="syncPreviewData?.project"
      :deliverable-info="syncPreviewData?.deliverable"
      :diff="syncPreviewData?.diff"
      :is-applying="syncApplying"
      @confirm="handleSyncConfirm"
      @cancel="handleSyncCancel"
    />
    <div class="mb-8">
      <BaseButton as="NuxtLink" :to="localePath('/panel/proposals')" variant="link" size="sm">
        <BaseActionIcon action="back" />
        Volver a propuestas
      </BaseButton>
    </div>

    <!-- Sticky header: title + investment + status -->
    <div v-if="proposal"
         class="sticky top-0 z-30 -mx-4 px-4 py-3 mb-6 bg-surface/80 backdrop-blur-md border-b border-border-muted transition-all sm:-mx-6 sm:px-6 panel-desktop:-mx-8 panel-desktop:px-8">
      <div class="flex flex-wrap items-center gap-2 sm:gap-3">
        <h1 class="text-lg sm:text-xl font-light text-text-default truncate">{{ proposal.title }}</h1>
        <span v-if="proposal.total_investment > 0" class="text-sm sm:text-base font-light text-text-subtle whitespace-nowrap">
          ({{ formatInvestment(proposal.total_investment, proposal.currency) }})
        </span>
        <span
          v-if="hasCustomizedEffectiveTotal"
          data-testid="general-finance-effective-total-badge"
          class="text-xs px-2 py-0.5 rounded-full font-medium bg-warning-soft text-warning-strong whitespace-nowrap"
          :title="`Total efectivo visible al cliente según módulos seleccionados`"
        >
          Cliente ve: {{ formatInvestment(effectiveTotalInvestment, proposal.currency) }}
        </span>
        <ProposalStatusSelect
          :proposal="proposal"
          :updating="statusUpdatingId === proposal.id"
          @change="onStatusSelect"
        />
      </div>
    </div>

    <!-- Loading -->
    <div v-if="proposalStore.isLoading" class="text-center py-12 text-text-subtle text-sm">
      Cargando...
    </div>

    <template v-else-if="proposal">
      <!-- Sobre las pestañas: lo pendiente puede estar en una que no se está
           mirando, así que el aviso tiene que vivir fuera de todas. Nombra qué
           quedó sin guardar en vez de decir sólo que hay algo. -->
      <UnsavedChangesNotice
        v-if="hasUnsavedEdits"
        class="mb-4"
        :title="unsavedTitle"
        :detail="unsavedDetail"
        message="Cada bloque se guarda por separado desde su propio botón. Si sales de esta página, lo pendiente se pierde."
        :can-save="false"
        :can-discard="false"
        testid="proposal-unsaved-notice"
      />

      <!-- Tabs -->
      <BaseTabs v-model="activeTab" :tabs="tabs" />

      <EntityHistoryPanel v-if="activeTab === 'history'" entity-type="proposal" :object-id="proposal.id" />

      <!-- Tab: General -->
      <div v-if="visitedTabs.has('general')" v-show="activeTab === 'general'">
        <ProposalGeneralTab
          :proposal="proposal"
          :form="form"
          :next-action="nextAction"
          :has-documents-tab="hasDocumentsTab"
          :effective-total-investment="effectiveTotalInvestment"
          :has-customized-effective-total="hasCustomizedEffectiveTotal"
          :investment-payment-percentages="investmentPaymentPercentages"
          :payment-amounts="paymentAmounts"
          @update="handleUpdate"
          @toggle-automations="toggleAutomationsPaused"
          @open-email-preview="openEmailPreview"
          @toggle-active="handleToggleActive"
          @toggle-contract-terms="toggleContractTerms"
          @toggle-explainer-video="toggleExplainerVideo"
          @next-action="handleNextAction"
          @open-actions="showActionsModal = true"
          @client-selected="onClientSelected"
          @create-inline-client="onCreateInlineClient"
          @normalize-payment-percentage="normalizeGeneralPaymentPercentage"
        />
      </div>

      <!-- Tab: Correos -->
      <div v-if="visitedTabs.has('emails')" v-show="activeTab === 'emails'">
        <ProposalEmailsTab
          :proposal="proposal"
          @email-intro-saved="handleEmailIntroSaved"
          @dirty-state-change="emailIntroDirty = $event"
          @open-email-preview="openInitialEmailPreview"
        />
      </div>

      <!-- Tab: Documentos -->
      <div v-if="visitedTabs.has('documents')" v-show="activeTab === 'documents'" class="max-w-7xl mx-auto">
        <ProposalDocumentsTab
          v-if="hasProposalDocuments"
          :proposal="proposal"
          :documents="proposal.proposal_documents || []"
          @refresh="refreshData"
          @edit-contract="(variant) => openContractModal(true, variant)"
          @generate-contract="(variant) => openContractModal(false, variant)"
        />
      </div>

      <!-- Tab: Cronograma -->
      <div v-if="visitedTabs.has('schedule')" v-show="activeTab === 'schedule'" class="max-w-7xl mx-auto">
        <ProjectScheduleEditor :proposal="proposal" />
      </div>

      <!-- Tab: Prompt Proposal -->
      <div v-if="visitedTabs.has('prompt')" v-show="activeTab === 'prompt'" class="max-w-7xl mx-auto">
        <ProposalPromptTab :proposal="proposal" />
      </div>

      <!-- Tab: Desarrollo (checklist Markdown) -->
      <div v-if="visitedTabs.has('development')" v-show="activeTab === 'development'">
        <DevChecklistTab
          :proposal="proposal"
          :refreshing="isRefreshing"
          @refresh="refreshData"
        />
      </div>

      <!-- Tab: JSON -->
      <div v-if="visitedTabs.has('json')" v-show="activeTab === 'json'">
        <ProposalJsonTab :proposal="proposal" :active="activeTab === 'json'" @applied="handleJsonApplied" />
      </div>

      <!-- Tab: Activity -->
      <div v-if="visitedTabs.has('activity')" v-show="activeTab === 'activity'" class="max-w-5xl mx-auto">
        <ProposalActivityTab :proposal="proposal" />
      </div>

      <!-- Tab: Analytics -->
      <div v-if="visitedTabs.has('analytics')" v-show="activeTab === 'analytics'" class="max-w-screen-2xl mx-auto">
        <ProposalAnalytics
          :proposal-id="proposal.id"
          :proposal="proposal"
          :refresh-key="analyticsRefreshKey"
          @retried="refreshData"
        />
      </div>

      <!-- Tab: Detalle técnico -->
      <div v-if="visitedTabs.has('technical')" v-show="activeTab === 'technical'" class="max-w-7xl mx-auto">
        <BaseSegmented
          v-model="technicalSubTab"
          class="mb-4 max-w-sm"
          full-width
          :options="[
            { value: 'editor', label: 'Editor', testId: 'technical-editor-subtab' },
            { value: 'json', label: 'JSON', testId: 'technical-json-subtab' },
          ]"
        />
        <div v-show="technicalSubTab === 'editor'">
          <p v-if="!technicalSection" class="text-sm text-warning-strong bg-warning-soft border border-warning-strong/30 rounded-lg px-4 py-3">
            No se encontró la sección «Detalle técnico». Ejecuta migraciones o crea la propuesta de nuevo.
          </p>
          <template v-else>
            <BaseCheckbox
              :model-value="technicalSection.is_enabled"
              class="mb-4"
              @update:model-value="toggleTechnicalSectionEnabled"
            >
              Visible en la propuesta (cuando exista vista pública del modo técnico)
            </BaseCheckbox>
            <TechnicalDocumentEditor
              :key="technicalSection.id"
              :section="technicalSection"
              :module-link-options="technicalModuleLinkOptions"
              :item-link-options="technicalItemLinkOptions"
              @save="handleSaveSection"
            />
          </template>
        </div>
        <div v-if="technicalSubTab === 'json'" class="space-y-4">
          <p class="text-xs text-text-muted">
            Solo el objeto <code class="bg-surface-raised px-1 rounded">content_json</code> del detalle técnico. Debe ser JSON válido (mismo esquema que el editor).
          </p>
          <JsonStatsPanel :stats="technicalJsonStats" test-id="technical-json-stats" />
          <BaseTextarea
            v-model="technicalJsonRaw"
            data-testid="technical-json-textarea"
            :rows="JSON_TEXTAREA_ROWS"
            class="font-mono"
          />
          <div v-if="technicalJsonError" class="text-sm text-danger-strong bg-danger-soft px-4 py-2 rounded-lg">{{ technicalJsonError }}</div>
          <BaseButton variant="primary" size="lg" @click="handleApplyTechnicalJson">
            Guardar JSON
          </BaseButton>
        </div>
      </div>

      <!-- Tab: Sections -->
      <div v-if="visitedTabs.has('sections')" v-show="activeTab === 'sections'" class="max-w-7xl mx-auto">
        <ProposalSectionsTab
          :proposal="proposal"
          :module-link-options="technicalModuleLinkOptions"
          :item-link-options="technicalItemLinkOptions"
          @send="handleSend"
          @resend="handleResend"
          @sync-hosting-percent="handleSyncHostingPercent"
          @dirty-state-change="sectionsDirty = $event"
        />
      </div>

      <!-- Tab: Hour rate -->
      <div v-if="visitedTabs.has('hour-rate')" v-show="activeTab === 'hour-rate'" class="max-w-7xl mx-auto">
        <ProposalHourRateTab
          :proposal="proposal"
          @dirty-state-change="hourRateDirty = $event"
        />
      </div>
    </template>

    <!-- Pre-send scorecard modal -->
    <BaseModal v-model="showSendChecklist" kind="confirm" padding="md">
      <div class="flex items-center justify-between mb-1">
        <h3 class="text-lg font-bold text-text-default">Scorecard pre-envío</h3>
        <BaseBadge
          v-if="scorecardData"
          :variant="scorecardData.score >= 8 ? 'success' : scorecardData.score >= 5 ? 'warning' : 'danger'"
        >
          {{ scorecardData.score }}/10
        </BaseBadge>
      </div>
      <p class="text-sm text-text-muted mb-5">{{ scorecardLoading ? 'Verificando...' : 'Verifica que todo esté listo antes de enviar.' }}</p>
      <ul v-if="!scorecardLoading" class="space-y-3 mb-6">
        <li v-for="(item, idx) in sendChecklist" :key="item.key || idx" class="flex items-center gap-3">
          <span class="w-6 h-6 rounded-full flex items-center justify-center text-sm flex-shrink-0"
            :class="item.pass ? 'bg-success-soft text-success-strong' : item.blocker ? 'bg-danger-soft text-danger-strong' : 'bg-warning-soft text-warning-strong'">
            {{ item.pass ? '✓' : '✗' }}
          </span>
          <div class="flex-1 min-w-0">
            <span class="text-sm" :class="item.pass ? 'text-text-muted' : item.blocker ? 'text-danger-strong font-medium' : 'text-warning-strong'">{{ item.label }}</span>
            <span v-if="!item.pass && item.blocker" class="ml-1 text-[10px] text-danger-strong font-semibold uppercase">bloqueante</span>
          </div>
          <BaseButton
            v-if="item.key === 'email_intro' && !item.pass"
            variant="link"
            size="sm"
            @click="openEmailsFromChecklist"
          >
            Completar en Correos
          </BaseButton>
        </li>
      </ul>
      <div v-else class="flex items-center justify-center py-8">
        <span class="text-sm text-text-subtle">Cargando scorecard...</span>
      </div>
      <div class="flex gap-3 justify-end">
        <BaseButton variant="ghost" size="lg" @click="showSendChecklist = false">
          Cancelar
        </BaseButton>
        <BaseControlGate :reasons="sendBlockReasons" label="Enviar no disponible" align="end">
          <template #default="{ describedBy }">
            <BaseButton
              variant="primary"
              size="lg"
              class="!bg-info-strong hover:!bg-info-strong/90"
              :loading="scorecardLoading"
              :disabled="Boolean(sendBlockReasons.length)"
              :disabled-reason="sendBlockReasons.join(' ')"
              :aria-describedby="describedBy"
              @click="confirmSend"
            >
              Enviar al Cliente
            </BaseButton>
          </template>
        </BaseControlGate>
      </div>
    </BaseModal>

    <BaseModal v-model="isPreviewOpen" kind="workspace" padding="none">
      <div class="flex flex-col h-[85vh]">
        <div class="flex items-center justify-between gap-4 p-4 border-b border-input-border">
          <div>
            <h3 class="text-base font-medium text-text-default">Vista previa del correo</h3>
            <p class="text-xs text-text-muted mt-0.5">
              Render real usando los datos guardados de la propuesta + los cambios actuales de la sección de configuración de correo.
            </p>
          </div>
          <div class="flex items-center gap-2">
            <select
              v-model="previewTemplateKey"
              class="px-3 py-2 border border-input-border bg-input-bg text-input-text rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
              data-testid="edit-email-preview-select"
            >
              <option v-for="tpl in PREVIEWABLE_EMAIL_TEMPLATES" :key="tpl.key" :value="tpl.key">
                {{ tpl.label }}
              </option>
            </select>
            <BaseButton variant="secondary" size="md" :loading="previewLoading" @click="loadPreview">
              <BaseActionIcon v-if="!previewLoading" action="refresh" />
              {{ previewLoading ? 'Cargando…' : 'Recargar' }}
            </BaseButton>
            <BaseButton variant="ghost" size="md" @click="isPreviewOpen = false">
              Cerrar
            </BaseButton>
          </div>
        </div>
        <div class="flex-1 overflow-hidden bg-surface-muted">
          <div v-if="previewLoading" class="flex items-center justify-center h-full text-text-muted text-sm">
            Generando vista previa…
          </div>
          <div v-else-if="previewError" class="flex items-center justify-center h-full text-danger-strong text-sm px-6 text-center">
            {{ previewError }}
          </div>
          <iframe
            v-else-if="previewHtml"
            :srcdoc="previewHtml"
            class="w-full h-full border-0"
            sandbox="allow-same-origin"
            title="Vista previa del correo"
          ></iframe>
        </div>
      </div>
    </BaseModal>

    <BaseModal v-model="showDiscountModal" kind="workspace" padding="none">
      <div class="flex flex-col h-[85vh]">
        <div class="flex items-center justify-between gap-4 p-4 border-b border-input-border">
          <div class="flex items-center gap-4">
            <div class="flex flex-col items-center justify-center rounded-2xl bg-danger-strong px-4 py-2 text-white leading-none">
              <span class="text-3xl font-black tracking-tight">-{{ proposal?.discount_percent }}%</span>
              <span class="text-[10px] font-semibold uppercase tracking-widest opacity-90">descuento</span>
            </div>
            <div>
              <h3 class="text-base font-medium text-text-default">Enviar oferta de descuento</h3>
              <p class="text-xs text-text-muted mt-0.5">
                Revisa el correo antes de enviarlo a {{ proposal?.client_email }}.
              </p>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <BaseButton variant="secondary" size="md" :loading="discountPreviewLoading" @click="loadDiscountPreview">
              <BaseActionIcon v-if="!discountPreviewLoading" action="refresh" />
              {{ discountPreviewLoading ? 'Cargando…' : 'Recargar' }}
            </BaseButton>
            <BaseButton
              variant="primary"
              size="md"
              class="!bg-danger-strong hover:!bg-danger-strong/90"
              :disabled="discountSending || discountPreviewLoading"
              @click="confirmSendDiscountOffer"
            >
              {{ discountSending ? 'Enviando…' : 'Enviar oferta' }}
            </BaseButton>
            <BaseButton variant="ghost" size="md" @click="showDiscountModal = false">
              Cerrar
            </BaseButton>
          </div>
        </div>
        <div class="flex-1 overflow-hidden bg-surface-muted">
          <div v-if="discountPreviewLoading" class="flex items-center justify-center h-full text-text-muted text-sm">
            Generando vista previa…
          </div>
          <div v-else-if="discountPreviewError" class="flex items-center justify-center h-full text-danger-strong text-sm px-6 text-center">
            {{ discountPreviewError }}
          </div>
          <iframe
            v-else-if="discountPreviewHtml"
            :srcdoc="discountPreviewHtml"
            class="w-full h-full border-0"
            sandbox="allow-same-origin"
            title="Vista previa de la oferta de descuento"
          ></iframe>
        </div>
      </div>
    </BaseModal>
  </div>
</template>

<script setup>
import EntityHistoryPanel from '~/components/history/EntityHistoryPanel.vue';
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
// General is the default tab: keep it static so the first paint needs no
// extra round-trip. Every other tab panel is only mounted once visited
// (see visitedTabs below), so deferring its chunk costs nothing up front.
import ProposalGeneralTab from '~/components/panel/proposal/ProposalGeneralTab.vue';
import TabPanelSkeleton from '~/components/panel/proposal/TabPanelSkeleton.vue';

/** defineAsyncComponent + the shared skeleton, so a slow chunk shows a
 *  placeholder instead of an empty panel (Vue's 200ms delay still applies). */
const lazyTab = (loader) => defineAsyncComponent({
  loader,
  loadingComponent: TabPanelSkeleton,
});

const ProposalSectionsTab = lazyTab(() => import('~/components/panel/proposal/ProposalSectionsTab.vue'));
const ProposalHourRateTab = lazyTab(() => import('~/components/panel/proposal/ProposalHourRateTab.vue'));
import { DEFAULT_HOSTING_PERCENT, DEFAULT_METHOD_PHASES } from '~/stores/proposals_constants';
// Hoisted so the idle warm-up in onMounted and the async wrapper share ONE
// dynamic-import call site (single chunk; the module registry caches it).
const technicalEditorLoader = () => import('~/components/BusinessProposal/admin/TechnicalDocumentEditor.vue');
const TechnicalDocumentEditor = lazyTab(technicalEditorLoader);
const ProposalAnalytics = lazyTab(() => import('~/components/BusinessProposal/admin/ProposalAnalytics.vue'));
// Modals stay static on purpose: they are gated by a `visible` prop rather
// than v-if, so an async wrapper would still resolve on page load. Switching
// them to v-if would also need their `watch(() => props.visible)` hooks to
// become immediate, since visible is already true at mount time.
import ContractParamsModal from '~/components/BusinessProposal/admin/ContractParamsModal.vue';
import ProposalActionsModal from '~/components/BusinessProposal/admin/ProposalActionsModal.vue';
import ProposalMultiSendModal from '~/components/BusinessProposal/admin/ProposalMultiSendModal.vue';
import ProposalResendModal from '~/components/BusinessProposal/admin/ProposalResendModal.vue';
const ProposalDocumentsTab = lazyTab(() => import('~/components/BusinessProposal/admin/ProposalDocumentsTab.vue'));
const ProposalEmailsTab = lazyTab(() => import('~/components/BusinessProposal/admin/ProposalEmailsTab.vue'));
const ProjectScheduleEditor = lazyTab(() => import('~/components/BusinessProposal/admin/ProjectScheduleEditor.vue'));
import JsonStatsPanel from '~/components/BusinessProposal/admin/JsonStatsPanel.vue';
import { useConfirmModal } from '~/composables/useConfirmModal';
import { usePanelRefresh } from '~/composables/usePanelRefresh';
import { useUnsavedGuard } from '~/composables/useUnsavedGuard';
import UnsavedChangesNotice from '~/components/panel/UnsavedChangesNotice.vue';
import { buildProposalItemLinkOptions, buildProposalModuleLinkOptions } from '~/utils/proposalModuleLinkOptions';
import { getProposalNextAction } from '~/utils/proposalNextAction';
import { JSON_TEXTAREA_ROWS, makeJsonStats } from '~/utils/proposalJsonStats';
const DevChecklistTab = lazyTab(() => import('~/components/panel/proposal/DevChecklistTab.vue'));
const ProposalActivityTab = lazyTab(() => import('~/components/panel/proposal/ProposalActivityTab.vue'));
const ProposalJsonTab = lazyTab(() => import('~/components/panel/proposal/ProposalJsonTab.vue'));
const ProposalPromptTab = lazyTab(() => import('~/components/panel/proposal/ProposalPromptTab.vue'));
import ProposalStatusSelect from '~/components/panel/proposal/ProposalStatusSelect.vue';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { useProposalStatusChange } from '~/composables/useProposalStatusChange';

const localePath = useLocalePath();
definePageMeta({ layout: 'admin', middleware: ['admin-auth'] });

const route = useRoute();
const proposalStore = useProposalStore();
const {
  confirmState, requestConfirm, handleConfirmed, handleSecondaryAction, handleCancelled,
} = useConfirmModal();
// Fed by ProposalSectionsTab's dirty-state-change emit; drives the
// route-leave / beforeunload / refresh guards below.
const sectionsDirty = ref(false);
// Same, for the hour-rate tab.
const hourRateDirty = ref(false);
// The initial-email message is saved independently from the General form.
const emailIntroDirty = ref(false);

const proposal = computed(() => proposalStore.currentProposal);


const allSections = computed(() =>
  [...(proposal.value?.sections || [])].sort((a, b) => a.order - b.order)
);

const technicalSection = computed(() =>
  allSections.value.find(s => s.section_type === 'technical_document') || null
);

const investmentSection = computed(() =>
  allSections.value.find(s => s.section_type === 'investment') || null
);

// Multiplier derived from the loaded proposal: effective / base. The backend
// computes effective_total_investment as base + Σ(base * pct_module/100), so
// the ratio is constant for a given module selection. Reusing it here keeps
// the % logic in a single place (backend) while letting the live form base
// drive the displayed effective total.
const effectiveTotalsMultiplier = computed(() => {
  const base = Number(proposal.value?.total_investment || 0);
  const effective = Number(proposal.value?.effective_total_investment || 0);
  if (base <= 0 || effective <= 0) return 1;
  return effective / base;
});

const effectiveTotalInvestment = computed(() => {
  const liveBase = Number(form.total_investment) || 0;
  return Math.round(liveBase * effectiveTotalsMultiplier.value);
});

const hasCustomizedEffectiveTotal = computed(() => {
  const liveBase = Number(form.total_investment) || 0;
  const effective = effectiveTotalInvestment.value;
  return liveBase > 0 && effective > 0 && Math.round(effective) !== Math.round(liveBase);
});

const technicalModuleLinkOptions = computed(() =>
  buildProposalModuleLinkOptions(proposal.value?.sections || []),
);

const technicalItemLinkOptions = computed(() =>
  buildProposalItemLinkOptions(proposal.value?.sections || []),
);

const validTabs =['general', 'emails', 'documents', 'schedule', 'development', 'sections', 'hour-rate', 'technical', 'prompt', 'json', 'activity', 'analytics'];
const activeTab = ref(validTabs.includes(route.query.tab) ? route.query.tab : 'general');
const technicalSubTab = ref('editor');

// Tabs mount on first visit and stay mounted afterwards. Before this, all 12
// panels rendered eagerly behind v-show, so opening the view paid for every
// tab's DOM (and for the requests the heavier tabs fire on mount) even when
// the user only ever looked at General.
//
// Membership is never removed, which is what makes returning to a tab
// instant: the panel keeps its component instance, so unsaved edits in
// Secciones / Tarifa por hora survive a trip to another tab exactly as they
// did under v-show. That is also why this is a plain v-if and not
// <KeepAlive> — nothing ever unmounts, so there is nothing to cache.
const visitedTabs = ref(new Set([activeTab.value]));
const analyticsRefreshKey = ref(0);

watch(activeTab, async (tab) => {
  visitedTabs.value.add(tab);
  // The tab was read from ?tab= on load but never written back, so a reload
  // or a shared link always dropped the user on General.
  //
  // history.replaceState rather than router.replace: a router navigation
  // re-runs the `admin-auth` middleware, which cost one auth/check request per
  // tab switch (13 instead of 2 across the twelve tabs). Only the URL needs to
  // change — `?tab=` is read once on mount, so a stale router query is fine.
  // `general` es el aterrizaje por defecto y no se escribe: la URL limpia es la
  // vista de reposo.
  if (import.meta.client) {
    const next = tab === 'general' ? null : tab;
    if (new URLSearchParams(window.location.search).get('tab') !== next) {
      const url = new URL(window.location.href);
      if (next) url.searchParams.set('tab', next);
      else url.searchParams.delete('tab');
      window.history.replaceState(window.history.state, '', url);
    }
  }
  if (tab === 'analytics') {
    analyticsRefreshKey.value += 1;
  }
  if (tab === 'activity' && !hasUnsavedEdits.value) {
    await proposalStore.fetchProposal(route.params.id);
    hydrateFormFromProposal();
  }
});
const hasDocumentsTab = computed(() =>
  ['sent', 'viewed', 'negotiating', 'accepted', 'rejected'].includes(proposal.value?.status),
);
const hasProposalDocuments = computed(() =>
  ['sent', 'viewed', 'negotiating', 'accepted', 'rejected'].includes(proposal.value?.status),
);
const hasScheduleTab = computed(() =>
  ['accepted', 'finished'].includes(proposal.value?.status),
);
const hasDevTab = computed(() => proposal.value?.status === 'accepted');

const tabs = computed(() => {
  const base = [
    { id: 'general', label: 'General' },
    { id: 'emails', label: 'Correos' },
  ];
  if (hasDocumentsTab.value) {
    base.push({ id: 'documents', label: 'Documentos' });
  }
  if (hasScheduleTab.value) {
    base.push({ id: 'schedule', label: 'Cronograma' });
  }
  if (hasDevTab.value) {
    base.push({ id: 'development', label: 'Desarrollo' });
  }
  base.push(
    { id: 'sections', label: 'Secciones' },
    { id: 'hour-rate', label: 'Tarifa por hora' },
    { id: 'technical', label: 'Det. técnico' },
    { id: 'prompt', label: 'Prompt Proposal' },
    { id: 'json', label: 'JSON' },
    { id: 'activity', label: 'Actividad' },
    { id: 'history', label: 'Historial' },
    { id: 'analytics', label: 'Analytics' },
  );
  return base;
});

// ── Actions menu (modal) ──
const showActionsModal = ref(false);
const showMultiSendModal = ref(false);
const showResendModal = ref(false);

async function handleMultiSendSent(payload) {
  if (payload?.error) {
    const errors = payload.error;
    notify.error({
      title: 'No se pudo enviar el correo conjunto.',
      detail: errors?.error
        || (errors ? Object.entries(errors).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`).join(' | ') : ''),
    });
    return;
  }
  await refreshData();
  notify.success({
    title: `Correo enviado al cliente con ${payload?.count ?? 0} propuestas.`,
  });
}
const nextAction = computed(() => {
  const base = getProposalNextAction(proposal.value);
  if (!base) return null;
  const launchPending = base.key === 'launch'
    && (isLaunching.value || proposal.value?.platform_onboarding_status === 'pending');
  return {
    ...base,
    disabled: launchPending,
    label: launchPending ? 'Lanzando...' : base.label,
  };
});
function handleNextAction() {
  if (!nextAction.value || nextAction.value.disabled) return;
  const handlers = {
    send: handleSend,
    negotiate: () => openContractModal(false),
    approve: () => handleStatusChange('accepted'),
    launch: handleLaunchToPlatform,
    finish: handleMarkAsFinished,
  };
  handlers[nextAction.value.key]?.();
}

// ── Contract modal state ──
const showContractModal = ref(false);
const contractModalEditing = ref(false);
// Which document the modal generates or edits: the single contract, or the
// product or service contract of a split closing.
const contractModalVariant = ref('combined');
// Past the negotiation entry a save only (re)generates documents; a proposal
// the client moved to negotiation has no contract yet and generates it here.
const CONTRACT_UPDATE_STATUSES = ['negotiating', 'accepted', 'rejected'];

function openContractModal(editing = false, variant = 'combined') {
  contractModalEditing.value = editing;
  contractModalVariant.value = variant;
  showContractModal.value = true;
}

async function handleContractConfirm(params) {
  showContractModal.value = false;
  const updatesOnly = contractModalEditing.value
    || CONTRACT_UPDATE_STATUSES.includes(proposal.value.status);
  const result = updatesOnly
    ? await proposalStore.updateContractParams(proposal.value.id, params, contractModalVariant.value)
    : await proposalStore.saveContractAndNegotiate(proposal.value.id, params);
  if (!result.success) {
    notify.error(result.message || 'No se pudo guardar el contrato.');
  }
}

async function handleStatusChange(newStatus) {
  const result = await proposalStore.updateProposalStatus(proposal.value.id, newStatus);
  if (result.success) {
    proposal.value = result.data;
    const ed = result.email_delivery;
    if (ed && ed.ok === false) {
      notify.warning({
        title: 'Estado actualizado',
        detail: ed.detail || 'No se pudo enviar el correo al cliente.',
      });
    }
  } else {
    notifyProposalFailure(result, 'No se pudo actualizar el estado');
  }
}

// Header status select (admin mode): shared confirm + PATCH + notify flow.
// The store updates currentProposal on success, so no local assignment needed.
const { updatingId: statusUpdatingId, changeStatus } = useProposalStatusChange({
  requestConfirm,
  onNegotiate: () => openContractModal(false),
});

async function onStatusSelect(newStatus) {
  await changeStatus(proposal.value, newStatus);
}

async function handleMarkAsFinished() {
  const confirmed = await requestConfirm({
    title: 'Marcar como finalizada',
    message: 'El proyecto pasará al estado Finalizada y se notificará al cliente por correo. ¿Deseas continuar?',
    variant: 'primary',
    confirmText: 'Marcar como finalizada',
    cancelText: 'Cancelar',
  });
  if (!confirmed) return;
  await handleStatusChange('finished');
}

let cancelOnboardingPoll = null;

async function handleLaunchToPlatform() {
  const alreadyOnboarded = !!proposal.value.platform_onboarding_completed_at;

  if (alreadyOnboarded) {
    const confirmed = await requestConfirm({
      title: 'Re-lanzar a Plataforma',
      message: 'El proyecto, entregables, requerimientos y archivos existentes serán eliminados y recreados desde cero. ¿Deseas continuar?',
      variant: 'danger',
      confirmText: 'Re-lanzar',
      cancelText: 'Cancelar',
    });
    if (!confirmed) return;
  }

  isLaunching.value = true;
  const result = await proposalStore.launchToPlatform(proposal.value.id, alreadyOnboarded);
  if (!result.success) {
    isLaunching.value = false;
    notify.error({
      title: result.errors?.error || 'Error al lanzar a la plataforma.',
    });
    return;
  }

  proposal.value = result.data;

  if (result.data.platform_onboarding_status === 'pending') {
    notify.success({ title: 'Onboarding en progreso...' });
    cancelOnboardingPoll = proposalStore.pollOnboardingStatus(
      proposal.value.id,
      (updated) => {
        proposal.value = updated;
        isLaunching.value = false;
        cancelOnboardingPoll = null;
        if (updated.platform_onboarding_status === 'completed') {
          notify.success({
            title: alreadyOnboarded ? 'Plataforma re-lanzada exitosamente.' : 'Propuesta lanzada a la plataforma.',
          });
        } else {
          notify.error({
            title: 'El onboarding falló. Revisa los logs del servidor.',
          });
        }
      },
    );
  } else {
    isLaunching.value = false;
    const succeeded = result.data.platform_onboarding_status === 'completed';
    notify.push({
      type: succeeded ? 'success' : 'error',
      title: succeeded
        ? (alreadyOnboarded ? 'Plataforma re-lanzada exitosamente.' : 'Propuesta lanzada a la plataforma.')
        : 'El onboarding falló. Revisa los logs del servidor.',
    });
  }
}

const technicalJsonRaw = ref('');
const technicalJsonError = ref('');

function refreshTechnicalJsonFromProposal() {
  const s = technicalSection.value;
  if (!s?.content_json) {
    technicalJsonRaw.value = '{}';
    return;
  }
  try {
    technicalJsonRaw.value = JSON.stringify(s.content_json, null, 2);
  } catch {
    technicalJsonRaw.value = '{}';
  }
  technicalJsonError.value = '';
}

async function handleApplyTechnicalJson() {
  technicalJsonError.value = '';
  const sid = technicalSection.value?.id;
  if (!sid) {
    technicalJsonError.value = 'No hay sección técnica.';
    return;
  }
  let parsed;
  try {
    parsed = JSON.parse(technicalJsonRaw.value.trim());
  } catch (e) {
    technicalJsonError.value = `JSON inválido: ${e.message}`;
    return;
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    technicalJsonError.value = 'El contenido debe ser un objeto JSON.';
    return;
  }
  const result = await proposalStore.updateSection(sid, { content_json: parsed });
  if (result.success) {
    notify.success({ title: 'Detalle técnico actualizado.' });
    await proposalStore.fetchProposal(proposal.value.id);
    refreshTechnicalJsonFromProposal();
  } else {
    notify.error({ title: 'No se pudo guardar.' });
  }
}

const isRefreshing = ref(false);
const notify = usePanelNotify();

// Notify a failed proposal action using the store's normalized error fields.
function notifyProposalFailure(result, fallbackTitle) {
  notify.error({
    title: result?.message || fallbackTitle,
    detail: result?.hint || '',
  });
}
const isLaunching = ref(false);
const syncPreviewVisible = ref(false);
const syncPreviewData = ref(null);
const syncApplying = ref(false);
const pendingSyncPayload = ref(null);
const investmentPaymentPercentages = ref([]);

const form = reactive({
  title: '',
  client_id: null,
  client_name: '',
  client_email: '',
  client_phone: '',
  client_company: '',
  project_type: '',
  market_type: '',
  project_type_custom: '',
  market_type_custom: '',
  language: 'es',
  total_investment: 0,
  currency: 'COP',
  hosting_percent: DEFAULT_HOSTING_PERCENT,
  hosting_discount_nine_month: 40,
  hosting_discount_semiannual: 20,
  hosting_discount_quarterly: 10,
  expires_at: '',
  reminder_days: 10,
  urgency_reminder_days: 15,
  discount_percent: 0,
  automations_paused: false,
  show_contract_terms: true,
  show_explainer_video: true,
  email_intro: '',
  email_features: [],
  email_method_phases: [],
  email_signed_by: 'gustavo',
});



// Preview modal state — see openEmailPreview() trigger in the email config section.
const PREVIEWABLE_EMAIL_TEMPLATES = [
  { key: 'proposal_sent_client', label: 'Propuesta enviada (master)' },
  { key: 'proposal_reminder', label: 'Recordatorio' },
  { key: 'proposal_urgency', label: 'Urgencia con descuento' },
  { key: 'proposal_urgency_no_discount', label: 'Urgencia sin descuento' },
  { key: 'proposal_accepted_client', label: 'Aceptación' },
  { key: 'proposal_finished_client', label: 'Finalización' },
  { key: 'proposal_rejected_client', label: 'Rechazo (agradecimiento)' },
  { key: 'proposal_negotiation_confirmation', label: 'Negociación' },
  { key: 'proposal_reengagement', label: 'Re-engagement post-rechazo' },
  { key: 'proposal_abandonment_followup', label: 'Seguimiento por abandono' },
  { key: 'proposal_investment_interest_followup', label: 'Seguimiento por inversión' },
  { key: 'proposal_scheduled_followup', label: 'Seguimiento programado' },
  { key: 'proposal_documents_sent', label: 'Documentos enviados' },
  { key: 'branded_email', label: 'Correo libre branded' },
];

const isPreviewOpen = ref(false);
const previewLoading = ref(false);
const previewError = ref('');
const previewHtml = ref('');
const previewTemplateKey = ref('proposal_sent_client');
const previewEmailIntroOverride = ref(null);

async function loadPreview() {
  if (!proposal.value?.id) return;
  previewLoading.value = true;
  previewError.value = '';
  previewHtml.value = '';
  const result = await proposalStore.previewProposalEmail(proposal.value.id, {
    template_key: previewTemplateKey.value,
    email_intro: previewEmailIntroOverride.value ?? form.email_intro,
    email_features: form.email_features
      .map((f) => (typeof f === 'string' ? f.trim() : ''))
      .filter(Boolean),
    email_method_phases: form.email_method_phases.map((p) => ({
      number: (p.number || '').trim(),
      title: (p.title || '').trim(),
      duration: (p.duration || '').trim(),
      description: (p.description || '').trim(),
    })),
    email_signed_by: form.email_signed_by,
  });
  previewLoading.value = false;
  if (result.success) {
    previewHtml.value = result.html;
  } else {
    previewError.value = result.error;
  }
}

async function openEmailPreview() {
  previewEmailIntroOverride.value = null;
  isPreviewOpen.value = true;
  await loadPreview();
}

async function openInitialEmailPreview(emailIntro) {
  previewEmailIntroOverride.value = emailIntro;
  previewTemplateKey.value = 'proposal_sent_client';
  isPreviewOpen.value = true;
  await loadPreview();
}

function handleEmailIntroSaved(emailIntro) {
  form.email_intro = emailIntro;
  scorecardData.value = null;
}

watch(previewTemplateKey, () => {
  if (isPreviewOpen.value) loadPreview();
});

// ── Discount offer (manual send with preview) ──────────────────────
const showDiscountModal = ref(false);
const discountPreviewHtml = ref('');
const discountPreviewLoading = ref(false);
const discountPreviewError = ref('');
const discountSending = ref(false);

async function loadDiscountPreview() {
  if (!proposal.value?.id) return;
  discountPreviewLoading.value = true;
  discountPreviewError.value = '';
  discountPreviewHtml.value = '';
  const result = await proposalStore.previewProposalEmail(proposal.value.id, {
    template_key: 'proposal_urgency',
  });
  discountPreviewLoading.value = false;
  if (result.success) {
    discountPreviewHtml.value = result.html;
  } else {
    discountPreviewError.value = result.error;
  }
}

async function openDiscountOfferModal() {
  showDiscountModal.value = true;
  await loadDiscountPreview();
}

async function confirmSendDiscountOffer() {
  if (!proposal.value?.id) return;
  discountSending.value = true;
  const result = await proposalStore.sendDiscountOffer(proposal.value.id);
  discountSending.value = false;
  if (result.success) {
    showDiscountModal.value = false;
    notify.success({ title: 'Oferta de descuento enviada al cliente.' });
  } else {
    notify.error({ title: result.message || 'No se pudo enviar la oferta.' });
  }
}

// True when the admin chose "create a new client" from the autocomplete: the
// backend must build a fresh UserProfile from the inline fields instead of
// editing the currently linked one.
const creatingNewClient = ref(false);


function onClientSelected(client) {
  if (!client) return;
  creatingNewClient.value = false;
  form.client_id = client.id;
  form.client_name = client.name || form.client_name;
  // Empty input is friendlier than a fake placeholder address; the badge already signals it.
  form.client_email = client.is_email_placeholder ? '' : client.email || '';
  form.client_phone = client.phone || form.client_phone;
  form.client_company = client.company || form.client_company;
}

function onCreateInlineClient(typedName) {
  creatingNewClient.value = true;
  form.client_id = null;
  form.client_name = typedName || '';
  // Drop the previously selected client's contact details so the new profile
  // isn't matched (by email) to that existing client.
  form.client_email = '';
  form.client_phone = '';
  form.client_company = '';
}

function parseSectionContentJson(section) {
  if (!section?.content_json) return {};
  if (typeof section.content_json === 'string') {
    try {
      return JSON.parse(section.content_json);
    } catch {
      return {};
    }
  }
  return section.content_json;
}

function parsePercentFromLabel(label) {
  if (!label) return null;
  const match = String(label).match(/(\d+(?:[.,]\d+)?)\s*%/);
  if (!match) return null;
  const parsed = Number(match[1].replace(',', '.'));
  return Number.isFinite(parsed) ? parsed : null;
}

function normalizePercent(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return 0;
  const clamped = Math.min(100, Math.max(0, numeric));
  return Math.round(clamped * 100) / 100;
}

function formatPercent(value) {
  const normalized = normalizePercent(value);
  if (Number.isInteger(normalized)) return String(normalized);
  return normalized.toFixed(2).replace(/\.?0+$/, '');
}

function extractInvestmentPercentages(contentJson) {
  const paymentOptions = Array.isArray(contentJson?.paymentOptions) ? contentJson.paymentOptions : [];
  return paymentOptions
    .map(opt => parsePercentFromLabel(opt?.label))
    .filter(percent => percent != null)
    .map(percent => normalizePercent(percent));
}

function replaceOrPrefixPercent(label, percent, index) {
  const percentText = `${formatPercent(percent)}%`;
  const base = String(label || '').trim();
  if (!base) return `${percentText} pago ${index + 1}`;
  if (/(\d+(?:[.,]\d+)?)\s*%/.test(base)) {
    return base.replace(/(\d+(?:[.,]\d+)?)\s*%/, percentText);
  }
  return `${percentText} ${base}`;
}

function buildPaymentDescription(percent) {
  const total = Number(effectiveTotalInvestment.value) || 0;
  const amount = Math.round(total * normalizePercent(percent) / 100);
  return `$${amount.toLocaleString('es-CO')} ${form.currency || 'COP'}`;
}

const paymentAmounts = computed(() =>
  investmentPaymentPercentages.value.map(pct => buildPaymentDescription(pct))
);

function normalizeGeneralPaymentPercentage(index) {
  const current = investmentPaymentPercentages.value[index];
  investmentPaymentPercentages.value[index] = normalizePercent(current);
}

watch(
  () => parseSectionContentJson(investmentSection.value)?.paymentOptions,
  (paymentOptions) => {
    investmentPaymentPercentages.value = extractInvestmentPercentages({ paymentOptions });
  },
  { immediate: true, deep: true },
);

async function syncInvestmentPercentagesFromGeneral() {
  const section = investmentSection.value;
  if (!section?.id) return { success: true, skipped: true };

  const contentJson = parseSectionContentJson(section);
  const paymentOptions = Array.isArray(contentJson.paymentOptions) ? contentJson.paymentOptions : [];
  if (!paymentOptions.length || !investmentPaymentPercentages.value.length) {
    return { success: true, skipped: true };
  }

  let editablePercentIdx = 0;
  const nextPaymentOptions = paymentOptions.map((option, idx) => {
    if (parsePercentFromLabel(option?.label) == null) return option;
    const percent = investmentPaymentPercentages.value[editablePercentIdx];
    editablePercentIdx += 1;
    if (percent == null) return option;
    const normalized = normalizePercent(percent);
    return {
      ...option,
      label: replaceOrPrefixPercent(option?.label, normalized, idx),
      description: buildPaymentDescription(normalized),
    };
  });

  const changed = JSON.stringify(paymentOptions) !== JSON.stringify(nextPaymentOptions);
  if (!changed) return { success: true, skipped: true };

  const result = await proposalStore.updateSection(section.id, {
    content_json: {
      ...contentJson,
      paymentOptions: nextPaymentOptions,
    },
  });
  return result.success ? { success: true } : { success: false };
}

function hydrateFormFromProposal() {
  if (!proposal.value) return;
  Object.assign(form, {
    title: proposal.value.title,
    client_id: proposal.value.client?.id ?? null,
    client_name: proposal.value.client_name,
    client_email: proposal.value.client_email || '',
    client_phone: proposal.value.client_phone || '',
    client_company: proposal.value.client?.company || '',
    project_type: proposal.value.project_type || '',
    market_type: proposal.value.market_type || '',
    project_type_custom: proposal.value.project_type_custom || '',
    market_type_custom: proposal.value.market_type_custom || '',
    language: proposal.value.language || 'es',
    total_investment: Number(proposal.value.total_investment),
    currency: proposal.value.currency,
    hosting_percent: proposal.value.hosting_percent ?? DEFAULT_HOSTING_PERCENT,
    hosting_discount_nine_month: proposal.value.hosting_discount_nine_month ?? 40,
    hosting_discount_semiannual: proposal.value.hosting_discount_semiannual ?? 20,
    hosting_discount_quarterly: proposal.value.hosting_discount_quarterly ?? 10,
    expires_at: proposal.value.expires_at
      ? proposal.value.expires_at.slice(0, 16)
      : '',
    reminder_days: proposal.value.reminder_days,
    urgency_reminder_days: proposal.value.urgency_reminder_days ?? 15,
    discount_percent: proposal.value.discount_percent ?? 0,
    // Backend default is False (automations enabled) — keep the fallback aligned.
    automations_paused: proposal.value.automations_paused ?? false,
    show_contract_terms: proposal.value.show_contract_terms ?? true,
    show_explainer_video: proposal.value.show_explainer_video ?? true,
    email_intro: proposal.value.email_intro || '',
    email_features: Array.isArray(proposal.value.email_features) ? [...proposal.value.email_features] : [],
    email_method_phases: Array.isArray(proposal.value.email_method_phases) && proposal.value.email_method_phases.length
      ? proposal.value.email_method_phases.map((p) => ({ ...p }))
      : DEFAULT_METHOD_PHASES.map((p) => ({ ...p })),
    email_signed_by: proposal.value.email_signed_by || 'gustavo',
  });
  creatingNewClient.value = false;
}

onMounted(async () => {
  const id = route.params.id;
  await proposalStore.fetchProposal(id);
  hydrateFormFromProposal();
  // Warm ONLY the technical editor's JS chunk during idle time — Det. técnico
  // is the heaviest tab and its data is already in the store, so the chunk is
  // the one first-open cost a prefetch can remove. The panel is deliberately
  // NOT pre-mounted: v-auto-resize would measure display:none textareas.
  const warmTechnicalChunk = () => { technicalEditorLoader(); };
  if (typeof window.requestIdleCallback === 'function') {
    window.requestIdleCallback(warmTechnicalChunk, { timeout: 5000 });
  } else {
    setTimeout(warmTechnicalChunk, 3000);
  }
});

/**
 * Cualquier pestaña con ediciones pendientes arma los mismos guards.
 *
 * Vía `flags` y no `snapshot`: esta página no tiene un formulario propio que
 * comparar — el estado sucio se lo reportan sus hijos por emit.
 *
 * Sin `save`: no existe un guardado atómico de la propuesta. Cada SectionEditor
 * guarda el suyo (`defineExpose({ save, isDirty })`) y ProposalSectionsTab no
 * guarda refs a ellos, así que un "guardar todo" necesita esas refs y una
 * historia de fallo parcial. Quedan dos salidas, que es lo que esta página
 * puede cumplir hoy.
 */
const {
  hasChanges: hasUnsavedEdits,
  unsavedTitle,
  unsavedDetail,
  guardedReload,
} = useUnsavedGuard({
  flags: {
    sections: () => sectionsDirty.value,
    hourRate: () => hourRateDirty.value,
    emailIntro: () => emailIntroDirty.value,
  },
  labels: {
    sections: 'secciones',
    hourRate: 'tarifa por hora',
    emailIntro: 'mensaje del correo',
  },
  reload: refreshData,
  // El modal de esta página ya existe: inyectarlo evita un segundo
  // confirmState que nadie renderiza.
  confirm: requestConfirm,
});

async function refreshData() {
  // fetchProposal re-hidrata cada SectionEditor abierto por su watch profundo y
  // pisa las ediciones sin guardar; el guard pregunta antes. El refetch
  // re-baseliniza los editores, así que las banderas se limpian solas.
  isRefreshing.value = true;
  try {
    await proposalStore.fetchProposal(route.params.id);
    hydrateFormFromProposal();
    if (visitedTabs.value.has('analytics')) {
      analyticsRefreshKey.value += 1;
    }
  } finally {
    isRefreshing.value = false;
  }
}

usePanelRefresh(guardedReload);

onBeforeUnmount(() => {
  if (cancelOnboardingPoll) cancelOnboardingPoll();
});

async function toggleAutomationsPaused() {
  form.automations_paused = !form.automations_paused;
  const result = await proposalStore.updateProposal(proposal.value.id, {
    automations_paused: form.automations_paused,
  });
  if (result.success) {
    notify.success({ title: form.automations_paused ? 'Automatizaciones pausadas.' : 'Automatizaciones reactivadas.' });
  } else {
    form.automations_paused = !form.automations_paused;
    notify.error({ title: 'Error al cambiar automatizaciones.' });
  }
}

async function toggleExplainerVideo(value) {
  if (proposalStore.isUpdating) return;
  const previous = form.show_explainer_video;
  form.show_explainer_video = value;
  const result = await proposalStore.updateProposal(proposal.value.id, { show_explainer_video: value });
  if (result.success) {
    notify.success({ title: 'Preferencia del video guardada.' });
  } else {
    form.show_explainer_video = previous;
    notify.error({ title: 'No se pudo guardar la visibilidad del video. Intenta de nuevo.' });
  }
}

async function toggleContractTerms() {
  const previousValue = form.show_contract_terms;
  form.show_contract_terms = !previousValue;
  const result = await proposalStore.updateProposal(proposal.value.id, {
    show_contract_terms: form.show_contract_terms,
  });
  if (result.success) {
    notify.success({
      title: form.show_contract_terms
        ? 'Contrato y condiciones visible.'
        : 'Contrato y condiciones oculto.',
    });
  } else {
    form.show_contract_terms = previousValue;
    notify.error({ title: 'No se pudo cambiar la visibilidad del contrato.' });
  }
}

function sanitizeEmailMetadata(payload) {
  payload.email_features = (payload.email_features || [])
    .map((f) => (typeof f === 'string' ? f.trim() : ''))
    .filter(Boolean);
  payload.email_method_phases = (payload.email_method_phases || []).map((p) => ({
    number: (p.number || '').trim(),
    title: (p.title || '').trim(),
    duration: (p.duration || '').trim(),
    description: (p.description || '').trim(),
  }));
  return payload;
}

async function handleUpdate() {
  const payload = sanitizeEmailMetadata({ ...form });
  if (creatingNewClient.value) {
    payload.create_new_client = true;
    payload.propagate_client_updates = false;
    payload.client_id = null;
  } else {
    payload.propagate_client_updates = true;
  }
  if (payload.expires_at) {
    const d = new Date(payload.expires_at);
    payload.expires_at = isNaN(d.getTime()) ? null : d.toISOString();
  } else {
    payload.expires_at = null;
  }
  const result = await proposalStore.updateProposal(proposal.value.id, payload);
  if (result.success) {
    const syncResult = await syncInvestmentPercentagesFromGeneral();
    if (syncResult.success) {
      notify.success({ title: 'Propuesta actualizada.' });
    } else {
      notify.error({ title: 'Se actualizó la propuesta, pero falló la sincronización de porcentajes de inversión.' });
    }
  } else {
    const errors = result.errors;
    notify.error({
      title: 'Error al actualizar.',
      detail: errors
        ? Object.entries(errors).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`).join(' | ')
        : '',
    });
  }
}

const showSendChecklist = ref(false);
const scorecardData = ref(null);
const scorecardLoading = ref(false);

const sendChecklist = computed(() => {
  if (scorecardData.value?.checks) {
    return scorecardData.value.checks.map(c => ({
      key: c.key,
      label: c.label,
      pass: c.passed,
      blocker: c.blocker,
    }));
  }
  // Fallback to local checks if scorecard hasn't loaded
  return [
    { label: 'Email del cliente configurado', pass: !!form.client_email?.trim(), blocker: true },
    { label: 'Nombre del cliente', pass: !!form.client_name?.trim(), blocker: true },
    { key: 'email_intro', label: 'Mensaje personalizado del correo', pass: !!form.email_intro?.trim(), blocker: true },
    { label: 'Inversión > $0', pass: Number(form.total_investment) > 0, blocker: true },
    { label: 'Fecha de expiración futura', pass: !!form.expires_at && new Date(form.expires_at) > new Date(), blocker: true },
    { label: 'Al menos 1 sección habilitada', pass: allSections.value?.some(s => s.is_enabled), blocker: true },
  ];
});

const allChecksPassing = computed(() => {
  if (scorecardData.value) {
    return scorecardData.value.can_send !== false;
  }
  return sendChecklist.value.filter(c => c.blocker).every(c => c.pass);
});

const sendBlockReasons = computed(() => sendChecklist.value
  .filter(item => item.blocker && !item.pass)
  .map(item => item.label));

async function handleSend() {
  showSendChecklist.value = true;
  scorecardLoading.value = true;
  try {
    const result = await proposalStore.fetchScorecard(proposal.value.id);
    if (result.success) {
      scorecardData.value = result.data;
    } else {
      notify.warning({
        title: 'No se pudo cargar el scorecard.',
        detail: 'Se muestran las verificaciones locales.',
      });
    }
  } catch (_e) { /* use local fallback */ }
  scorecardLoading.value = false;
}

async function confirmSend() {
  showSendChecklist.value = false;
  const result = await proposalStore.sendProposal(proposal.value.id);
  if (result.success) {
    const ed = result.email_delivery;
    if (ed && ed.ok === false) {
      notify.warning({
        title: 'Propuesta marcada como enviada',
        detail: ed.detail || 'No se pudo enviar el correo al cliente.',
        action: { label: 'Reenviar', handler: () => handleResend() },
      });
    } else {
      notify.success({ title: 'Propuesta enviada al cliente' });
    }
  } else {
    notifyProposalFailure(result, 'No se pudo enviar la propuesta');
  }
}

function handleResend() {
  showResendModal.value = true;
}

function handleResendComplete(result) {
  hydrateFormFromProposal();
  const ed = result.email_delivery;
  if (ed && ed.ok === false) {
    notify.warning({
      title: 'Reenvío registrado',
      detail: ed.detail || 'No se pudo enviar el correo al cliente.',
    });
  } else {
    notify.success({ title: 'Propuesta re-enviada al cliente' });
  }
}

function openEmailsFromChecklist() {
  showSendChecklist.value = false;
  activeTab.value = 'emails';
}

async function toggleTechnicalSectionEnabled() {
  const s = technicalSection.value;
  if (!s?.id) return;
  const willEnable = !s.is_enabled;
  const result = await proposalStore.updateSection(s.id, { is_enabled: willEnable });
  if (result.success) {
    notify.success({ title: willEnable ? 'Sección técnica habilitada.' : 'Sección técnica deshabilitada.' });
  } else {
    notify.error({ title: 'No se pudo actualizar la sección técnica.' });
  }
}

async function handleToggleActive() {
  const result = await proposalStore.toggleProposalActive(proposal.value.id);
  if (result.success) {
    const label = result.data.is_active ? 'activada' : 'desactivada';
    notify.success({ title: `Propuesta ${label}.` });
  } else {
    notify.error({ title: 'Error al cambiar el estado.' });
  }
}

// Save handler for the TECHNICAL tab only — commercial sections save inside
// ProposalSectionsTab. Accepted proposals route through the sync preview.
async function handleSaveSection({ sectionId, payload }) {
  const isAccepted = proposal.value?.status === 'accepted';

  if (isAccepted) {
    const previewResult = await proposalStore.previewSync(sectionId, payload.content_json);
    if (!previewResult.success) {
      notify.error({ title: 'No se pudo calcular la vista previa de sincronización.' });
      return;
    }
    if (!previewResult.data.has_project) {
      const r = await proposalStore.updateSection(sectionId, payload);
      notify.push(r.success
        ? { type: 'success', title: 'Sección técnica guardada.' }
        : { type: 'error', title: 'Error al guardar.' });
      return;
    }
    syncPreviewData.value = previewResult.data;
    pendingSyncPayload.value = { sectionId, payload };
    syncPreviewVisible.value = true;
    return;
  }

  const r = await proposalStore.updateSection(sectionId, payload);
  if (!r.success) {
    notifyProposalFailure(r, 'No se pudo guardar la sección');
  }
}

async function handleSyncConfirm() {
  syncApplying.value = true;
  const { sectionId, payload } = pendingSyncPayload.value;
  const result = await proposalStore.applySync(sectionId, payload.content_json);
  syncApplying.value = false;
  syncPreviewVisible.value = false;
  syncPreviewData.value = null;
  pendingSyncPayload.value = null;
  notify.push(result.success
    ? { type: 'success', title: 'Sección técnica guardada y proyecto sincronizado.' }
    : { type: 'error', title: 'Error al aplicar la sincronización.' });
}

function handleSyncCancel() {
  syncPreviewVisible.value = false;
  syncPreviewData.value = null;
  pendingSyncPayload.value = null;
}

async function handleSyncHostingPercent(percent) {
  if (form.hosting_percent !== percent) {
    form.hosting_percent = percent;
    await proposalStore.updateProposal(proposal.value.id, { hosting_percent: percent });
  }
}


function formatInvestment(value, currency = 'COP') {
  if (!value) return '';
  const num = Number(value);
  return '$' + num.toLocaleString('es-CO', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) + ' ' + currency;
}

// --- JSON tab (export/import live in ProposalJsonTab) ---
const TECHNICAL_EXPECTED_KEYS = [
  'purpose', 'stack', 'architecture', 'dataModel', 'growthReadiness',
  'epics', 'apiSummary', 'apiDomains', 'integrations', 'environmentsNote',
  'environments', 'security', 'performanceQuality', 'backupsNote',
  'quality', 'decisions',
];

const technicalJsonParsed = computed(() => {
  const raw = technicalJsonRaw.value.trim();
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : null;
  } catch {
    return null;
  }
});

const technicalJsonSource = computed(
  () => technicalJsonParsed.value || technicalSection.value?.content_json || null,
);

const technicalJsonStats = makeJsonStats({
  sourceRef: technicalJsonSource,
  rawStringRef: technicalJsonRaw,
  expectedKeys: TECHNICAL_EXPECTED_KEYS,
  updatedAtRef: computed(() => proposal.value?.updated_at),
});

function handleJsonApplied() {
  // The store already refreshed currentProposal; resync the General form.
  hydrateFormFromProposal();
}

// Refresh only when the JSON pane actually opens (tab entry with the sub-tab
// already on JSON, or switching the sub-tab while on the tab). Entering the
// tab in Editor mode must not pay the full-document stringify.
watch(
  () => activeTab.value === 'technical' && technicalSubTab.value === 'json',
  (jsonPaneOpen) => {
    if (jsonPaneOpen) refreshTechnicalJsonFromProposal();
  },
);

</script>
