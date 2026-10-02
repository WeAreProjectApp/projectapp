<script setup>
/**
 * The client field set, shared by every surface that creates or edits a client.
 *
 * One component rather than one copy per modal on purpose: create, edit and the
 * three inline "crear al vuelo" panels used to ask for different subsets, so a
 * client filed from one of them came out incomplete and had to be edited right
 * after. Sharing the fields is what keeps them in step — order and layout
 * included.
 *
 * Only `name` is required; the panel convention marks required fields with an
 * asterisk, so the absence of that marker already communicates optionality.
 */
import { computed } from 'vue';
import BaseFormField from '~/components/base/BaseFormField.vue';
import BaseFormRow from '~/components/base/BaseFormRow.vue';
import BaseInput from '~/components/base/BaseInput.vue';
import BaseSelect from '~/components/base/BaseSelect.vue';
import { BILLING_CODE_MAX_LENGTH } from '~/utils/billingCode';

const props = defineProps({
  /** Shared identity, contact and billing fields. */
  modelValue: { type: Object, required: true },
  /**
   * Show the archive control. Off by default so the three inline "crear al
   * vuelo" panels don't offer it: you are creating a client to use right now,
   * and filing it away in the same breath is never what that flow means.
   */
  showArchived: { type: Boolean, default: false },
  /**
   * Editing an existing client. The control then only ANNOUNCES the change —
   * flipping it opens the cascade preview, because archiving suspends the
   * client's projects and the plain save must not carry that.
   */
  editing: { type: Boolean, default: false },
  /** Prefix for each field's data-testid, e.g. `clients-new` -> `clients-new-name`. */
  testidPrefix: { type: String, required: true },
  /** Compact input sizing for inline creation. */
  dense: { type: Boolean, default: false },
  /** Field-scoped validation returned by the local form or the API. */
  errors: { type: Object, default: () => ({}) },
});

const emit = defineEmits(['update:modelValue', 'clear-error', 'request-archive']);
const identificationOptions = [
  { value: 'NIT', label: 'NIT · Empresa' },
  { value: 'CC', label: 'C.C. · Persona natural' },
];
const identificationType = computed(() => props.modelValue.identification_type
  || (props.modelValue.nit ? 'NIT' : (props.modelValue.cedula ? 'CC' : 'NIT')));
const identificationField = computed(() => identificationType.value === 'CC' ? 'cedula' : 'nit');

function update(field, value) {
  emit('update:modelValue', { ...props.modelValue, [field]: value });
  emit('clear-error', field);
}

function onArchivedToggle(next) {
  // Editing: the archive is its own reviewed operation, so the checkbox is a
  // request, not a value change. Creating: there are no projects yet, so there
  // is nothing to preview and the flag is plain form state.
  if (props.editing) {
    emit('request-archive');
    return;
  }
  update('is_archived', next);
}

function errorFor(field) {
  const value = props.errors[field];
  if (Array.isArray(value)) {
    return value.find((message) => typeof message === 'string' && message.trim()) || '';
  }
  return typeof value === 'string' ? value : '';
}
</script>

<template>
  <div :class="dense ? 'space-y-3' : 'space-y-4'">
    <BaseFormRow :cols="2" :gap="dense ? 3 : 4">
      <BaseFormField
        v-slot="{ invalid, errorId }"
        label="Nombre"
        required
        required-message="Escribe el nombre del cliente."
        :error="errorFor('name')"
        :size="dense ? 'sm' : 'md'"
      >
        <BaseInput
          :model-value="modelValue.name"
          type="text"
          required
          :error="invalid"
          :aria-describedby="errorId"
          :size="dense ? 'sm' : 'md'"
          :data-testid="`${testidPrefix}-name`"
          @update:model-value="update('name', $event)"
        />
      </BaseFormField>
      <BaseFormField v-slot="{ invalid, errorId }" label="Email" :error="errorFor('email')" :size="dense ? 'sm' : 'md'">
        <BaseInput
          :model-value="modelValue.email"
          type="email"
          :error="invalid"
          :aria-describedby="errorId"
          :size="dense ? 'sm' : 'md'"
          :data-testid="`${testidPrefix}-email`"
          @update:model-value="update('email', $event)"
        />
      </BaseFormField>
      <BaseFormField v-slot="{ invalid, errorId }" label="Teléfono" :error="errorFor('phone')" :size="dense ? 'sm' : 'md'">
        <BaseInput
          :model-value="modelValue.phone"
          type="tel"
          :error="invalid"
          :aria-describedby="errorId"
          :size="dense ? 'sm' : 'md'"
          :data-testid="`${testidPrefix}-phone`"
          @update:model-value="update('phone', $event)"
        />
      </BaseFormField>
      <BaseFormField v-slot="{ invalid, errorId }" label="Empresa" :error="errorFor('company')" :size="dense ? 'sm' : 'md'">
        <BaseInput
          :model-value="modelValue.company"
          type="text"
          :error="invalid"
          :aria-describedby="errorId"
          :size="dense ? 'sm' : 'md'"
          :data-testid="`${testidPrefix}-company`"
          @update:model-value="update('company', $event)"
        />
      </BaseFormField>
    </BaseFormRow>

    <!-- The type and number are one legal identity, shared with billing. -->
    <BaseFormRow>
      <BaseFormField label="Tipo de identificación" :size="dense ? 'sm' : 'md'">
        <BaseSelect
          :model-value="identificationType"
          :options="identificationOptions"
          :size="dense ? 'sm' : 'md'"
          :data-testid="`${testidPrefix}-identification-type`"
          @update:model-value="update('identification_type', $event)"
        />
      </BaseFormField>
      <BaseFormField v-slot="{ invalid, errorId }" label="Número de identificación" :error="errorFor(identificationField)" :size="dense ? 'sm' : 'md'">
        <BaseInput
          :model-value="modelValue[identificationField]"
          type="text"
          :error="invalid"
          :aria-describedby="errorId"
          :size="dense ? 'sm' : 'md'"
          placeholder="Para cuentas de cobro"
          :maxlength="identificationType === 'CC' ? 20 : 32"
          :data-testid="`${testidPrefix}-${identificationField}`"
          @update:model-value="update(identificationField, $event)"
        />
      </BaseFormField>
    </BaseFormRow>
    <BaseFormRow>
      <BaseFormField v-slot="{ invalid, errorId }" label="Dirección" :error="errorFor('address')" :size="dense ? 'sm' : 'md'">
        <BaseInput
          :model-value="modelValue.address"
          :maxlength="512"
          :error="invalid"
          :aria-describedby="errorId"
          :size="dense ? 'sm' : 'md'"
          :data-testid="`${testidPrefix}-address`"
          @update:model-value="update('address', $event)"
        />
      </BaseFormField>
      <BaseFormField v-slot="{ invalid, errorId }" label="Código de facturación" :error="errorFor('billing_code')" :size="dense ? 'sm' : 'md'">
        <BaseInput
          :model-value="modelValue.billing_code"
          type="text"
          :error="invalid"
          :aria-describedby="errorId"
          :size="dense ? 'sm' : 'md'"
          :maxlength="BILLING_CODE_MAX_LENGTH"
          class="uppercase"
          placeholder="Ej: G&M (numeración PA-G&M-001)"
          :data-testid="`${testidPrefix}-billing-code`"
          @update:model-value="update('billing_code', $event)"
        />
      </BaseFormField>
    </BaseFormRow>

    <!-- Lifecycle. Last on purpose: it is not part of the client's identity,
         it is what the panel does with it. -->
    <BaseFormField
      v-if="showArchived"
      label="Estado"
      :size="dense ? 'sm' : 'md'"
    >
      <label class="flex items-start gap-2 text-sm text-text-default">
        <input
          type="checkbox"
          class="mt-0.5 h-4 w-4 rounded border-input-border text-primary"
          :checked="Boolean(modelValue.is_archived)"
          :data-testid="`${testidPrefix}-archived`"
          @change="onArchivedToggle($event.target.checked)"
        >
        <span>
          Archivado
          <span class="block text-xs text-text-subtle">
            {{
              editing
                ? 'Se revisa el impacto sobre sus proyectos antes de aplicarlo.'
                : 'Queda fuera de las listas activas y de los buscadores.'
            }}
          </span>
        </span>
      </label>
    </BaseFormField>
  </div>
</template>
