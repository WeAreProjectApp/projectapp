<template>
  <LegalDocument :doc="messages.terms || {}" :back-label="messages.back_to_waiter" />
</template>

<script setup>
import LegalDocument from '~/components/legal/LegalDocument.vue'
import { useMessages } from '~/composables/useMessages'

const { messages } = useMessages('waiter')

useSeoHead('waiterTerms')
</script>
