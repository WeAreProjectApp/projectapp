<script setup>
import ClientAutocomplete from '~/components/ui/ClientAutocomplete.vue';
import ProjectSelect from '~/components/accounting/ProjectSelect.vue';
import BaseButton from '~/components/base/BaseButton.vue';
import BaseFormField from '~/components/base/BaseFormField.vue';
import BaseFormRow from '~/components/base/BaseFormRow.vue';
import BaseFormRowAction from '~/components/base/BaseFormRowAction.vue';

/**
 * Filtros de asociación del listado de documentos.
 *
 * Cliente y proyecto son ejes independientes (sin cascada — eso es cosa del
 * formulario), cada uno con su recorte «sin asociar» como chip excluyente del
 * valor elegido: los documentos sueltos son un corte de primera clase, no un
 * residuo. Los valores viajan como los ejes del composable de URL:
 * null (sin filtro) | 'none' | id.
 */
const props = defineProps({
  client: { type: [Number, String], default: null },
  project: { type: [Number, String], default: null },
  /** Label del cliente activo, para rehidratar el autocomplete en deep links. */
  clientLabel: { type: String, default: '' },
});

const emit = defineEmits(['update:client', 'update:project']);

function onClientSelect(clientRow) {
  emit('update:client', clientRow ? clientRow.id : null);
}

function toggleClientNone() {
  emit('update:client', props.client === 'none' ? null : 'none');
}

function onProjectPicked(value) {
  emit('update:project', value ?? null);
}

function toggleProjectNone() {
  emit('update:project', props.project === 'none' ? null : 'none');
}
</script>

<template>
  <div class="grid grid-cols-1 gap-4 panel-landscape:grid-cols-2">
    <BaseFormRow layout="field-action">
      <BaseFormField label="Cliente">
        <ClientAutocomplete
          :key="client === 'none' ? 'client-none' : 'client-picker'"
          :model-value="typeof client === 'number' ? client : null"
          :initial-label="clientLabel"
          :show-linked-hint="false"
          placeholder="Filtrar por cliente..."
          test-id="documents-filter-client"
          @select="onClientSelect"
        />
      </BaseFormField>
      <BaseFormRowAction>
        <BaseButton
          type="button"
          :variant="client === 'none' ? 'primary' : 'secondary'"
          class="w-full panel-portrait:w-auto"
          data-testid="documents-filter-client-none"
          :aria-pressed="client === 'none'"
          @click="toggleClientNone"
        >
          Sin cliente
        </BaseButton>
      </BaseFormRowAction>
    </BaseFormRow>

    <BaseFormRow layout="field-action">
      <ProjectSelect
        :model-value="typeof project === 'number' ? project : null"
        :client-profile-id="typeof client === 'number' ? client : null"
        :allow-no-client="true"
        :allow-create="false"
        :show-hint="false"
        testid="documents-filter-project"
        @update:model-value="onProjectPicked"
      />
      <BaseFormRowAction>
        <BaseButton
          type="button"
          :variant="project === 'none' ? 'primary' : 'secondary'"
          class="w-full panel-portrait:w-auto"
          data-testid="documents-filter-project-none"
          :aria-pressed="project === 'none'"
          @click="toggleProjectNone"
        >
          Sin proyecto
        </BaseButton>
      </BaseFormRowAction>
    </BaseFormRow>

    <p
      class="col-span-full -mt-2 text-xs text-text-muted"
      data-testid="documents-filter-project-help"
    >
      Opcional. Filtra por un proyecto o elige «Sin proyecto».
    </p>
  </div>
</template>
