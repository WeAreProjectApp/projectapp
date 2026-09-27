<template>
  <div>
    <ConfirmModal
      v-model="confirmState.open"
      :title="confirmState.title"
      :message="confirmState.message"
      :confirm-text="confirmState.confirmText"
      :cancel-text="confirmState.cancelText"
      :variant="confirmState.variant"
      :loading="confirmState.busy"
      @confirm="handleConfirmed"
      @cancel="handleCancelled"
    />
    <div class="mb-6">
      <h1 class="text-2xl font-light text-text-default">MCPs</h1>
      <p class="text-sm text-text-subtle mt-1">
        Control operativo de los módulos del Panel desde clientes MCP compatibles.
      </p>
    </div>

    <!-- Guía paso a paso (acordeón nativo, colapsado por defecto) -->
    <details
      class="group mb-6 bg-surface border border-border-muted rounded-xl shadow-sm"
      data-testid="mcps-guide"
    >
      <summary
        class="flex flex-wrap items-center gap-2 p-4 cursor-pointer select-none list-none marker:hidden panel-portrait:gap-3 panel-portrait:p-5 [&::-webkit-details-marker]:hidden"
      >
        <span class="text-sm font-semibold text-text-default">
          ¿Cómo conectar un conector a Claude?
        </span>
        <BaseBadge variant="primary" size="sm" class="shrink-0">Guía paso a paso</BaseBadge>
        <BaseActionIcon action="expand" class="ml-auto text-text-subtle transition-transform duration-200 group-open:rotate-180" />
      </summary>

      <div class="px-4 sm:px-5 pb-5 pt-1 border-t border-border-muted">
        <ol class="space-y-3 mt-4">
          <li
            v-for="(step, index) in guideSteps"
            :key="index"
            class="flex items-start gap-3"
          >
            <span
              class="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-primary-soft text-text-brand text-xs font-semibold"
            >
              {{ index + 1 }}
            </span>
            <p class="text-sm text-text-muted leading-relaxed" v-html="step" />
          </li>
        </ol>

        <p class="text-xs text-text-subtle mt-4 leading-relaxed">
          🔒 El token <strong class="font-semibold text-text-muted">es la credencial</strong>:
          trátalo como una contraseña. Crea credenciales separadas por cliente o propósito,
          limita sus funciones y revócalas cuando dejen de usarse. Las operaciones sensibles
          nunca se ejecutan en la primera llamada: devuelven una vista previa y un
          <code class="text-xs bg-surface-muted rounded px-1 py-0.5">confirmation_id</code> temporal.
        </p>
      </div>
    </details>

    <div v-if="store.loading && store.connectors.length === 0" class="text-center py-16 text-text-subtle text-sm">
      Cargando conectores...
    </div>

    <div
      v-else-if="store.error && store.connectors.length === 0"
      data-testid="mcps-error"
      class="max-w-md bg-surface border border-border-muted rounded-xl shadow-sm p-6 text-center"
    >
      <p class="text-sm text-text-muted mb-4">{{ store.error }}</p>
      <BaseButton variant="secondary" size="sm" @click="store.fetchConnectors()">
        Reintentar
      </BaseButton>
    </div>

    <div v-else class="space-y-3">
      <div
        v-for="connector in store.connectors"
        :key="connector.slug"
        :data-testid="`mcp-card-${connector.slug}`"
        class="bg-surface border border-border-muted rounded-xl shadow-sm overflow-hidden"
      >
        <!-- Accordion header (always visible; click toggles the detail body) -->
        <div
          role="button"
          tabindex="0"
          :aria-expanded="isExpanded(connector.slug)"
          :data-testid="`mcp-card-header-${connector.slug}`"
          class="flex flex-wrap items-center gap-3 px-4 py-4 cursor-pointer select-none transition-colors hover:bg-surface-muted focus:outline-none focus:ring-2 focus:ring-focus-ring/30 panel-portrait:flex-nowrap panel-portrait:px-5"
          @click="toggleRow(connector.slug)"
          @keydown.enter.prevent="toggleRow(connector.slug)"
          @keydown.space.prevent="toggleRow(connector.slug)"
        >
          <BaseActionIcon
            :action="isExpanded(connector.slug) ? 'collapse' : 'expand'"
            class="text-text-subtle"
          />
          <h2
            class="min-w-0 max-w-full flex-1 truncate text-base font-bold text-text-default"
            :title="connector.name"
          >{{ connector.name }}</h2>

          <BaseBadge v-if="connector.is_legacy" variant="neutral" size="sm">
            Compatibilidad
          </BaseBadge>

          <div class="ml-7 flex w-full items-center justify-between gap-2 panel-portrait:ml-auto panel-portrait:w-auto panel-portrait:justify-end panel-portrait:gap-3 panel-portrait:flex-shrink-0">
            <!-- Connection status at a glance (hidden on narrow screens) -->
            <BaseBadge
              :variant="statusVariant(connector)"
              size="sm"
              class="hidden panel-portrait:inline-flex"
              :data-testid="`mcp-connection-badge-${connector.slug}`"
            >
              <span class="h-1.5 w-1.5 rounded-full" :class="statusFor(connector).dot" />
              {{ statusFor(connector).label }}
            </BaseBadge>

            <!-- Active status + toggle: click must not collapse/expand the row -->
            <div class="flex items-center gap-2" @click.stop @keydown.enter.stop @keydown.space.stop>
              <span
                class="text-xs font-medium"
                :class="connector.is_active ? 'text-success-strong' : 'text-text-subtle'"
                :data-testid="`mcp-status-${connector.slug}`"
              >
                {{ connector.is_active ? 'Activo' : 'Inactivo' }}
              </span>
              <BaseToggle
                :model-value="connector.is_active"
                :aria-label="`Activar ${connector.name}`"
                :data-testid="`mcp-toggle-${connector.slug}`"
                @update:model-value="(value) => onToggle(connector, value)"
              />
            </div>
          </div>
        </div>

        <!-- Accordion body: description, status, metadata, sub-accordions, actions -->
        <div
          v-if="isExpanded(connector.slug)"
          :data-testid="`mcp-detail-${connector.slug}`"
          class="border-t border-border-muted px-4 sm:px-5 py-4 space-y-4"
        >
          <p class="min-w-0 max-w-full text-sm text-text-muted [overflow-wrap:anywhere]">{{ connector.description }}</p>

          <!-- Connection status derived from the latest MCP request -->
          <div
            class="flex items-start gap-2 text-sm rounded-lg px-3 py-2"
            :class="statusFor(connector).box"
            :data-testid="`mcp-connection-${connector.slug}`"
          >
            <span class="mt-1 h-2 w-2 rounded-full flex-shrink-0" :class="statusFor(connector).dot" />
            <div class="min-w-0 max-w-full [overflow-wrap:anywhere]">
              <span class="font-medium">{{ statusFor(connector).label }}</span>
              <template v-if="connector.recent_events?.length">
                <span class="text-text-muted">
                  · {{ formatDate(connector.recent_events[0].created_at) }}
                  · {{ eventLabel(connector.recent_events[0]) }}
                </span>
                <p v-if="!connector.recent_events[0].ok && connector.recent_events[0].detail" class="text-xs text-text-muted mt-0.5">
                  {{ connector.recent_events[0].detail }}
                </p>
              </template>
            </div>
          </div>

          <div
            class="flex flex-wrap items-center gap-2"
            :data-testid="`mcp-risk-summary-${connector.slug}`"
          >
            <BaseBadge variant="info" size="sm">
              Lectura {{ connector.risk_counts?.read || 0 }}
            </BaseBadge>
            <BaseBadge variant="primary" size="sm">
              Edición {{ connector.risk_counts?.write || 0 }}
            </BaseBadge>
            <BaseBadge variant="warning" size="sm">
              Sensibles {{ connector.risk_counts?.sensitive || 0 }}
            </BaseBadge>
            <span class="text-xs text-text-subtle">
              {{ connector.tool_count || connector.tools?.length || 0 }} funciones en total
            </span>
          </div>

          <!-- Compatibility token + last used -->
          <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
            <span class="inline-flex items-center gap-1.5 text-text-subtle">
              <KeyIcon class="h-4 w-4" />
              Credencial principal:
            </span>
            <code v-if="connector.has_token" class="text-xs bg-surface-muted rounded px-2 py-1">
              {{ connector.token_prefix }}…
            </code>
            <span v-else class="text-text-subtle">sin generar</span>
            <span v-if="connector.last_used_at" class="text-xs text-text-subtle sm:ml-auto">
              Último uso: {{ formatDate(connector.last_used_at) }}
            </span>
          </div>

          <details class="group" :data-testid="`mcp-credentials-${connector.slug}`">
            <summary
              class="flex items-center gap-2 text-xs font-semibold text-text-subtle uppercase tracking-wider cursor-pointer select-none list-none marker:hidden [&::-webkit-details-marker]:hidden"
              :data-testid="`mcp-credentials-toggle-${connector.slug}`"
            >
              <BaseActionIcon action="expand" class="transition-transform duration-200 group-open:rotate-180" />
              Credenciales ({{ connector.credentials?.length || 0 }})
            </summary>
            <div class="mt-3 space-y-2">
              <p v-if="!connector.credentials?.length" class="text-sm text-text-subtle">
                Todavía no hay credenciales. Crea una con alcance y vencimiento propios.
              </p>
              <div
                v-for="credential in connector.credentials"
                :key="credential.id"
                class="rounded-lg border border-border-muted bg-surface-muted p-3"
                :data-testid="`mcp-credential-${credential.id}`"
              >
                <div class="flex flex-wrap items-start gap-2">
                  <div class="min-w-0 flex-1">
                    <div class="flex flex-wrap items-center gap-2">
                      <span class="font-medium text-sm text-text-default">{{ credential.label }}</span>
                      <BaseBadge :variant="credential.is_usable ? 'success' : 'danger'" size="sm">
                        {{ credential.is_usable ? 'Vigente' : 'No disponible' }}
                      </BaseBadge>
                      <code class="text-xs text-text-subtle">{{ credential.token_prefix }}…</code>
                    </div>
                    <p class="mt-1 text-xs text-text-muted">
                      {{ credentialScopeLabel(credential) }}
                      <template v-if="credential.actor"> · Actor: {{ credential.actor }}</template>
                    </p>
                    <p class="mt-0.5 text-xs text-text-subtle">
                      Vence: {{ credential.expires_at ? formatDate(credential.expires_at) : 'sin vencimiento' }}
                      <template v-if="credential.last_used_at">
                        · Último uso: {{ formatDate(credential.last_used_at) }}
                      </template>
                    </p>
                  </div>
                  <div v-if="credential.is_usable" class="flex flex-wrap gap-1.5">
                    <BaseButton
                      variant="ghost"
                      size="sm"
                      :data-testid="`mcp-credential-edit-${credential.id}`"
                      @click="openCredentialModal(connector, credential)"
                    >
                      Editar alcance
                    </BaseButton>
                    <BaseButton
                      variant="secondary"
                      size="sm"
                      :data-testid="`mcp-credential-rotate-${credential.id}`"
                      @click="onRotateCredential(connector, credential)"
                    >
                      Rotar
                    </BaseButton>
                    <BaseButton
                      variant="danger-ghost"
                      size="sm"
                      :data-testid="`mcp-credential-revoke-${credential.id}`"
                      @click="onRevokeCredential(connector, credential)"
                    >
                      Revocar
                    </BaseButton>
                  </div>
                </div>
              </div>
            </div>
          </details>

          <!-- Sub-accordion: recent activity (collapsed by default) -->
          <details v-if="connector.recent_events?.length" class="group">
            <summary
              class="flex items-center gap-2 text-xs font-semibold text-text-subtle uppercase tracking-wider cursor-pointer select-none list-none marker:hidden [&::-webkit-details-marker]:hidden"
              :data-testid="`mcp-activity-toggle-${connector.slug}`"
            >
              <BaseActionIcon action="expand" class="transition-transform duration-200 group-open:rotate-180" />
              Actividad reciente ({{ connector.recent_events.length }})
            </summary>
            <ul class="mt-2 space-y-1.5" :data-testid="`mcp-activity-list-${connector.slug}`">
              <li
                v-for="(event, index) in connector.recent_events"
                :key="index"
                class="flex flex-wrap items-start gap-x-2 gap-y-0.5 text-xs"
              >
                <span
                  class="mt-1 h-1.5 w-1.5 rounded-full flex-shrink-0"
                  :class="event.ok ? 'bg-success-strong' : 'bg-danger-strong'"
                />
                <span class="whitespace-nowrap text-text-subtle">{{ formatDate(event.created_at) }}</span>
                <span class="min-w-0 max-w-full text-text-default [overflow-wrap:anywhere]">{{ eventLabel(event) }}</span>
                <BaseBadge v-if="event.risk" :variant="riskVariant(event.risk)" size="sm">
                  {{ riskLabel(event.risk) }}
                </BaseBadge>
                <code v-if="event.credential_prefix" class="text-text-subtle">
                  Credencial {{ event.credential_prefix }}…
                </code>
                <span v-if="event.duration_ms != null" class="text-text-subtle">{{ event.duration_ms }} ms</span>
                <code v-if="event.error_code" class="text-danger-strong">{{ event.error_code }}</code>
                <span v-if="showDetail(event)" class="min-w-0 max-w-full text-text-muted [overflow-wrap:anywhere]">{{ event.detail }}</span>
                <span
                  v-if="event.object_refs?.length"
                  class="w-full pl-3.5 text-[10px] text-text-subtle [overflow-wrap:anywhere]"
                >
                  Objetos: {{ formatObjectRefs(event.object_refs) }}
                </span>
                <span v-if="event.request_id" class="w-full pl-3.5 text-[10px] text-text-subtle">
                  Request {{ event.request_id }}
                </span>
              </li>
            </ul>
          </details>

          <!-- Sub-accordion: available tools (collapsed by default) -->
          <details v-if="connector.tools?.length" class="group">
            <summary
              class="flex items-center gap-2 text-xs font-semibold text-text-subtle uppercase tracking-wider cursor-pointer select-none list-none marker:hidden [&::-webkit-details-marker]:hidden"
              :data-testid="`mcp-tools-toggle-${connector.slug}`"
            >
              <BaseActionIcon action="expand" class="transition-transform duration-200 group-open:rotate-180" />
              Funciones disponibles ({{ connector.tools.length }})
            </summary>
            <ul class="mt-2 space-y-1 max-h-72 overflow-y-auto pr-1" :data-testid="`mcp-tools-list-${connector.slug}`">
              <li v-for="tool in connector.tools" :key="tool.name" class="min-w-0 text-sm">
                <code class="break-all rounded bg-surface-muted px-1.5 py-0.5 text-xs">{{ tool.name }}</code>
                <BaseBadge :variant="riskVariant(tool.risk)" size="sm" class="ml-1">
                  {{ riskLabel(tool.risk) }}
                </BaseBadge>
                <BaseBadge v-if="tool.requires_confirmation" variant="warning" size="sm" class="ml-1">
                  Confirmación
                </BaseBadge>
                <span class="ml-1 min-w-0 max-w-full text-text-muted [overflow-wrap:anywhere]">{{ tool.description }}</span>
              </li>
            </ul>
          </details>

          <!-- Credential actions -->
          <div class="flex flex-wrap items-center justify-end gap-2 pt-4 border-t border-border-muted">
            <BaseButton
              variant="secondary"
              size="sm"
              :data-testid="`mcp-create-credential-${connector.slug}`"
              @click="openCredentialModal(connector)"
            >
              Nueva credencial limitada
            </BaseButton>
            <BaseButton
              variant="primary"
              size="sm"
              :data-testid="`mcp-generate-token-${connector.slug}`"
              @click="onGenerateToken(connector)"
            >
              <BaseActionIcon :action="connector.has_token ? 'regenerate' : 'generate'" />
              {{ connector.has_token ? 'Rotar principal' : 'Generar principal' }}
            </BaseButton>
          </div>
        </div>
      </div>
    </div>

    <BaseModal
      v-model="credentialModal.open"
      kind="form-wide"
      padding="md"
      :close-on-backdrop="false"
    >
      <form :id="modalFormId" data-testid="mcp-credential-modal" @submit.prevent="saveCredential">
        <h3 class="text-lg font-bold text-text-default mb-1">
          {{ credentialModal.credentialId ? 'Editar credencial' : 'Nueva credencial' }}
        </h3>
        <p class="text-sm text-text-muted mb-5">
          {{ credentialModal.connector?.name }} · asigna sólo las funciones necesarias.
        </p>

        <div class="grid gap-4 panel-portrait:grid-cols-2">
          <label class="space-y-1">
            <span class="text-xs font-semibold text-text-muted">Etiqueta</span>
            <BaseInput
              v-model="credentialModal.label"
              :disabled="Boolean(credentialModal.credentialId)"
              disabled-reason="La etiqueta identifica la credencial y no puede cambiarse después de crearla."
              maxlength="100"
              placeholder="Ej. Automatización contable"
              data-testid="mcp-credential-label"
            />
          </label>
          <label class="space-y-1">
            <span class="text-xs font-semibold text-text-muted">Vencimiento opcional</span>
            <BaseInput
              v-model="credentialModal.expiresAt"
              type="datetime-local"
              data-testid="mcp-credential-expiry"
            />
          </label>
        </div>

        <label class="block mt-4 space-y-1">
          <span class="text-xs font-semibold text-text-muted">Alcance</span>
          <BaseSelect
            v-model="credentialModal.scopeMode"
            :options="scopeOptions"
            data-testid="mcp-credential-scope"
          />
        </label>

        <div v-if="credentialModal.scopeMode === 'custom'" class="mt-4 rounded-xl border border-border-muted p-3">
          <BaseInput
            v-model="credentialModal.search"
            type="search"
            placeholder="Buscar función por nombre o descripción"
            data-testid="mcp-credential-tool-search"
          />
          <div class="mt-3 max-h-72 space-y-2 overflow-y-auto pr-1">
            <BaseCheckbox
              v-for="tool in visibleCredentialTools"
              :key="tool.name"
              v-model="credentialModal.selectedTools"
              :value="tool.name"
              class="flex"
            >
              <span class="flex flex-wrap items-center gap-1">
                <code class="break-all text-xs">{{ tool.name }}</code>
                <BaseBadge :variant="riskVariant(tool.risk)" size="sm">
                  {{ riskLabel(tool.risk) }}
                </BaseBadge>
                <span class="w-full text-xs text-text-subtle">{{ tool.description }}</span>
              </span>
            </BaseCheckbox>
            <p v-if="!visibleCredentialTools.length" class="text-sm text-text-subtle">
              No hay funciones que coincidan con la búsqueda.
            </p>
          </div>
          <p class="mt-2 text-xs text-text-subtle">
            {{ credentialModal.selectedTools.length }} funciones seleccionadas.
          </p>
        </div>

        <p v-if="credentialModal.error" class="mt-3 text-sm text-danger-strong">
          {{ credentialModal.error }}
        </p>
      </form>
      <template #footer>
        <BaseModalActions>
          <BaseButton variant="secondary" size="sm" @click="closeCredentialModal">
            Cancelar
          </BaseButton>
          <BaseButton
            type="submit" :form="modalFormId"
            variant="primary"
            size="sm"
            :loading="credentialModal.saving"
            data-testid="mcp-credential-save"
          >
            {{ credentialModal.credentialId ? 'Guardar alcance' : 'Crear credencial' }}
          </BaseButton>
        </BaseModalActions>
      </template>
    </BaseModal>

    <!-- One-time token modal -->
    <BaseModal v-model="tokenModal.open" kind="form" padding="md" :close-on-backdrop="false">
      <div data-testid="mcp-token-modal">
        <h3 class="text-lg font-bold text-text-default mb-2">URL de {{ tokenModal.label }}</h3>
        <p class="text-sm text-text-muted mb-4">
          Cópiala ahora: por seguridad no se volverá a mostrar. Pégala en
          claude.ai → Settings → Connectors → “Add custom connector”.
        </p>
        <code
          data-testid="mcp-token-url"
          class="block text-xs bg-surface-muted rounded p-3 break-all mb-4"
        >{{ tokenModal.url }}</code>
      </div>
      <template #footer>
        <BaseModalActions>
          <BaseButton variant="secondary" size="sm" data-testid="mcp-token-copy" @click="copyTokenUrl">
            <BaseActionIcon action="copy" />
            {{ tokenModal.copied ? 'Copiada' : 'Copiar URL' }}
          </BaseButton>
          <BaseButton variant="primary" size="sm" data-testid="mcp-token-close" @click="closeTokenModal">
            Listo, la guardé
          </BaseButton>
        </BaseModalActions>
      </template>
    </BaseModal>
  </div>
</template>

<script setup>
import { useId, computed, onMounted, reactive, ref } from 'vue';
import { KeyIcon } from '@heroicons/vue/24/outline';
import BaseBadge from '~/components/base/BaseBadge.vue';
import BaseButton from '~/components/base/BaseButton.vue';
import BaseCheckbox from '~/components/base/BaseCheckbox.vue';
import BaseInput from '~/components/base/BaseInput.vue';
import BaseModal from '~/components/base/BaseModal.vue';
import BaseSelect from '~/components/base/BaseSelect.vue';
import BaseToggle from '~/components/base/BaseToggle.vue';
import { useConfirmModal } from '~/composables/useConfirmModal';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { usePanelRefresh } from '~/composables/usePanelRefresh';
import { useMcpsStore } from '~/stores/mcps';
import { formatDateTime as formatDate } from '~/utils/formatDate';

definePageMeta({ layout: 'admin', middleware: ['admin-auth', 'superuser-only'] });

const store = useMcpsStore();
const notify = usePanelNotify();
const { confirmState, requestConfirm, handleConfirmed, handleCancelled } = useConfirmModal();

const tokenModal = reactive({ open: false, url: '', label: 'la credencial', copied: false });
const credentialModal = reactive({
  open: false,
  connector: null,
  credentialId: null,
  label: '',
  expiresAt: '',
  scopeMode: 'read',
  selectedTools: [],
  search: '',
  saving: false,
  error: '',
});

const scopeOptions = [
  { value: 'read', label: 'Sólo lectura (recomendado)' },
  { value: 'custom', label: 'Selección personalizada' },
  { value: 'all', label: 'Todas las funciones del conector' },
];

const visibleCredentialTools = computed(() => {
  const search = credentialModal.search.trim().toLowerCase();
  const tools = credentialModal.connector?.tools || [];
  if (!search) return tools;
  return tools.filter((tool) => (
    tool.name.toLowerCase().includes(search)
    || tool.description.toLowerCase().includes(search)
  ));
});

// Which connector rows are expanded (by slug). Reassign a new Set on each
// toggle so Vue's reactivity picks up the change (Set mutations aren't tracked).
const expandedConnectors = ref(new Set());

function isExpanded(slug) {
  return expandedConnectors.value.has(slug);
}

function toggleRow(slug) {
  const next = new Set(expandedConnectors.value);
  if (next.has(slug)) next.delete(slug);
  else next.add(slug);
  expandedConnectors.value = next;
}

// Pasos accionables para conectar un MCP, mostrados en el acordeón de la vista.
// Se permiten <strong> para resaltar la acción/etiqueta real de la UI.
const guideSteps = [
  '<strong>Elige el alcance:</strong> crea una credencial limitada (recomendado) o genera la principal.',
  '<strong>Copia la URL:</strong> se muestra una sola vez en el modal («Copiar URL»). Formato <code class="text-xs bg-surface-muted rounded px-1 py-0.5">…/api/mcp/&lt;slug&gt;/&lt;token&gt;/</code>.',
  '<strong>Actívalo:</strong> enciende el toggle de la card (pasa a «Activo»).',
  '<strong>Conéctalo en claude.ai:</strong> Settings → Connectors → «Add custom connector» → pega la URL.',
  '<strong>Verifica:</strong> pídele algo al conector en el chat; aquí verás «Conectado» y la actividad reciente.',
];

const statusStyles = {
  connected: { label: 'Conectado', dot: 'bg-success-strong', box: 'bg-success-soft text-success-strong' },
  error: { label: 'Error de conexión', dot: 'bg-danger-strong', box: 'bg-danger-soft text-danger-strong' },
  none: { label: 'Sin actividad', dot: 'bg-surface-raised border border-border-default', box: 'bg-surface-muted text-text-muted' },
};

const eventLabels = {
  handshake: 'Conexión (initialize)',
  discovery: 'Descubrimiento de capacidades',
  tool_call: 'Tool',
  auth_error: 'Error de autenticación',
  origin_rejected: 'Origin rechazado',
};

// Maps the connection status to a BaseBadge variant for the header indicator.
const statusVariants = { connected: 'success', error: 'danger', none: 'neutral' };
const riskVariants = { read: 'info', write: 'primary', sensitive: 'warning' };
const riskLabels = { read: 'Lectura', write: 'Edición', sensitive: 'Sensible' };

function statusFor(connector) {
  return statusStyles[connector.connection_status] || statusStyles.none;
}

function statusVariant(connector) {
  return statusVariants[connector.connection_status] || 'neutral';
}

function riskVariant(risk) {
  return riskVariants[risk] || 'neutral';
}

function riskLabel(risk) {
  return riskLabels[risk] || 'Sin clasificar';
}

function readToolNames(connector) {
  return (connector?.tools || [])
    .filter((tool) => tool.risk === 'read')
    .map((tool) => tool.name)
    .sort();
}

function sameNames(left, right) {
  const a = [...left].sort();
  const b = [...right].sort();
  return a.length === b.length && a.every((name, index) => name === b[index]);
}

function credentialScopeLabel(credential) {
  if (!credential.allowed_tools?.length) return 'Todas las funciones';
  return `${credential.allowed_tools.length} funciones autorizadas`;
}

function localDateTime(value) {
  if (!value) return '';
  const date = new Date(value);
  const local = new Date(date.getTime() - (date.getTimezoneOffset() * 60_000));
  return local.toISOString().slice(0, 16);
}

function openCredentialModal(connector, credential = null) {
  const allowedTools = credential?.allowed_tools || [];
  const readTools = readToolNames(connector);
  credentialModal.connector = connector;
  credentialModal.credentialId = credential?.id || null;
  credentialModal.label = credential?.label || '';
  credentialModal.expiresAt = localDateTime(credential?.expires_at);
  credentialModal.scopeMode = (
    !credential ? 'read'
      : !allowedTools.length ? 'all'
        : sameNames(allowedTools, readTools) ? 'read' : 'custom'
  );
  credentialModal.selectedTools = [...allowedTools];
  credentialModal.search = '';
  credentialModal.saving = false;
  credentialModal.error = '';
  credentialModal.open = true;
}

function closeCredentialModal() {
  credentialModal.open = false;
  credentialModal.connector = null;
  credentialModal.error = '';
}

function selectedAllowedTools() {
  if (credentialModal.scopeMode === 'all') return [];
  if (credentialModal.scopeMode === 'read') {
    return readToolNames(credentialModal.connector);
  }
  return [...new Set(credentialModal.selectedTools)].sort();
}

function showOneTimeUrl(data, label) {
  tokenModal.url = data.connector_url;
  tokenModal.label = label;
  tokenModal.copied = false;
  tokenModal.open = true;
}

async function saveCredential() {
  const allowedTools = selectedAllowedTools();
  const label = credentialModal.label.trim();
  if (!credentialModal.credentialId && !label) {
    credentialModal.error = 'La etiqueta es obligatoria.';
    return;
  }
  if (credentialModal.scopeMode === 'custom' && !allowedTools.length) {
    credentialModal.error = 'Selecciona al menos una función para el alcance personalizado.';
    return;
  }
  const payload = {
    allowed_tools: allowedTools,
    expires_at: credentialModal.expiresAt
      ? new Date(credentialModal.expiresAt).toISOString()
      : null,
  };
  credentialModal.saving = true;
  credentialModal.error = '';
  const connector = credentialModal.connector;
  const result = credentialModal.credentialId
    ? await store.updateCredential(connector.slug, credentialModal.credentialId, payload)
    : await store.createCredential(connector.slug, { ...payload, label });
  credentialModal.saving = false;
  if (!result.success) {
    credentialModal.error = result.error;
    return;
  }
  const created = !credentialModal.credentialId;
  closeCredentialModal();
  if (created) showOneTimeUrl(result.data, label);
}

function eventLabel(event) {
  const base = eventLabels[event.event] || event.event;
  if (event.event === 'tool_call' && event.ok && event.detail) {
    return `${base}: ${event.detail}`;
  }
  return base;
}

function showDetail(event) {
  // tool_call OK already carries its detail (the tool name) in the label.
  if (!event.detail) return false;
  return !(event.event === 'tool_call' && event.ok);
}

function formatObjectRefs(refs) {
  return refs
    .map((ref) => `${ref.field}=${Array.isArray(ref.value) ? ref.value.join(',') : ref.value}`)
    .join(' · ');
}

onMounted(() => {
  store.fetchConnectors();
});

usePanelRefresh(() => store.fetchConnectors());

async function onToggle(connector, value) {
  const result = await store.toggleConnector(connector.slug, value);
  if (!result.success) {
    notify.error({ title: 'No se pudo actualizar el conector', detail: result.error });
  }
}

async function onGenerateToken(connector) {
  const result = await store.generateToken(connector.slug);
  if (!result.success) {
    notify.error({ title: 'No se pudo generar el token', detail: result.error });
    return;
  }
  showOneTimeUrl(result.data, `${connector.name} · principal`);
}

async function onRotateCredential(connector, credential) {
  const result = await store.rotateCredential(connector.slug, credential.id);
  if (!result.success) {
    notify.error({ title: 'No se pudo rotar la credencial', detail: result.error });
    return;
  }
  showOneTimeUrl(result.data, `${connector.name} · ${credential.label}`);
}

function onRevokeCredential(connector, credential) {
  requestConfirm({
    title: 'Revocar credencial',
    message: `¿Revocar la credencial “${credential.label}”? La URL actual dejará de funcionar.`,
    confirmText: 'Revocar',
    variant: 'danger',
    waitForConfirm: true,
    onConfirm: async () => {
      const result = await store.revokeCredential(connector.slug, credential.id);
      if (!result.success) {
        notify.error({ title: 'No se pudo revocar la credencial', detail: result.error });
      }
    },
  });
}

async function copyTokenUrl() {
  try {
    await navigator.clipboard.writeText(tokenModal.url);
    tokenModal.copied = true;
  } catch {
    notify.error({ title: 'No se pudo copiar', detail: 'Selecciona la URL manualmente.' });
  }
}

function closeTokenModal() {
  tokenModal.open = false;
  tokenModal.url = '';
  tokenModal.label = 'la credencial';
}

const modalFormId = useId();
</script>
