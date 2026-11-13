<script setup>
import { ref, watch } from 'vue';
import EntityHistoryPanel from './EntityHistoryPanel.vue';
import DocumentHistoryPanel from './DocumentHistoryPanel.vue';
const props = defineProps({ entityType: { type: String, required: true }, objectId: { type: [String, Number], default: null } });
const active = ref('detail');
const tabs = [{ id: 'detail', label: 'Detalle' }, { id: 'history', label: 'Historial' }];
watch(() => props.objectId, () => { active.value = 'detail'; });
</script>
<template>
  <div class="min-w-0 space-y-4">
    <BaseTabs v-if="objectId" v-model="active" :tabs="tabs" data-testid="entity-history-tabs" />
    <div v-show="active === 'detail'"><slot /></div>
    <template v-if="objectId && active === 'history'">
      <DocumentHistoryPanel v-if="entityType === 'document'" :object-id="objectId" />
      <EntityHistoryPanel v-else :entity-type="entityType" :object-id="objectId" />
    </template>
  </div>
</template>
