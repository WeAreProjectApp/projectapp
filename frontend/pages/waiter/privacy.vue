<template>
  <LegalDocument :doc="messages.privacy || {}" :back-label="messages.back_to_waiter" />
</template>

<script setup>
import LegalDocument from '~/components/legal/LegalDocument.vue'
import { useMessages } from '~/composables/useMessages'

const { messages } = useMessages('waiter')

useSeoHead('waiterPrivacy')
</script>
