<template>
  <ContactSuccess />
</template>

<script setup>
import ContactSuccess from '~/components/pages/ContactSuccess.vue'

const { localeProperties } = useI18n()
useHead({ htmlAttrs: { lang: () => localeProperties.value.language } })
</script>
