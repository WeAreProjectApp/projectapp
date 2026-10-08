<template>
  <WaiterProduct />
</template>

<script setup>
import WaiterProduct from '~/components/pages/WaiterProduct.vue'
import { useWebPageJsonLd } from '~/composables/useSeoJsonLd'

useSeoHead('waiter')

const { locale } = useI18n()
const isEn = computed(() => locale.value.startsWith('en'))

useWebPageJsonLd({
  name: 'Waiter',
  description: isEn.value
    ? 'Waiter is ProjectApp’s point of sale for restaurants, with a digital menu and an assistant that serves customers on WhatsApp.'
    : 'Waiter es el punto de venta de ProjectApp para restaurantes, con menú digital y un asistente que atiende por WhatsApp.',
  url: `/${locale.value}/waiter`,
})
</script>
