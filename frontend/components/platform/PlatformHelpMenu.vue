<template>
  <div v-if="auth.isClient && (availableTours.length || (store.videoEnabled && help?.videoAvailable.value))" class="relative">
    <BaseButton unstyled type="button" data-tour="help" data-testid="platform-help-trigger" :aria-label="t('platformHelp.help')" :aria-expanded="open" :title="t('platformHelp.help')"
      class="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-text-brand hover:bg-primary-soft dark:text-white"
      @click="open = !open">
      <span aria-hidden="true">?</span><span v-if="!collapsed">{{ t('platformHelp.help') }}</span>
    </BaseButton>
    <div v-if="open" class="mt-2 space-y-2 rounded-xl border border-border-default bg-surface p-3 text-sm dark:bg-primary" data-testid="platform-help-menu">
      <BaseButton v-for="tour in availableTours" :key="tour.id" :data-testid="`platform-help-tour-${tour.slug}`" variant="ghost" class="w-full text-left" @click="launch(tour.id)">
        {{ tour.content[`title_${language}`] }}
      </BaseButton>
      <BaseButton v-if="store.videoEnabled && help?.videoAvailable.value" variant="ghost" class="w-full" @click="requestVideo">{{ t('platformHelp.video') }}</BaseButton>
    </div>
  </div>
</template>

<script setup>
import { computed, inject, ref } from 'vue'
import { usePlatformAuthStore } from '~/stores/platform-auth'
import { usePlatformHelpStore } from '~/stores/platform-help'
defineProps({ collapsed: { type: Boolean, default: false } })
const auth = usePlatformAuthStore()
const store = usePlatformHelpStore()
const help = inject('platformHelp', null)
const { t, locale } = useI18n()
const open = ref(false)
const language = computed(() => locale.value.startsWith('en') ? 'en' : 'es')
const availableTours = computed(() => store.tourEnabled ? store.tours.filter((tour) => tour.context !== 'voice' || help?.voiceVisible.value) : [])
function launch(id) { open.value = false; help?.start(id) }
function requestVideo() { open.value = false; help?.openVideo() }
</script>
