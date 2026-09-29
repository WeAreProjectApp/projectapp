<template>
  <BaseModal :model-value="modelValue" kind="detail" padding="md" :close-on-backdrop="!mutating" :close-on-esc="!mutating" @update:model-value="close">
    <div class="space-y-5 px-6 py-5" data-testid="secure-link-detail">
      <div v-if="loading" class="py-10 text-center text-sm text-text-subtle">Cargando enlace…</div>
      <template v-else-if="detail">
        <div class="flex min-w-0 flex-col gap-2 panel-portrait:flex-row panel-portrait:items-start panel-portrait:justify-between">
          <div class="min-w-0">
            <h3 class="text-lg font-bold text-text-default [overflow-wrap:anywhere]">{{ detail.title }}</h3>
            <p class="text-sm text-text-muted">{{ detail.type_label }} · {{ detail.origin_label }}</p>
          </div>
          <SecureLinkStatusBadge :status="detail.lifecycle_status || detail.status" :team-only="detail.team_only" />
        </div>

        <dl class="grid grid-cols-1 gap-3 text-sm panel-portrait:grid-cols-2">
          <div v-if="!detail.team_only">
            <dt class="text-text-subtle">{{ t('secureLinks.panel.sentAt') }}</dt>
            <dd class="text-text-default">{{ detail.sent_at ? formatDateTime(detail.sent_at) : t('secureLinks.panel.notSent') }}</dd>
          </div>
          <div v-if="detail.team_only">
            <dt class="text-text-subtle">Enviado por</dt>
            <dd class="text-text-default [overflow-wrap:anywhere]">
              {{ detail.creator_name || 'Cliente' }}<template v-if="detail.creator_email"> · {{ detail.creator_email }}</template>
            </dd>
          </div>
          <div v-else>
            <dt class="text-text-subtle">Creado por</dt>
            <dd class="text-text-default">{{ detail.created_by_name || detail.origin_label }}</dd>
          </div>
          <div>
            <dt class="text-text-subtle">Cliente / proyecto</dt>
            <dd class="text-text-default [overflow-wrap:anywhere]">{{ association || 'Sin asociar' }}</dd>
          </div>
          <div>
            <dt class="text-text-subtle">Vence</dt>
            <dd class="text-text-default">{{ formatDateTime(detail.expires_at) }}</dd>
          </div>
          <div>
            <dt class="text-text-subtle">Abierto</dt>
            <dd class="text-text-default">{{ detail.consumed_at ? formatDateTime(detail.consumed_at) : 'Todavía no' }}</dd>
          </div>
        </dl>

        <BaseAlert v-if="detail.team_only" variant="info">
          Lo creó un cliente desde la página pública: sólo el equipo puede abrirlo.
        </BaseAlert>

        <fieldset :disabled="Boolean(busy)" class="flex flex-wrap gap-2">
          <BaseButton v-if="!detail.team_only && detail.status === 'active' && !detail.sent_at" variant="secondary" size="sm" :loading="busy === 'sent'" :title="t('secureLinks.panel.manualSendHint')" data-testid="secure-link-mark-sent" @click="markSent">
            <BaseActionIcon action="complete" />
            {{ t('secureLinks.panel.markSent') }}
          </BaseButton>
          <BaseButton variant="secondary" size="sm" :loading="busy === 'content'" data-testid="secure-link-view-content" @click="toggleContent">
            <BaseActionIcon :action="content ? 'hide' : 'view'" />
            {{ content ? 'Ocultar contenido' : 'Ver contenido' }}
          </BaseButton>
          <BaseButton variant="secondary" size="sm" :loading="busy === 'url'" data-testid="secure-link-copy-url" @click="copyUrl">
            <BaseActionIcon action="copy" />
            {{ urlFeedback.label || 'Copiar enlace' }}
          </BaseButton>
          <BaseButton variant="ghost" size="sm" data-testid="secure-link-edit" @click="editMetadata">
            <BaseActionIcon action="edit" />
            Editar
          </BaseButton>
          <BaseButton variant="ghost" size="sm" data-testid="secure-link-edit-content" @click="editContent">
            <BaseActionIcon action="edit" />
            {{ t('secureLinks.panel.editContent') }}
          </BaseButton>
          <BaseButton
            v-if="detail.status === 'active'"
            variant="danger-ghost"
            size="sm"
            :loading="busy === 'revoke'"
            data-testid="secure-link-revoke"
            @click="revoke"
          >
            <BaseActionIcon action="deactivate" />
            Revocar
          </BaseButton>
        </fieldset>

        <SecureLinkContent v-if="content" :fields="content.fields" />

        <fieldset :disabled="Boolean(busy)" v-if="detail.status !== 'active'" class="space-y-3 rounded-xl border border-border-default p-4" data-testid="secure-link-reactivate">
          <h4 class="text-sm font-semibold text-text-default">Reactivar enlace</h4>
          <p class="text-sm text-text-muted">
            El mismo enlace se podrá abrir una vez más. Si sospechas que otra persona lo abrió, genera uno nuevo y el anterior dejará de funcionar.
          </p>
          <BaseSegmented v-model="reactivation.validityDays" :options="validityOptions" size="sm" data-testid="secure-link-reactivate-validity" />
          <BaseCheckbox v-model="reactivation.rotate" data-testid="secure-link-reactivate-rotate">
            Generar un enlace nuevo e invalidar el anterior
          </BaseCheckbox>
          <BaseButton variant="primary" size="sm" :loading="busy === 'reactivate'" data-testid="secure-link-reactivate-submit" @click="reactivate">
            <BaseActionIcon action="activate" />
            Reactivar
          </BaseButton>
        </fieldset>

        <section>
          <h4 class="mb-2 text-sm font-semibold text-text-default">Historial</h4>
          <ol class="space-y-2" data-testid="secure-link-events">
            <li v-for="event in detail.events" :key="event.id" class="text-sm text-text-muted [overflow-wrap:anywhere]">
              <span class="text-text-default">{{ event.kind_label }}</span>
              · {{ formatDateTime(event.created_at) }}
              <template v-if="event.actor_name"> · {{ event.actor_name }}</template>
              <template v-if="event.ip_address"> · IP {{ event.ip_address }}</template>
              <template v-if="event.details?.reason"> · {{ reasonLabel(event.details.reason) }}</template>
            </li>
          </ol>
        </section>

      </template>
      <BaseAlert v-if="error" variant="danger" data-testid="secure-link-detail-error">
        {{ error }}
        <BaseButton v-if="!detail" variant="link" size="sm" data-testid="secure-link-detail-retry" @click="load">{{ t('secureLinks.retry') }}</BaseButton>
      </BaseAlert>
    </div>
  </BaseModal>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue';
import BaseActionIcon from '~/components/base/BaseActionIcon.vue';
import BaseAlert from '~/components/base/BaseAlert.vue';
import BaseButton from '~/components/base/BaseButton.vue';
import BaseCheckbox from '~/components/base/BaseCheckbox.vue';
import BaseModal from '~/components/base/BaseModal.vue';
import BaseSegmented from '~/components/base/BaseSegmented.vue';
import SecureLinkContent from '~/components/secureLinks/SecureLinkContent.vue';
import SecureLinkStatusBadge from '~/components/secureLinks/SecureLinkStatusBadge.vue';
import { useClipboardFeedback } from '~/composables/useClipboardFeedback';
import { useSecureLinksStore } from '~/stores/secure_links';
import { formatDateTime } from '~/utils/formatDate';

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  linkId: { type: Number, default: null },
});
const emit = defineEmits(['update:modelValue', 'edit', 'changed']);
const store = useSecureLinksStore();
const { t } = useI18n();
const loading = ref(false);
const mutating = computed(() => ['revoke', 'reactivate', 'sent'].includes(busy.value));
const clipboard = useClipboardFeedback();

const detail = ref(null);
const content = ref(null);
const busy = ref('');
const error = ref('');
const reactivation = reactive({ validityDays: 7, rotate: false });
const validityOptions = [1, 3, 7, 30].map((days) => ({ value: days, label: days === 1 ? '1 día' : `${days} días` }));
const urlFeedback = computed(() => clipboard.feedbackFor('secure-link-url'));
const association = computed(() => [detail.value?.client_name, detail.value?.project_name].filter(Boolean).join(' · '));

const REASONS = { consumed: 'ya estaba usado', expired: 'estaba vencido', revoked: 'estaba revocado', staff_only: 'sin sesión del equipo' };

function reasonLabel(reason) {
  return REASONS[reason] || reason;
}

let generation = 0;
function current(version) {
  return version === generation && props.modelValue;
}

async function load() {
  const version = generation;
  loading.value = !detail.value;
  error.value = '';
  const result = await store.fetchDetail(props.linkId);
  if (!current(version)) return;
  loading.value = false;
  if (result.success) detail.value = result.data;
  else error.value = result.error.status === 404
    ? t('secureLinks.panel.deleted') : result.error.message;
}

watch(() => [props.modelValue, props.linkId], ([open]) => {
  generation += 1;
  content.value = null;
  detail.value = null;
  error.value = '';
  busy.value = '';
  loading.value = false;
  reactivation.validityDays = 7;
  reactivation.rotate = false;
  if (open && props.linkId) load();
}, { immediate: true, flush: 'sync' });

onBeforeUnmount(() => { generation += 1; content.value = null; });

function close(value) {
  if (mutating.value) return;
  if (!value) { generation += 1; content.value = null; }
  emit('update:modelValue', value);
}

async function runAction(name, request, completed) {
  if (busy.value) return;
  const version = generation;
  busy.value = name;
  error.value = '';
  const result = await request();
  if (!current(version)) return;
  if (!result.success) error.value = result.error.message;
  else await completed(result);
  if (current(version)) busy.value = '';
}

function toggleContent() {
  if (content.value) { content.value = null; return; }
  return runAction('content', () => store.viewContent(props.linkId), async (result) => {
    content.value = result.data;
    await load();
  });
}

async function copyText(text) {
  await clipboard.copyText({
    key: 'secure-link-url',
    text,
    successLabel: 'Enlace copiado',
    errorLabel: 'No se pudo copiar',
  });
}

function copyUrl() {
  return runAction('url', () => store.fetchLinkUrl(props.linkId), (result) => copyText(result.url));
}

function editMetadata() {
  emit('edit', { link: detail.value, fields: null });
}

function editContent() {
  return runAction('content', () => store.viewContent(props.linkId), (result) => {
    const values = Object.fromEntries(result.data.fields.map((field) => [field.key, field.value]));
    emit('edit', { link: detail.value, fields: values });
  });
}

function revoke() {
  return runAction('revoke', () => store.revokeLink(props.linkId), async () => {
    emit('changed');
    await load();
  });
}

function markSent() {
  return runAction('sent', () => store.markSent(props.linkId), async () => {
    emit('changed');
    await load();
  });
}

function reactivate() {
  return runAction('reactivate', () => store.reactivateLink(props.linkId, {
    validity_days: reactivation.validityDays,
    rotate: reactivation.rotate,
  }), async (result) => {
    if (reactivation.rotate && result.data.url) await copyText(result.data.url);
    emit('changed', result.data);
    await load();
  });
}
</script>
