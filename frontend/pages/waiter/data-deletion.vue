<template>
  <LegalDocument :doc="messages.data_deletion || {}" :back-label="messages.back_to_waiter" />
</template>

<script setup>
import LegalDocument from '~/components/legal/LegalDocument.vue'
import { useMessages } from '~/composables/useMessages'

const { messages } = useMessages('waiter')
const { t } = useI18n()

useSeoHead('waiterDataDeletion')
// useSeoHead only fills the meta tags; set the document title as well.
useHead({ title: () => t('meta.waiterDataDeletion.title') })
</script>
