<script setup>
import BaseButton from '~/components/base/BaseButton.vue'
import { onBeforeUnmount, onMounted, watch } from 'vue'
import { usePlatformClientAccessStore } from '~/stores/platform-client-access'
import ProjectClientCredential from './ProjectClientCredential.vue'
const props = defineProps({ api: { type: Object, required: true }, projectId: { type: Number, required: true }, canReveal: { type: Boolean, default: true } })
const { t } = useI18n()
const store = usePlatformClientAccessStore()
const load = () => store.load(props.projectId, props.api)
watch(() => props.projectId, load, { immediate: true })
onMounted(() => window.addEventListener('focus', load))
onBeforeUnmount(() => { window.removeEventListener('focus', load); store.clear() })
</script>

<template>
  <section class="space-y-5 text-text-default" data-testid="project-client-access">
    <h2 class="text-lg font-semibold">{{ t('projectClientAccess.title') }}</h2>
    <p v-if="store.loading" role="status">{{ t('projectClientAccess.loading') }}</p>
    <p v-else-if="!store.environments.length">{{ t('projectClientAccess.empty') }}</p>
    <p v-if="store.error" role="alert">{{ store.error }}</p>
    <BaseButton variant="secondary" size="md" textPolicy="wrap" class="min-h-11" type="button" @click="load">{{ t('projectClientAccess.retry') }}</BaseButton>
    <article v-for="environment in store.environments" :key="`${projectId}-${environment.environment}`" class="space-y-4 rounded-xl border border-border-default p-4" :data-testid="`client-access-${environment.environment}`">
      <h3 class="font-medium">{{ t(`projectClientAccess.${environment.environment}`) }}</h3>
      <div v-for="field in ['site_url', 'admin_url'].filter((name) => environment[name])" :key="field" class="space-y-1">
        <p class="text-sm text-text-subtle">{{ t(`projectClientAccess.${field}`) }}</p>
        <a :href="environment[field]" target="_blank" rel="noopener noreferrer" class="inline-flex min-h-11 items-center break-all text-text-brand underline">{{ environment[field] }}</a>
      </div>
      <template v-if="canReveal">
        <ProjectClientCredential v-for="field in environment.credential_actions || []" :key="field" :api="api" :project-id="projectId" :environment="environment.environment" :field="field" @denied="load" />
      </template>
    </article>
  </section>
</template>
