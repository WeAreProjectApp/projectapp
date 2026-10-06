<script setup>
import { computed, ref, watch } from 'vue';
import { useI18n } from '#imports';
import { create_request, get_request } from '~/stores/services/request_http';

const props = defineProps({ open: Boolean, client: { type: Object, default: null } });
const emit = defineEmits(['close']);
const { t, locale } = useI18n();
const contexts = ref([]);
const activeContext = ref(null);
const activeCategory = ref(null);
const records = ref([]);
const count = ref(0);
const page = ref(1);
const loading = ref(false);
const error = ref('');
const revealed = ref({});
let version = 0;
const root = computed(() => `proposals/client-profiles/${props.client?.id}/retained-project-data/`);
const label = (category) => locale.value.startsWith('en') ? category.label_en || category.label : category.label;
const description = (category) => locale.value.startsWith('en') ? category.description_en || category.description : category.description;

async function loadContexts() {
  const current = ++version;
  loading.value = true;
  error.value = '';
  try {
    const response = await get_request(root.value);
    if (current === version) contexts.value = response.data.contexts;
  } catch {
    if (current === version) error.value = t('projectAccess.retention.loadError');
  } finally {
    if (current === version) loading.value = false;
  }
}

async function selectCategory(context, category, nextPage = 1) {
  const current = ++version;
  activeContext.value = context;
  activeCategory.value = category;
  revealed.value = {};
  loading.value = true;
  error.value = '';
  try {
    const response = await get_request(`${root.value}?context=${context.id}&category=${encodeURIComponent(category.key)}&page=${nextPage}`);
    if (current !== version) return;
    records.value = response.data.results;
    count.value = response.data.count;
    page.value = nextPage;
  } catch {
    if (current === version) error.value = t('projectAccess.retention.loadError');
  } finally {
    if (current === version) loading.value = false;
  }
}

function showContexts() {
  version += 1;
  activeContext.value = null;
  activeCategory.value = null;
  records.value = [];
  revealed.value = {};
  loading.value = false;
  error.value = '';
}

async function reveal(record) {
  if (revealed.value[record.id] !== undefined) {
    delete revealed.value[record.id];
    return;
  }
  const current = version;
  try {
    const response = await create_request(`${root.value}${activeContext.value.id}/${encodeURIComponent(record.key)}/${encodeURIComponent(record.id)}/reveal/`, {});
    if (current === version && props.open) revealed.value[record.id] = response.data.value;
  } catch {
    if (current === version) error.value = t('projectAccess.retention.revealError');
  }
}

function visibleFields(record) {
  return Object.entries(record.fields).filter(([key, value]) => value !== null && value !== '' && t(`projectAccess.retention.fields.${key}`) !== `projectAccess.retention.fields.${key}`);
}

const displayValue = (value) => typeof value === 'boolean' ? t(value ? 'projectAccess.retention.yes' : 'projectAccess.retention.no') : Array.isArray(value) ? value.join('\n') : String(value);

watch([() => props.open, () => props.client?.id], ([open]) => {
  showContexts();
  contexts.value = [];
  if (open && props.client?.id) loadContexts();
}, { immediate: true });
</script>

<template>
  <BaseModal :model-value="open" kind="form" @close="emit('close')">
    <div class="space-y-4 p-6" data-testid="client-retained-project-data">
      <h2 class="text-lg font-semibold text-text-default">{{ $t('projectAccess.retention.title') }}</h2>
      <p class="text-sm text-text-muted">{{ client?.company || client?.full_name || client?.name }} · {{ $t('projectAccess.retention.hint') }}</p>
      <BaseButton v-if="activeCategory" variant="secondary" size="sm" @click="showContexts">{{ $t('projectAccess.retention.back') }}</BaseButton>
      <BaseAlert v-if="error" variant="danger" role="alert">{{ error }}</BaseAlert>
      <p v-if="loading" role="status" class="text-sm text-text-muted">{{ $t('projectAccess.retention.loading') }}</p>
      <template v-else-if="!activeCategory">
        <p v-if="!contexts.length" class="text-sm text-text-muted" data-testid="retained-data-empty">{{ $t('projectAccess.retention.empty') }}</p>
        <section v-for="context in contexts" :key="context.id" class="space-y-3 rounded-lg border border-border-muted p-4">
          <h3 class="break-words font-semibold text-text-default">{{ context.project_name }}</h3>
          <p class="text-xs text-text-subtle">{{ $t('projectAccess.retention.originalProject') }}</p>
          <div class="flex flex-wrap gap-2">
            <BaseButton v-for="category in context.categories" :key="category.key" variant="secondary" size="sm" :data-testid="`retained-category-${category.key}`" @click="selectCategory(context, category)">{{ label(category) }} ({{ category.count }})</BaseButton>
          </div>
        </section>
      </template>
      <template v-else>
        <h3 class="font-semibold text-text-default">{{ activeContext.project_name }} · {{ label(activeCategory) }}</h3>
        <p class="text-sm text-text-muted">{{ description(activeCategory) }}</p>
        <article v-for="record in records" :key="record.id" class="space-y-3 rounded-lg border border-border-muted p-4" data-testid="retained-data-record">
          <h4 class="break-words font-semibold text-text-default">{{ record.title }}</h4>
          <dl class="space-y-2 text-sm">
            <div v-for="[key, value] in visibleFields(record)" :key="key">
              <dt class="text-text-subtle">{{ $t(`projectAccess.retention.fields.${key}`) }}</dt>
              <dd class="whitespace-pre-wrap break-words text-text-default">{{ displayValue(value) }}</dd>
            </div>
          </dl>
          <div class="flex flex-wrap gap-3">
            <a v-for="file in record.files" :key="file.field" :href="`/api/${root}${activeContext.id}/${encodeURIComponent(record.key)}/${encodeURIComponent(record.id)}/files/${file.field}/`" class="break-words text-sm text-primary underline">{{ $t('projectAccess.retention.download') }} {{ file.name }}</a>
          </div>
          <BaseButton v-if="record.can_reveal" variant="secondary" size="sm" @click="reveal(record)">{{ $t(revealed[record.id] === undefined ? 'projectAccess.retention.reveal' : 'projectAccess.retention.hide') }}</BaseButton>
          <p v-if="revealed[record.id] !== undefined" class="whitespace-pre-wrap break-words text-sm text-text-default">{{ revealed[record.id] }}</p>
        </article>
        <div class="flex flex-wrap items-center justify-between gap-3">
          <BaseButton v-if="page > 1" variant="secondary" size="sm" @click="selectCategory(activeContext, activeCategory, page - 1)">{{ $t('projectAccess.retention.previous') }}</BaseButton>
          <p class="text-sm text-text-muted">{{ page }} / {{ Math.max(1, Math.ceil(count / 50)) }}</p>
          <BaseButton v-if="page * 50 < count" variant="secondary" size="sm" @click="selectCategory(activeContext, activeCategory, page + 1)">{{ $t('projectAccess.retention.next') }}</BaseButton>
        </div>
      </template>
    </div>
    <template #footer>
      <BaseModalActions><BaseButton variant="secondary" @click="emit('close')">{{ $t('projectAccess.retention.close') }}</BaseButton></BaseModalActions>
    </template>
  </BaseModal>
</template>
