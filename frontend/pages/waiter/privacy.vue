<template>
  <LegalDocument :doc="messages.privacy || {}" :back-label="messages.back_to_waiter" />
</template>

<script setup>
import LegalDocument from '~/components/legal/LegalDocument.vue'
import { useMessages } from '~/composables/useMessages'

const { messages } = useMessages('waiter')
const { t } = useI18n()

useSeoHead('waiterPrivacy')
// useSeoHead only fills the meta tags; set the document title as well.
useHead({ title: () => t('meta.waiterPrivacy.title') })
</script>
