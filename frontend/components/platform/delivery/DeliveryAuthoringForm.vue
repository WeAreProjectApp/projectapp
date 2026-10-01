<script setup>
import { computed, reactive } from 'vue'
import BaseAlert from '~/components/base/BaseAlert.vue'
import BaseCheckbox from '~/components/base/BaseCheckbox.vue'
import BaseFormField from '~/components/base/BaseFormField.vue'
import BaseInput from '~/components/base/BaseInput.vue'
import BaseSelect from '~/components/base/BaseSelect.vue'
import BaseTextarea from '~/components/base/BaseTextarea.vue'

const props = defineProps({
  entity: { type: String, required: true }, initial: { type: Object, default: () => ({}) },
  contracts: { type: Array, default: () => [] }, documents: { type: Array, default: () => [] },
  proposalDocuments: { type: Array, default: () => [] }, commercialPhases: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false }, error: { type: String, default: '' },
})
const emit = defineEmits(['submit', 'cancel'])
const { t } = useI18n()
const form = reactive({
  key: '', title: '', description: '', order: 0, contract_id: '', amendment_id: '', commercial_phase_id: '',
  document_id: '', proposal_document_id: '', client_visible: true, is_current: true,
  ...props.initial,
  guide: { role: '', environment: '', preparation: '', data: '', expected_result: '', failure_signals: '', ...props.initial.guide },
  stepsText: (props.initial.guide?.steps || []).join('\n'),
})
const fieldErrors = reactive({})
const contractOptions = computed(() => props.contracts.map((item) => ({ value: item.id, label: item.title })))
const amendmentOptions = computed(() => [{ value: '', label: t('platformDelivery.none') }, ...(props.contracts.find((contract) => String(contract.id) === String(form.contract_id))?.amendments || []).map((item) => ({ value: item.id, label: item.title }))])
const documentOptions = computed(() => [{ value: '', label: t('platformDelivery.none') }, ...props.documents.map((item) => ({ value: item.id, label: item.title }))])
const proposalOptions = computed(() => [{ value: '', label: t('platformDelivery.none') }, ...props.proposalDocuments.map((item) => ({ value: item.id, label: item.title }))])
const commercialOptions = computed(() => [{ value: '', label: t('platformDelivery.none') }, ...props.commercialPhases.map((item) => ({ value: item.id, label: item.proposal?.title || item.title }))])
const idOrNull = (value) => value ? Number(value) : null
const isContract = computed(() => ['contracts', 'amendments'].includes(props.entity))
function submit() {
  Object.keys(fieldErrors).forEach((key) => delete fieldErrors[key])
  for (const key of ['key', 'title']) if (!form[key]?.trim()) fieldErrors[key] = t('platformDelivery.fieldRequired')
  if (['amendments', 'scopes'].includes(props.entity) && !form.contract_id) fieldErrors.contract_id = t('platformDelivery.fieldRequired')
  if (!Number.isFinite(Number(form.order)) || Number(form.order) < 0) fieldErrors.order = t('platformDelivery.numericOrder')
  if (Object.keys(fieldErrors).length) return
  const payload = { key: form.key.trim(), title: form.title.trim() }
  if (!isContract.value) payload.description = form.description.trim()
  if (['phases', 'stages', 'requirements'].includes(props.entity)) payload.order = Number(form.order)
  if (isContract.value) {
    payload.document_id = idOrNull(form.document_id)
    payload.proposal_document_id = idOrNull(form.proposal_document_id)
    payload.client_visible = !!form.client_visible
  }
  if (props.entity === 'amendments') payload.contract_id = Number(form.contract_id)
  if (props.entity === 'scopes') Object.assign(payload, { contract_id: Number(form.contract_id), amendment_id: idOrNull(form.amendment_id), is_current: form.is_current })
  if (props.entity === 'phases') Object.assign(payload, { scope_id: form.scope_id, commercial_phase_id: idOrNull(form.commercial_phase_id) })
  if (props.entity === 'stages') payload.phase_id = form.phase_id
  if (props.entity === 'requirements') Object.assign(payload, {
    stage_id: form.stage_id,
    guide: { ...form.guide, steps: form.stepsText.split('\n').map((line) => line.trim()).filter(Boolean) },
  })
  emit('submit', payload)
}
</script>

<template>
  <form class="space-y-5" @submit.prevent="submit" data-testid="delivery-authoring-form">
    <BaseAlert v-if="error" variant="danger" role="alert">{{ error }}</BaseAlert>
    <BaseFormRow :cols="2">
      <BaseFormField :label="t('platformDelivery.key')" :hint="t('platformDelivery.keyHint')" :error="fieldErrors.key" for="delivery-author-key" required>
        <BaseInput id="delivery-author-key" v-model="form.key" :error="!!fieldErrors.key" data-testid="delivery-author-key" />
      </BaseFormField>
      <BaseFormField :label="t('platformDelivery.name')" :error="fieldErrors.title" for="delivery-author-title" required>
        <BaseInput id="delivery-author-title" v-model="form.title" :error="!!fieldErrors.title" data-testid="delivery-author-title" />
      </BaseFormField>
    </BaseFormRow>
    <BaseFormField v-if="!isContract" :label="t('platformDelivery.description')" for="delivery-author-description">
      <BaseTextarea id="delivery-author-description" v-model="form.description" :rows="3" />
    </BaseFormField>
    <BaseFormField v-if="['amendments', 'scopes'].includes(entity)" :label="t('platformDelivery.contract')" :error="fieldErrors.contract_id" for="delivery-author-contract" required>
      <BaseSelect id="delivery-author-contract" v-model="form.contract_id" :options="contractOptions" :placeholder="t('platformDelivery.select')" @update:model-value="form.amendment_id = ''" />
    </BaseFormField>
    <template v-if="entity === 'scopes'">
      <BaseFormField :label="t('platformDelivery.amendment')" for="delivery-author-amendment">
        <BaseSelect id="delivery-author-amendment" v-model="form.amendment_id" :options="amendmentOptions" />
      </BaseFormField>
      <BaseCheckbox v-model="form.is_current">{{ t('platformDelivery.isCurrent') }}</BaseCheckbox>
    </template>
    <template v-if="isContract">
      <BaseFormRow :cols="2" :help="t('platformDelivery.sourceHint')">
        <BaseFormField :label="t('platformDelivery.contractDocument')" for="delivery-author-document">
          <BaseSelect id="delivery-author-document" v-model="form.document_id" :options="documentOptions" @update:model-value="form.proposal_document_id = ''" />
        </BaseFormField>
        <BaseFormField :label="t('platformDelivery.proposalDocument')" for="delivery-author-proposal">
          <BaseSelect id="delivery-author-proposal" v-model="form.proposal_document_id" :options="proposalOptions" @update:model-value="form.document_id = ''" />
        </BaseFormField>
      </BaseFormRow>
      <BaseCheckbox v-model="form.client_visible">{{ t('platformDelivery.clientVisible') }}</BaseCheckbox>
    </template>
    <BaseFormField v-if="entity === 'phases'" :label="t('platformDelivery.commercialPhase')" :hint="t('platformDelivery.commercialHint')" for="delivery-author-commercial">
      <BaseSelect id="delivery-author-commercial" v-model="form.commercial_phase_id" :options="commercialOptions" />
    </BaseFormField>
    <BaseFormField v-if="['phases', 'stages', 'requirements'].includes(entity)" :label="t('platformDelivery.order')" :error="fieldErrors.order" for="delivery-author-order">
      <BaseInput id="delivery-author-order" v-model="form.order" type="number" min="0" />
    </BaseFormField>
    <template v-if="entity === 'requirements'">
      <h3 class="text-base font-semibold text-text-default">{{ t('platformDelivery.guide') }}</h3>
      <BaseFormRow :cols="2">
        <BaseFormField :label="t('platformDelivery.role')" for="delivery-author-role">
          <BaseInput id="delivery-author-role" v-model="form.guide.role" />
        </BaseFormField>
        <BaseFormField :label="t('platformDelivery.environment')" for="delivery-author-environment">
          <BaseInput id="delivery-author-environment" v-model="form.guide.environment" />
        </BaseFormField>
      </BaseFormRow>
      <BaseFormField v-for="[key, label] in [['preparation', 'preparation'], ['data', 'data'], ['expected_result', 'expected'], ['failure_signals', 'failures']]" :key="key" :label="t(`platformDelivery.${label}`)" :for="`delivery-author-${key}`">
        <BaseTextarea :id="`delivery-author-${key}`" v-model="form.guide[key]" :rows="3" />
      </BaseFormField>
      <BaseFormField :label="t('platformDelivery.steps')" :hint="t('platformDelivery.stepsHint')" for="delivery-author-steps">
        <BaseTextarea id="delivery-author-steps" v-model="form.stepsText" :rows="5" />
      </BaseFormField>
    </template>
    <BaseModalActions>
      <BaseButton variant="ghost" @click="emit('cancel')">{{ t('platformDelivery.cancel') }}</BaseButton>
      <BaseButton type="submit" :loading="loading" data-testid="delivery-authoring-save">{{ t('platformDelivery.save') }}</BaseButton>
    </BaseModalActions>
  </form>
</template>
