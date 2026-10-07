<template>
    <!-- Client picker (autocomplete + snapshot fields) -->
    <div class="space-y-4 border border-border-muted rounded-xl p-4 bg-surface-raised">
      <div>
        <label class="block text-sm font-medium text-text-default mb-1">Cliente</label>
        <ClientAutocomplete
          v-model="form.client_id"
          :initial-label="form.client_name"
          :disabled="Boolean(proposal.linked_project)"
          disabled-reason="Cambia el propietario desde Proyectos para conservar las relaciones."
          test-id="proposal-edit-client-autocomplete"
          allow-create
          @select="emit('client-selected', $event)"
          @create-new="emit('create-inline-client', $event)"
        />
        <p v-if="!proposal.linked_project" class="text-xs text-text-subtle mt-1">
          Busca un cliente existente o escribe uno nuevo. Si no eliges email, se generará uno temporal y las automatizaciones quedarán pausadas.
        </p>
      </div>

      <!-- Placeholder warning badge -->
      <div
        v-if="proposal?.client?.is_email_placeholder"
        class="flex items-start gap-2 px-3 py-2 rounded-lg bg-warning-soft border border-warning-strong/30"
      >
        <span class="text-warning-strong text-xs font-medium">
          📧 Email pendiente — las automatizaciones de correo están pausadas para este cliente.
        </span>
      </div>

      <!-- Snapshot fields (still editable, but clearly subordinated) -->
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label class="block text-xs font-medium text-text-muted mb-1">Nombre snapshot</label>
          <BaseInput
            id="edit-client-name"
            v-model="form.client_name"
            type="text"
            required
            size="sm"
            data-testid="edit-client-name"
          />
        </div>
        <div>
          <label class="block text-xs font-medium text-text-muted mb-1">Email del cliente</label>
          <BaseInput
            id="edit-client-email"
            v-model="form.client_email"
            type="email"
            size="sm"
            data-testid="edit-client-email"
          />
        </div>
        <div>
          <label class="block text-xs font-medium text-text-muted mb-1">Teléfono / WhatsApp</label>
          <BaseInput
            id="edit-client-phone"
            v-model="form.client_phone"
            type="tel"
            size="sm"
            placeholder="+57 300 123 4567"
            data-testid="edit-client-phone"
          />
        </div>
        <div>
          <label class="block text-xs font-medium text-text-muted mb-1">Empresa</label>
          <BaseInput
            id="edit-client-company"
            v-model="form.client_company"
            type="text"
            size="sm"
            placeholder="Acme Inc."
            data-testid="edit-client-company"
          />
        </div>
      </div>

    </div>

</template>

<script setup>
import ClientAutocomplete from '~/components/ui/ClientAutocomplete.vue';
const props = defineProps({ proposal: { type: Object, required: true }, form: { type: Object, required: true } });
const emit = defineEmits(['client-selected', 'create-inline-client']);
const form = props.form;
</script>
