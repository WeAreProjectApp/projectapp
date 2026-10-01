<script setup>
import { ref, watch } from 'vue'
import BasePageShell from '~/components/base/BasePageShell.vue'
import CollectionAccountContextEditor from '~/components/accounting/billing/CollectionAccountContextEditor.vue'
import { get_request } from '~/stores/services/request_http'
const route = useRoute()
const account = ref(null), error = ref(''), loading = ref(false)
let sequence = 0
async function load() {
  const request = ++sequence
  account.value = null; error.value = ''; loading.value = true
  try { const result = await get_request(`accounting/collection-accounts/${route.params.id}/`); if (request === sequence) account.value = result.data }
  catch (err) { if (request === sequence) error.value = err.response?.data?.detail || 'No se pudo cargar la cuenta.' }
  finally { if (request === sequence) loading.value = false }
}
watch(() => route.params.id, load, { immediate: true })
definePageMeta({ layout: 'admin', middleware: ['admin-auth', 'superuser-only'] })
</script>
<template><BasePageShell><h1 class="mb-4 text-2xl font-semibold">Asociación de cuenta de cobro</h1><p v-if="loading" role="status">Cargando cuenta…</p><div v-if="error" role="alert"><p>{{ error }}</p><button class="mt-2 text-text-brand" @click="load">Reintentar</button></div><template v-if="account"><p class="mb-4">{{ account.public_number }} · {{ account.total }} {{ account.currency }} · {{ account.commercial_status }}</p><CollectionAccountContextEditor v-if="account.project_id" :account-id="account.id" :project-id="account.project_id" /><p v-else>La cuenta no tiene proyecto; conserva su flujo contable existente.</p></template></BasePageShell></template>
