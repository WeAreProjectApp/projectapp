<template>
  <BaseModal
    :model-value="open"
    :kind="isClient ? 'form-wide' : 'form'"
    title-id="bulk-assign-title"
    :initial-focus="initialFocusSelector"
    @close="emit('close')"
  >
    <div
      class="flex h-full min-h-0 flex-col"
      :data-testid="`${testidPrefix}-bulk-assign-modal`"
    >
      <div class="shrink-0 px-6 pt-6 pb-2">
        <h3 id="bulk-assign-title" class="text-lg font-bold text-text-default">
          {{ isClient ? 'Asignar cliente' : 'Asignar proyecto' }}
        </h3>
        <p class="text-sm text-text-subtle mt-1">
          {{ selectedCount }}
          {{ selectedCount === 1 ? entity.singular : entity.plural }}
          seleccionad{{ selectedCount === 1 ? 'o' : 'os' }}. Elige el destino y
          revisa el alcance antes de confirmar.
        </p>
      </div>

      <!-- The client catalog and the named scope stay visible together. The
           project picker remains the ordinary floating field presentation. -->
      <div class="min-h-0 flex-1 px-6 py-4">
        <div
          v-if="isClient"
          class="grid min-h-0 gap-4 panel-landscape:grid-cols-[minmax(0,1.2fr)_minmax(18rem,0.8fr)]"
        >
          <ClientAutocomplete
            v-model="clientId"
            :active="open"
            :test-id="`${testidPrefix}-bulk-client`"
            placeholder="Filtrar clientes por nombre, correo o empresa..."
            presentation="catalog"
            :show-linked-hint="false"
            sort-storage-key="panel.accounting.bulk-client-name-order"
            :initial-label="clientLabel"
            allow-create
            @select="onClientSelect"
            @create-new="onCreateNewClient"
          />

          <div class="min-w-0 space-y-4">
            <div
              v-if="inlineClientOpen"
              class="space-y-3 rounded-xl border border-border-default bg-surface-raised p-4"
              :data-testid="`${testidPrefix}-bulk-inline-client`"
            >
              <p class="text-sm font-medium text-text-default">Crear cliente nuevo</p>
              <ClientFormFields
                v-model="inlineClient"
                :errors="inlineClientErrors"
                :testid-prefix="`${testidPrefix}-bulk-inline-client`"
                dense
                @clear-error="clearInlineClientError"
              />
              <BaseAlert
                v-if="clientCreateError"
                variant="danger"
                :data-testid="`${testidPrefix}-bulk-inline-client-error`"
              >
                {{ clientCreateError }}
              </BaseAlert>
              <div class="flex justify-end gap-2">
                <BaseButton type="button" variant="secondary" size="sm" @click="cancelInlineClient">
                  Cancelar
                </BaseButton>
                <BaseButton
                  type="button"
                  variant="primary"
                  size="sm"
                  :loading="creatingClient"
                  :disabled="creatingClient"
                  :data-testid="`${testidPrefix}-bulk-inline-client-save`"
                  @click="createInlineClient"
                >
                  {{ creatingClient ? 'Creando...' : 'Crear cliente' }}
                </BaseButton>
              </div>
            </div>

            <ClientBulkAssignSummary
              v-if="hasTarget"
              :plan="plan"
              :record-label="recordLabel"
            />
            <div
              v-else
              class="space-y-2"
              :data-testid="`${testidPrefix}-bulk-selection-review`"
            >
              <p class="text-xs font-semibold uppercase tracking-wide text-text-subtle">
                Registros seleccionados ({{ selectedRows.length }})
              </p>
              <ul
                class="max-h-64 divide-y divide-border-muted overflow-y-auto rounded-lg border border-border-muted bg-surface-muted"
                :data-testid="`${testidPrefix}-bulk-selection-list`"
              >
                <li
                  v-for="row in selectedRows"
                  :key="row.id"
                  class="truncate px-3 py-1.5 text-xs text-text-default"
                  :title="recordLabel(row)"
                >
                  {{ recordLabel(row) }}
                </li>
              </ul>
            </div>
          </div>
        </div>

        <div v-else class="space-y-4">
          <ProjectCatalogSelect
            v-model="projectId"
            :test-id="`${testidPrefix}-bulk-project`"
            placeholder="Buscar el proyecto a asignar..."
            @select="onProjectSelect"
          />
          <ProjectBulkAssignSummary
            v-if="hasTarget"
            :plan="plan"
            :record-label="recordLabel"
          />
        </div>
      </div>

      <!--
        Una sola línea, nunca vacía: o dice por qué Asignar está apagado, o
        confirma a quién se va a enlazar. Es la misma garantía que daba la
        barra antes del menú — un botón apagado sin razón visible es un
        callejón sin salida — sólo que ahora vive pegada al botón que gobierna.
      -->
    </div>
    <template #footer>
      <BaseModalActions>
        <p
          :id="`${testidPrefix}-bulk-hint`"
          class="flex items-center gap-1.5 text-xs text-text-muted min-w-0"
          :data-testid="`${testidPrefix}-bulk-hint`"
          :title="statusLine.text"
          aria-live="polite"
        >
          <component :is="statusLine.icon" class="w-4 h-4 flex-shrink-0" />
          <span class="truncate">{{ statusLine.text }}</span>
        </p>
        <div class="flex flex-col-reverse gap-2 panel-portrait:flex-row panel-portrait:items-center">
          <BaseButton
            variant="secondary"
            size="sm"
            :data-testid="`${testidPrefix}-bulk-assign-cancel`"
            @click="emit('close')"
          >
            Cancelar
          </BaseButton>
          <BaseButton
            variant="primary"
            size="sm"
            :loading="busy"
            :disabled="Boolean(blockedReason)"
            :disabled-reason="blockedReason"
            :aria-describedby="`${testidPrefix}-bulk-hint`"
            :data-testid="isClient
            ? `${testidPrefix}-bulk-assign`
            : `${testidPrefix}-bulk-assign-project`"
            @click="confirm"
          >
            {{ isClient ? 'Asignar cliente' : 'Asignar proyecto' }}
          </BaseButton>
        </div>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import { InformationCircleIcon, LinkIcon } from '@heroicons/vue/24/outline';

import ClientBulkAssignSummary from '~/components/accounting/ClientBulkAssignSummary.vue';
import ProjectBulkAssignSummary from '~/components/accounting/ProjectBulkAssignSummary.vue';
import ClientFormFields from '~/components/clients/ClientFormFields.vue';
import ClientAutocomplete from '~/components/ui/ClientAutocomplete.vue';
import ProjectCatalogSelect from '~/components/accounting/ProjectCatalogSelect.vue';
import BaseAlert from '~/components/base/BaseAlert.vue';
import BaseButton from '~/components/base/BaseButton.vue';
import BaseModal from '~/components/base/BaseModal.vue';
import { useProposalClientsStore } from '~/stores/proposal_clients';
import { clientFormPayload, emptyClientForm } from '~/utils/billingCode';
import { buildAssignmentPlan } from '~/utils/clientAssignment';
import { buildProjectAssignmentPlan } from '~/utils/projectAssignment';

/**
 * Bulk assignment of a client or a project to the current selection.
 *
 * Lives in a modal rather than inline in the bulk bar because the bar had
 * grown to six controls with two of them belonging to different operations
 * entirely. One component for both targets on purpose: they differ only in
 * picker, plan builder and summary — the chrome around them (the live plan,
 * the never-empty reason line, the gated confirm) is the whole value, and a
 * second copy of it is exactly the drift the shared bar was created to stop.
 *
 * This is a mass edit, so the scope has to be visible BEFORE it runs: the
 * summary lists every affected record, and the confirm stays disabled with
 * the reason on screen until there is actually something to change.
 */
const props = defineProps({
  open: { type: Boolean, default: false },
  /** Which side is being assigned. */
  target: { type: String, default: 'client' },
  /** FULL record list from the store, not the filtered rows. */
  rows: { type: Array, default: () => [] },
  selectedIds: { type: Array, default: () => [] },
  /** `{ singular, plural }` noun for the copy. */
  entity: { type: Object, required: true },
  /** (row) => the row's identity in the summary list. */
  recordLabel: { type: Function, required: true },
  testidPrefix: { type: String, required: true },
  /** Store mutation in flight. */
  busy: { type: Boolean, default: false },
});

const emit = defineEmits(['close', 'submit']);

const clientsStore = useProposalClientsStore();
const isClient = computed(() => props.target === 'client');
const initialFocusSelector = computed(() => (
  `[data-testid="${props.testidPrefix}-bulk-${isClient.value ? 'client' : 'project'}"]`
));

const clientId = ref(null);
const clientLabel = ref('');
const projectId = ref(null);
const selectedProjectRow = ref(null);
const inlineClientOpen = ref(false);
const inlineClient = ref(emptyClientForm());
const creatingClient = ref(false);
const clientCreateError = ref('');
const inlineClientErrors = ref({});

/**
 * Selection frozen at open time. The page clears the selection right after a
 * successful submit, and reading it live would blank the plan while the
 * dialog is still transitioning out.
 */
const rowsSnapshot = ref([]);
const idsSnapshot = ref([]);

const selectedCount = computed(() => idsSnapshot.value.length);
const selectedRows = computed(() => {
  const rowsById = new Map(rowsSnapshot.value.map((row) => [row.id, row]));
  return idsSnapshot.value.map((id) => rowsById.get(id)).filter(Boolean);
});

const plan = computed(() => (isClient.value
  ? buildAssignmentPlan({
    rows: rowsSnapshot.value,
    selectedIds: idsSnapshot.value,
    mode: 'assign',
    targetClientId: clientId.value,
    targetClientLabel: clientLabel.value,
  })
  : buildProjectAssignmentPlan({
    rows: rowsSnapshot.value,
    selectedIds: idsSnapshot.value,
    mode: 'assign',
    targetProject: selectedProjectRow.value,
  })));

const hasTarget = computed(() => (
  isClient.value ? clientId.value != null : projectId.value != null
));

/** Empty string = the confirm button is live. */
const blockedReason = computed(() => {
  if (isClient.value) {
    if (!clientId.value) return 'Elige un cliente para poder asignar.';
    if (plan.value.affected.length === 0) {
      return `Todo lo seleccionado ya tiene a ${clientLabel.value}.`;
    }
    return '';
  }
  if (!projectId.value) return 'Elige un proyecto para poder asignar.';
  if (plan.value.affected.length > 0) return '';
  if (plan.value.blockedClientMismatch.length > 0) {
    return `La selección pertenece a otro cliente: "${plan.value.targetProjectLabel}" es de ${plan.value.targetClientLabel || 'otro cliente'}.`;
  }
  return `Todo lo seleccionado ya tiene "${plan.value.targetProjectLabel}".`;
});

/**
 * La razón de bloqueo sólo queda vacía cuando ya hay destino Y hay filas que
 * cambiar, así que el else es exactamente el caso en que corresponde
 * confirmar el enlace. Por eso la línea nunca está vacía.
 */
const statusLine = computed(() => {
  if (blockedReason.value) {
    return { text: blockedReason.value, icon: InformationCircleIcon };
  }
  if (isClient.value) {
    return {
      text: `Cliente enlazado: ${clientLabel.value} (#${clientId.value})`,
      icon: LinkIcon,
    };
  }
  const blocked = plan.value.blockedClientMismatch.length;
  const suffix = blocked > 0
    ? ` · ${blocked} de otro cliente no se ${blocked === 1 ? 'toca' : 'tocan'}`
    : '';
  return {
    text: `Proyecto enlazado: ${plan.value.targetProjectLabel} (#${projectId.value})${suffix}`,
    icon: LinkIcon,
  };
});

function onClientSelect(client) {
  clientLabel.value = client?.name || '';
  if (client) {
    inlineClientOpen.value = false;
    clientCreateError.value = '';
  }
}

function onProjectSelect(project) {
  selectedProjectRow.value = project || null;
}

function onCreateNewClient(typedName) {
  clientCreateError.value = '';
  inlineClientErrors.value = {};
  inlineClient.value = { ...emptyClientForm(), name: typedName || '' };
  inlineClientOpen.value = true;
}

function cancelInlineClient() {
  inlineClientOpen.value = false;
  inlineClient.value = emptyClientForm();
  clientCreateError.value = '';
  inlineClientErrors.value = {};
}

function clearInlineClientError(field) {
  if (!inlineClientErrors.value[field]) return;
  const next = { ...inlineClientErrors.value };
  delete next[field];
  inlineClientErrors.value = next;
}

async function createInlineClient() {
  if (creatingClient.value) return;
  inlineClientErrors.value = {};
  if (!inlineClient.value.name.trim()) {
    inlineClientErrors.value = { name: 'Escribe el nombre del cliente.' };
    return;
  }
  creatingClient.value = true;
  clientCreateError.value = '';
  const result = await clientsStore.createClient(clientFormPayload(inlineClient.value));
  creatingClient.value = false;
  if (!result.success || !result.data?.id) {
    const fields = Object.fromEntries(
      Object.entries(result.errors || {})
        .filter(([field]) => !['message', 'error', 'detail'].includes(field))
        .map(([field, messages]) => [
          field,
          Array.isArray(messages) ? messages.join(' ') : String(messages || ''),
        ]),
    );
    inlineClientErrors.value = fields;
    clientCreateError.value = Object.keys(fields).length
      ? ''
      : (result.errors?.message || result.errors?.error || result.errors?.detail
        || 'No se pudo crear el cliente. Inténtalo de nuevo.');
    return;
  }
  clientId.value = result.data.id;
  onClientSelect(result.data);
  inlineClient.value = emptyClientForm();
}

// Typing in the picker drops the committed id without re-emitting `select`,
// so the label has to follow the id or the summary would name a target that
// is no longer chosen.
watch(clientId, (id) => {
  if (id == null) clientLabel.value = '';
});
watch(projectId, (id) => {
  if (id == null) selectedProjectRow.value = null;
});

// Every opening starts from scratch, and freezes the selection it will act on.
watch(() => props.open, (open) => {
  if (!open) return;
  clientId.value = null;
  clientLabel.value = '';
  projectId.value = null;
  selectedProjectRow.value = null;
  inlineClientOpen.value = false;
  inlineClient.value = emptyClientForm();
  creatingClient.value = false;
  clientCreateError.value = '';
  inlineClientErrors.value = {};
  rowsSnapshot.value = [...props.rows];
  idsSnapshot.value = [...props.selectedIds];
}, { immediate: true });

/**
 * Hand the parent only the rows that actually change — the same ones the
 * summary listed, so the count reported afterwards matches what was promised.
 */
function confirm() {
  if (blockedReason.value || props.busy) return;
  const current = plan.value;
  emit('submit', isClient.value
    ? {
      ids: current.affected.map((row) => row.id),
      client: current.targetClientId,
      mode: 'assign',
      plan: current,
    }
    : {
      ids: current.affected.map((row) => row.id),
      project: current.targetProjectId,
      mode: 'assign',
      plan: current,
    });
  emit('close');
}
</script>
