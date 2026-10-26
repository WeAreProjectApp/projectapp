<template>
  <div v-if="active" class="mb-4 rounded-lg border border-border-muted bg-surface p-3" data-testid="radar-destination-status">
    <p class="text-sm" :class="error ? 'text-danger-strong' : 'text-text-muted'" :role="error ? 'alert' : 'status'">{{ error || (changed ? text.changed : text.focused) }}</p>
    <BaseButton v-if="error" variant="secondary" size="sm" @click="checkRecord">{{ text.retry }}</BaseButton>
  </div>
</template>
<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import BaseButton from '~/components/base/BaseButton.vue';
import { get_request } from '~/stores/services/request_http';
import { useDashboardAttentionText } from '~/composables/useDashboardAttentionText';
import { useRadarFocus } from '~/composables/useRadarFocus';
const props = defineProps({ kind: { type: String, required: true }, id: { type: Number, required: true }, ready: Boolean, target: { type: String, required: true } });
const route = useRoute();
const text = useDashboardAttentionText();
const focus = useRadarFocus();
const active = computed(() => route.query.radar === '1');
const error = ref('');
const changed = ref(false);
let token = 0;
onBeforeUnmount(() => { token += 1; });
async function checkRecord() {
  const request = ++token;
  error.value = '';
  if (!active.value) return;
  try {
    const response = await get_request(`panel/dashboard/attention/${props.kind}/${props.id}/`);
    if (request === token) changed.value = !response.data.eligible;
  } catch (failure) {
    if (request !== token) return;
    error.value = failure.response?.status === 404 ? text.value.missing : failure.response?.status === 403 ? text.value.forbidden : text.value.detailError;
  }
}
watch(() => [active.value, props.id], checkRecord, { immediate: true });
watch(() => [active.value, props.ready, props.id], () => {
  if (active.value && props.ready) focus(props.target);
}, { immediate: true, flush: 'post' });
</script>
