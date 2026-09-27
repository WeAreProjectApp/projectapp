<script setup>
import {
  computed, onMounted, reactive, ref,
} from 'vue';
import { useConfirmModal } from '~/composables/useConfirmModal';
import { DOCUMENT_STATE_COLORS, stateBadgeVariant } from '~/utils/documentState';
import ProjectStateHelpBadge from '~/components/panel/projects/ProjectStateHelpBadge.vue';

const props = defineProps({
  stateStore: { type: Object, required: true },
  title: { type: String, required: true },
  description: { type: String, required: true },
  backTo: { type: String, required: true },
  backLabel: { type: String, required: true },
  testId: { type: String, default: 'state-catalog' },
  activeCountField: { type: String, required: true },
  activeCountLabel: { type: String, required: true },
  manageGroups: { type: Boolean, default: true },
  operationalEffects: { type: Array, default: () => [] },
});

const notify = usePanelNotify();
const localePath = useLocalePath();
const newState = reactive({
  name: '',
  description: '',
  color: 'gray',
  group: '',
  operational_effect: props.operationalEffects[0]?.value || '',
});
const newGroup = reactive({ name: '', selection_mode: 'additive' });
const editing = reactive({});
const groupEditing = reactive({});
const mergeTargets = reactive({});
const createValidationAttempted = ref(false);
const createApiErrors = reactive({});
const editValidationAttempted = reactive({});
const editApiErrors = reactive({});
const mergeValidationAttempted = reactive({});
const createGroupValidationAttempted = ref(false);
const createGroupApiErrors = reactive({});
const {
  confirmState,
  requestConfirm,
  handleConfirmed,
  handleCancelled,
} = useConfirmModal();

const groups = computed(() => props.stateStore.groups.map((group) => ({
  ...group,
  states: props.stateStore.states.filter((state) => state.group === group.id),
})));

const hasOperationalEffects = computed(() => props.operationalEffects.length > 0);

// Cada catálogo valida sólo los campos que pinta: el de documentos no tiene
// descripción ni efecto operativo, y exigirlos bloquearía el envío con un
// error que nadie ve.
const createStateFields = computed(() => (hasOperationalEffects.value
  ? ['name', 'description', 'group', 'operational_effect']
  : ['name', 'group']));
const editStateFields = computed(() => (hasOperationalEffects.value
  ? ['name', 'description']
  : ['name']));
const editApiFields = computed(() => (hasOperationalEffects.value
  ? ['name', 'description']
  : ['name', 'group']));

function clearErrors(target) {
  Object.keys(target).forEach((field) => delete target[field]);
}

/**
 * Copies the serializer errors the form shows beside a field into `target`.
 * Anything without a field comes back in `rest`, so the caller still reports
 * it instead of dropping it.
 */
function captureFieldErrors(target, fieldErrors, allowedFields) {
  clearErrors(target);
  if (!fieldErrors || typeof fieldErrors !== 'object') return { captured: false, rest: '' };
  let captured = false;
  const rest = [];
  Object.entries(fieldErrors).forEach(([field, message]) => {
    if (!message) return;
    if (!allowedFields.includes(field)) {
      rest.push(String(message));
      return;
    }
    target[field] = String(message);
    captured = true;
  });
  return { captured, rest: rest.join(' · ') };
}

function createFieldError(field) {
  if (createApiErrors[field]) return createApiErrors[field];
  if (!createValidationAttempted.value || !createStateFields.value.includes(field)) return '';
  if (field === 'name' && !newState.name.trim()) {
    return 'Escribe el nombre del estado.';
  }
  if (field === 'description' && !newState.description.trim()) {
    return 'Explica qué significa el estado.';
  }
  if (field === 'group' && !newState.group) {
    return 'Elige el grupo del estado.';
  }
  if (field === 'operational_effect' && !newState.operational_effect) {
    return 'Elige el efecto operativo del estado.';
  }
  return '';
}

function clearCreateFieldError(field) {
  delete createApiErrors[field];
}

function editFieldError(state, field) {
  if (editApiErrors[state.id]?.[field]) return editApiErrors[state.id][field];
  if (!editValidationAttempted[state.id] || !editStateFields.value.includes(field)) return '';
  const draft = editDraft(state);
  if (field === 'name' && !draft.name.trim()) {
    return 'Escribe el nombre del estado.';
  }
  if (field === 'description' && !draft.description.trim()) {
    return 'Explica qué significa el estado.';
  }
  return '';
}

function clearEditFieldError(stateId, field) {
  if (!editApiErrors[stateId]) return;
  delete editApiErrors[stateId][field];
}

function mergeFieldError(state) {
  if (
    state.system_key
    || !mergeValidationAttempted[state.id]
    || mergeTargets[state.id]
  ) return '';
  return 'Elige el estado de destino.';
}

// Fusionar sólo junta estados del mismo grupo; en proyectos, además, del mismo
// efecto operativo, porque el efecto decide cobros, avisos y cierre.
function mergeCandidates(state) {
  return props.stateStore.activeStates.filter((item) => (
    item.id !== state.id
    && item.group === state.group
    && (!hasOperationalEffects.value || item.operational_effect === state.operational_effect)
  ));
}

const createGroupNameError = computed(() => (
  createGroupApiErrors.name
  || (createGroupValidationAttempted.value && !newGroup.name.trim()
    ? 'Escribe el nombre del grupo.'
    : '')
));

function clearCreateGroupError() {
  delete createGroupApiErrors.name;
}

onMounted(async () => {
  await props.stateStore.fetchCatalog({ includeRetired: true });
  if (!newState.group && props.stateStore.groups.length) {
    newState.group = props.stateStore.groups.find(
      (group) => group.selection_mode === 'additive',
    )?.id || props.stateStore.groups[0].id;
  }
});

async function createState(confirmSimilar = false) {
  createValidationAttempted.value = true;
  if (createStateFields.value.some((field) => createFieldError(field))) return;
  const name = newState.name.trim();
  const payload = {
    ...newState,
    name,
    confirm_similar: confirmSimilar,
  };
  if (!hasOperationalEffects.value) {
    delete payload.operational_effect;
  }
  const result = await props.stateStore.createState(payload);
  if (result.needsConfirmation) {
    const names = result.suggestions.map((item) => item.name).join(', ');
    const confirmed = await requestConfirm({
      title: 'Revisar estados parecidos',
      message: `Ya existen estados parecidos: ${names}. Crear otro puede fragmentar los filtros y el historial.`,
      confirmText: 'Crear de todas formas',
      variant: 'warning',
    });
    if (confirmed) {
      await createState(true);
    }
    return;
  }
  if (!result.success) {
    const { captured, rest } = captureFieldErrors(
      createApiErrors,
      result.fieldErrors,
      createStateFields.value,
    );
    if (!captured || rest) {
      notify.error({ title: 'No se pudo crear', detail: captured ? rest : result.message });
    }
    return;
  }
  newState.name = '';
  newState.description = '';
  createValidationAttempted.value = false;
  clearErrors(createApiErrors);
  notify.success({ title: 'Estado creado' });
}

function editDraft(state) {
  if (!editing[state.id]) {
    editing[state.id] = {
      name: state.name,
      description: state.description || '',
      color: state.color,
      group: state.group,
      order: state.order,
      operational_effect: state.operational_effect || '',
      incompatibility_ids: [...(state.incompatibility_ids || [])],
    };
  }
  return editing[state.id];
}

function groupDraft(group) {
  if (!groupEditing[group.id]) {
    groupEditing[group.id] = {
      name: group.name,
      selection_mode: group.selection_mode,
      order: group.order,
    };
  }
  return groupEditing[group.id];
}

async function saveGroup(group) {
  const result = await props.stateStore.updateGroup(group.id, groupDraft(group));
  if (result.success) {
    delete groupEditing[group.id];
    notify.success({ title: 'Grupo actualizado' });
  } else {
    notify.error({
      title: 'No se pudo actualizar el grupo',
      detail: result.message,
    });
  }
}

async function saveState(state) {
  editValidationAttempted[state.id] = true;
  if (editStateFields.value.some((field) => editFieldError(state, field))) return;
  const payload = { ...editDraft(state) };
  if (!hasOperationalEffects.value) {
    delete payload.operational_effect;
  }
  const result = await props.stateStore.updateState(state.id, payload);
  if (result.success) {
    delete editing[state.id];
    delete editValidationAttempted[state.id];
    delete editApiErrors[state.id];
    notify.success({ title: 'Estado actualizado' });
  } else {
    const errors = {};
    const { captured, rest } = captureFieldErrors(
      errors,
      result.fieldErrors,
      editApiFields.value,
    );
    if (captured) editApiErrors[state.id] = errors;
    if (!captured || rest) {
      notify.error({ title: 'No se pudo actualizar', detail: captured ? rest : result.message });
    }
  }
}

async function retire(state) {
  const confirmed = await requestConfirm({
    title: 'Retirar estado',
    message: `“${state.name}” dejará de aparecer en el selector. Su historial se conservará.`,
    confirmText: 'Retirar estado',
    variant: 'warning',
  });
  if (!confirmed) return;
  const result = await props.stateStore.retireState(state.id);
  if (result.success) notify.success({ title: 'Estado retirado' });
  else notify.error({ title: 'No se puede retirar', detail: result.message });
}

async function merge(state) {
  mergeValidationAttempted[state.id] = true;
  const target = mergeTargets[state.id];
  if (!target) return;
  const targetState = props.stateStore.states.find(
    (item) => item.id === Number(target),
  );
  const confirmed = await requestConfirm({
    title: 'Fusionar estados',
    message: `“${state.name}” se fusionará con “${targetState?.name || 'el estado elegido'}”. Los episodios históricos se conservarán.`,
    confirmText: 'Fusionar estados',
    variant: 'warning',
  });
  if (!confirmed) return;
  const result = await props.stateStore.mergeState(state.id, target);
  if (result.success) {
    delete mergeValidationAttempted[state.id];
    notify.success({ title: 'Estados fusionados' });
  } else {
    notify.error({
      title: 'No se pudieron fusionar',
      detail: result.message,
    });
  }
}

// Sólo la restricción permanente: el destino que falta se dice bajo su selector.
function mergeBlockReasons(state) {
  return [
    state.system_key ? 'Los estados semilla del sistema no se pueden fusionar.' : '',
  ].filter(Boolean);
}

async function createGroup() {
  createGroupValidationAttempted.value = true;
  if (createGroupNameError.value) return;
  const name = newGroup.name.trim();
  const result = await props.stateStore.createGroup({
    ...newGroup,
    name,
    order: props.stateStore.groups.length,
  });
  if (result.success) {
    newGroup.name = '';
    createGroupValidationAttempted.value = false;
    clearErrors(createGroupApiErrors);
    notify.success({ title: 'Grupo creado' });
    return;
  }
  const { captured, rest } = captureFieldErrors(
    createGroupApiErrors,
    result.fieldErrors,
    ['name'],
  );
  if (!captured || rest) {
    notify.error({ title: 'No se pudo crear el grupo', detail: captured ? rest : result.message });
  }
}

function activeCount(state) {
  return state[props.activeCountField] ?? 0;
}
</script>

<template>
  <main class="mx-auto w-full max-w-6xl space-y-6" :data-testid="testId">
    <header class="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <NuxtLink :to="localePath(backTo)" class="inline-flex items-center gap-1 text-sm text-text-muted hover:text-text-default">
          <BaseActionIcon action="back" />
          {{ backLabel }}
        </NuxtLink>
        <h1 class="mt-2 text-2xl font-light text-text-default">{{ title }}</h1>
        <p class="mt-1 max-w-2xl text-sm text-text-muted">{{ description }}</p>
      </div>
    </header>

    <section class="grid gap-4 rounded-xl border border-border-default bg-surface p-5" :class="manageGroups ? 'lg:grid-cols-2' : ''">
      <form class="space-y-3" @submit.prevent="createState()">
        <h2 class="text-sm font-semibold text-text-default">Crear estado</h2>
        <div class="grid gap-2" :class="hasOperationalEffects ? 'sm:grid-cols-2 lg:grid-cols-[minmax(0,1fr)_auto_auto_auto]' : 'sm:grid-cols-[minmax(0,1fr)_auto_auto]'">
          <BaseFormField
            v-slot="{ invalid, errorId }"
            label="Nombre del estado"
            required
            :error="createFieldError('name')"
          >
            <BaseInput
              v-model="newState.name"
              placeholder="Nombre"
              aria-label="Nombre del nuevo estado"
              data-testid="catalog-new-state-name"
              :error="invalid"
              :aria-describedby="errorId"
              @update:model-value="clearCreateFieldError('name')"
            />
          </BaseFormField>
          <BaseFormField
            v-slot="{ errorId }"
            label="Grupo"
            :error="createFieldError('group')"
          >
            <select
              v-model="newState.group"
              aria-label="Grupo del nuevo estado"
              :aria-describedby="errorId"
              class="rounded-lg border border-input-border bg-input-bg px-3 py-2 text-sm"
              @change="clearCreateFieldError('group')"
            >
              <option v-for="group in stateStore.groups.filter((item) => item.is_active)" :key="group.id" :value="group.id">{{ group.name }}</option>
            </select>
          </BaseFormField>
          <BaseFormField
            v-if="hasOperationalEffects"
            v-slot="{ errorId }"
            label="Efecto operativo"
            required
            :error="createFieldError('operational_effect')"
          >
            <select
              v-model="newState.operational_effect"
              aria-label="Efecto operativo del nuevo estado"
              :aria-describedby="errorId"
              class="rounded-lg border border-input-border bg-input-bg px-3 py-2 text-sm"
              @change="clearCreateFieldError('operational_effect')"
            >
              <option v-for="effect in operationalEffects" :key="effect.value" :value="effect.value">{{ effect.label }}</option>
            </select>
          </BaseFormField>
          <BaseFormField label="Color">
            <select v-model="newState.color" aria-label="Color del nuevo estado" class="rounded-lg border border-input-border bg-input-bg px-3 py-2 text-sm">
              <option v-for="color in DOCUMENT_STATE_COLORS" :key="color.value" :value="color.value">{{ color.label }}</option>
            </select>
          </BaseFormField>
        </div>
        <BaseFormField
          v-if="hasOperationalEffects"
          v-slot="{ invalid, errorId }"
          label="Descripción"
          required
          :error="createFieldError('description')"
        >
          <BaseTextarea
            v-model="newState.description"
            :rows="2"
            maxlength="300"
            placeholder="Qué significa este estado para quien lo elige"
            aria-label="Descripción del nuevo estado"
            data-testid="catalog-new-state-description"
            :error="invalid"
            :aria-describedby="errorId"
            @update:model-value="clearCreateFieldError('description')"
          />
        </BaseFormField>
        <p v-if="hasOperationalEffects" class="text-xs text-text-subtle">
          El nombre se puede cambiar; el efecto define cobros, avisos y cierre.
        </p>
        <BaseButton
          type="submit"
          variant="primary"
          size="sm"
          data-testid="catalog-create-state"
        >
          Crear estado
        </BaseButton>
      </form>
      <form v-if="manageGroups" class="space-y-3 border-t border-border-muted pt-4 lg:border-l lg:border-t-0 lg:pl-5 lg:pt-0" @submit.prevent="createGroup">
        <h2 class="text-sm font-semibold text-text-default">Crear grupo</h2>
        <div class="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
          <BaseFormField
            v-slot="{ invalid, errorId }"
            label="Nombre del grupo"
            required
            :error="createGroupNameError"
          >
            <BaseInput
              v-model="newGroup.name"
              placeholder="Nombre del grupo"
              aria-label="Nombre del nuevo grupo"
              data-testid="catalog-new-group-name"
              :error="invalid"
              :aria-describedby="errorId"
              @update:model-value="clearCreateGroupError"
            />
          </BaseFormField>
          <BaseFormField label="Modo">
            <select v-model="newGroup.selection_mode" aria-label="Modo del nuevo grupo" class="rounded-lg border border-input-border bg-input-bg px-3 py-2 text-sm">
              <option value="exclusive">Uno activo</option>
              <option value="additive">Varios activos</option>
            </select>
          </BaseFormField>
        </div>
        <BaseButton
          type="submit"
          variant="secondary"
          size="sm"
          data-testid="catalog-create-group"
        >
          Crear grupo
        </BaseButton>
      </form>
    </section>

    <section v-for="group in groups" :key="group.id" class="rounded-xl border border-border-default bg-surface" :data-testid="`catalog-group-${group.id}`">
      <div class="flex flex-col gap-3 border-b border-border-muted px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div v-if="manageGroups" class="grid flex-1 gap-2 sm:grid-cols-[minmax(0,1fr)_10rem_6rem_auto]">
          <BaseInput v-model="groupDraft(group).name" aria-label="Nombre del grupo" />
          <select v-model="groupDraft(group).selection_mode" class="rounded-lg border border-input-border bg-input-bg px-2 py-2 text-sm">
            <option value="exclusive">Uno activo</option>
            <option value="additive">Varios activos</option>
          </select>
          <BaseInput v-model.number="groupDraft(group).order" type="number" min="0" aria-label="Orden del grupo" />
          <BaseButton variant="secondary" size="sm" :data-testid="`catalog-save-group-${group.id}`" @click="saveGroup(group)">Guardar grupo</BaseButton>
        </div>
        <h2 v-else class="font-medium text-text-default">{{ group.name }}</h2>
        <BaseBadge variant="neutral">{{ group.states.length }} estados</BaseBadge>
      </div>
      <div v-if="!group.states.length" class="p-5 text-sm text-text-muted">No hay estados en este grupo.</div>
      <div v-else class="divide-y divide-border-muted">
        <article
          v-for="state in group.states"
          :key="state.id"
          class="space-y-4 p-4 sm:p-5"
          :class="!state.is_active ? 'opacity-60' : ''"
          :data-testid="`catalog-state-${state.id}`"
        >
          <div class="flex flex-wrap items-center gap-2">
            <BaseBadge :variant="stateBadgeVariant(state)">{{ state.name }}</BaseBadge>
            <ProjectStateHelpBadge
              v-if="hasOperationalEffects"
              :state="state"
              position="bottom"
              :test-id="`catalog-state-help-${state.id}`"
            />
            <BaseBadge v-if="state.system_key" variant="info" size="sm">Semilla</BaseBadge>
            <BaseBadge v-if="!state.is_active" variant="neutral" size="sm">Retirado</BaseBadge>
            <span class="text-xs text-text-muted">{{ activeCount(state) }} {{ activeCountLabel }} activos · {{ state.historical_episode_count }} episodios</span>
          </div>
          <div v-if="state.is_active" class="space-y-3">
            <BaseFormRow
              :cols="2"
              :gap="3"
              at="portrait"
              class="panel-landscape:grid-cols-12"
              :data-testid="`catalog-state-edit-actions-${state.id}`"
            >
              <BaseFormField
                v-slot="{ invalid, errorId }"
                label="Nombre del estado"
                required
                class="panel-landscape:col-span-3"
                :error="editFieldError(state, 'name')"
              >
                <BaseInput
                  v-model="editDraft(state).name"
                  aria-label="Nombre del estado"
                  :error="invalid"
                  :aria-describedby="errorId"
                  @update:model-value="clearEditFieldError(state.id, 'name')"
                />
              </BaseFormField>
              <BaseFormField label="Color" class="panel-landscape:col-span-2">
                <select v-model="editDraft(state).color" aria-label="Color del estado" class="w-full rounded-lg border border-input-border bg-input-bg px-2 py-2 text-sm">
                  <option v-for="color in DOCUMENT_STATE_COLORS" :key="color.value" :value="color.value">{{ color.label }}</option>
                </select>
              </BaseFormField>
              <BaseFormField
                v-if="hasOperationalEffects"
                v-slot="{ errorId }"
                label="Efecto operativo"
                required
                class="panel-landscape:col-span-3"
                :error="editFieldError(state, 'operational_effect')"
              >
                <select
                  v-model="editDraft(state).operational_effect"
                  aria-label="Efecto operativo del estado"
                  :aria-describedby="errorId"
                  class="w-full rounded-lg border border-input-border bg-input-bg px-2 py-2 text-sm"
                  disabled
                  title="El efecto operativo es inmutable"
                >
                  <option v-for="effect in operationalEffects" :key="effect.value" :value="effect.value">{{ effect.label }}</option>
                </select>
              </BaseFormField>
              <BaseFormField
                v-else
                v-slot="{ errorId }"
                label="Grupo"
                class="panel-landscape:col-span-3"
                :error="editFieldError(state, 'group')"
              >
                <select
                  v-model="editDraft(state).group"
                  aria-label="Grupo del estado"
                  :aria-describedby="errorId"
                  class="w-full rounded-lg border border-input-border bg-input-bg px-2 py-2 text-sm"
                  @change="clearEditFieldError(state.id, 'group')"
                >
                  <option v-for="item in stateStore.groups" :key="item.id" :value="item.id">{{ item.name }}</option>
                </select>
              </BaseFormField>
              <BaseFormField label="Orden" class="panel-landscape:col-span-2">
                <BaseInput v-model.number="editDraft(state).order" type="number" min="0" aria-label="Orden" />
              </BaseFormField>
              <BaseFormRowAction class="panel-portrait:col-span-2 panel-landscape:col-span-2">
                <BaseButton
                  class="w-full"
                  variant="secondary"
                  size="sm"
                  :data-testid="`catalog-save-state-${state.id}`"
                  @click="saveState(state)"
                >
                  Guardar
                </BaseButton>
              </BaseFormRowAction>
            </BaseFormRow>
            <BaseFormField
              v-if="hasOperationalEffects"
              v-slot="{ invalid, errorId }"
              label="Descripción"
              required
              :error="editFieldError(state, 'description')"
            >
              <BaseTextarea
                v-model="editDraft(state).description"
                :rows="2"
                maxlength="300"
                :aria-label="`Descripción de ${state.name}`"
                :data-testid="`catalog-state-description-${state.id}`"
                :error="invalid"
                :aria-describedby="errorId"
                @update:model-value="clearEditFieldError(state.id, 'description')"
              />
            </BaseFormField>
          </div>
          <div
            v-if="state.is_active"
            class="grid grid-cols-1 items-start gap-3 border-t border-border-muted pt-4 panel-portrait:grid-cols-12"
            :data-testid="`catalog-state-maintenance-actions-${state.id}`"
          >
            <BaseFormField
              v-slot="{ errorId }"
              size="sm"
              class="min-w-0 panel-portrait:col-span-6 panel-landscape:col-span-8"
              :error="mergeFieldError(state)"
            >
              <select v-model="mergeTargets[state.id]" :aria-label="`Destino para fusionar ${state.name}`" :aria-describedby="errorId" class="w-full rounded-lg border border-input-border bg-input-bg px-2 py-1.5 text-xs">
                <option value="">Fusionar con…</option>
                <option v-for="target in mergeCandidates(state)" :key="target.id" :value="target.id">{{ target.name }}</option>
              </select>
            </BaseFormField>
            <!-- La semilla es una restricción permanente, no un campo por
                 completar: queda como ayuda accesible del botón deshabilitado. -->
            <BaseControlGate
              :reasons="mergeBlockReasons(state)"
              label="Fusionar no disponible"
              align="stretch"
              class="w-full panel-portrait:col-span-3 panel-landscape:col-span-2"
              :visible="false"
            >
              <template #default="{ describedBy }">
                <BaseButton
                  variant="ghost"
                  size="sm"
                  class="w-full"
                  :data-testid="`catalog-merge-state-${state.id}`"
                  :disabled="Boolean(mergeBlockReasons(state).length)"
                  :disabled-reason="mergeBlockReasons(state).join(' ')"
                  :aria-describedby="describedBy"
                  @click="merge(state)"
                >
                  Fusionar
                </BaseButton>
              </template>
            </BaseControlGate>
            <BaseButton
              variant="danger-ghost"
              size="sm"
              class="w-full panel-portrait:col-span-3 panel-landscape:col-span-2"
              :data-testid="`catalog-retire-state-${state.id}`"
              @click="retire(state)"
            >
              Retirar
            </BaseButton>
          </div>
          <details v-if="state.is_active && !hasOperationalEffects" class="rounded-lg border border-border-muted bg-surface-raised px-3 py-2">
            <summary class="cursor-pointer text-xs font-medium text-text-muted">Combinaciones excluidas</summary>
            <div class="mt-2 flex flex-wrap gap-3">
              <label v-for="candidate in stateStore.activeStates.filter((item) => item.id !== state.id)" :key="candidate.id" class="flex min-w-0 max-w-full items-center gap-2 text-xs text-text-default">
                <input v-model="editDraft(state).incompatibility_ids" type="checkbox" :value="candidate.id" class="rounded border-input-border text-text-brand focus:ring-focus-ring/30" />
                <span class="min-w-0 max-w-full [overflow-wrap:anywhere]">{{ candidate.name }}</span>
              </label>
            </div>
          </details>
        </article>
      </div>
    </section>
  </main>
  <ConfirmModal
    v-model="confirmState.open"
    :title="confirmState.title"
    :message="confirmState.message"
    :confirm-text="confirmState.confirmText"
    :cancel-text="confirmState.cancelText"
    :variant="confirmState.variant"
    @confirm="handleConfirmed"
    @cancel="handleCancelled"
  />
</template>
