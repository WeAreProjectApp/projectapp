<template>
  <div id="platform-documents">
    <!-- Header -->
    <div class="mb-8" data-enter>
      <h1 class="text-2xl font-bold text-text-default sm:text-3xl">Mis documentos</h1>
      <p class="mt-1 text-sm text-text-muted">
        Revisa, descarga y firma los documentos de tu proyecto.
      </p>
    </div>

    <!-- Loading -->
    <div v-if="store.isLoading" class="py-20 text-center" data-enter>
      <div class="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-border-default border-t-esmerald dark:border-t-lemon" />
      <p class="mt-4 text-sm text-text-muted">Cargando documentos...</p>
    </div>

    <template v-else>
      <!-- Email validation card -->
      <section
        v-if="!store.emailVerified"
        class="mb-6 rounded-3xl border border-border-default bg-surface p-6"
        data-enter
      >
        <div class="flex items-start gap-3">
          <span class="mt-0.5 inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary-soft text-text-brand">
            <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l9 6 9-6M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>
          </span>
          <div class="flex-1">
            <h2 class="text-base font-semibold text-text-default">Valida tu correo electrónico</h2>
            <p class="mt-1 text-sm text-text-muted">
              Para poder firmar necesitas confirmar tu correo
              <span class="font-medium text-text-default">{{ store.email }}</span>.
            </p>

            <div v-if="feedback" class="mt-4 rounded-2xl border px-4 py-3 text-sm" :class="feedbackOk ? 'border-emerald-500/20 bg-primary-soft text-text-brand' : 'border-red-500/20 bg-red-50 text-red-600'">
              {{ feedback }}
            </div>

            <div v-if="!codeSent" class="mt-4">
              <BaseButton variant="primary" size="md" :disabled="store.isSending" @click="sendCode">
                {{ store.isSending ? 'Enviando...' : 'Enviar código' }}
              </BaseButton>
            </div>

            <form v-else class="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center" @submit.prevent="confirmCode">
              <input
                v-model="code"
                type="text"
                inputmode="numeric"
                maxlength="6"
                placeholder="Código de 6 dígitos"
                class="w-full max-w-[200px] rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-center text-lg font-semibold tracking-[0.3em] text-text-default outline-none transition focus:border-border-default focus:ring-1 focus:ring-esmerald/10"
              >
              <BaseButton variant="primary" size="md" type="submit" :disabled="store.isSending || code.length !== 6">
                {{ store.isSending ? 'Validando...' : 'Validar correo' }}
              </BaseButton>
              <BaseButton unstyled
                type="button"
                class="text-sm font-medium text-text-muted transition hover:text-text-default disabled:opacity-50"
                :disabled="store.isSending"
                @click="sendCode"
              >
                Reenviar
              </BaseButton>
            </form>
          </div>
        </div>
      </section>

      <div
        v-else
        class="mb-6 flex items-center gap-2 rounded-2xl border border-emerald-500/20 bg-primary-soft px-4 py-3 text-sm text-text-brand"
        data-enter
      >
        <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
        Tu correo está validado. Ya puedes firmar tus documentos.
      </div>

      <!-- Empty -->
      <div
        v-if="store.documents.length === 0"
        class="rounded-3xl border border-dashed border-border-default py-20 text-center"
        data-enter
      >
        <p class="text-sm font-medium text-text-default">Todavía no tienes documentos disponibles.</p>
        <p class="mt-1 text-xs text-text-muted">Tu administrador publicará aquí tus documentos.</p>
      </div>

      <!-- Main signable document -->
      <section
        v-if="store.signableDocument"
        class="mb-6 rounded-3xl border border-border-default bg-surface p-6"
        data-enter
      >
        <div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <span class="text-xs font-semibold uppercase tracking-wider text-text-muted">Documento principal</span>
            <h2 class="mt-1 text-lg font-semibold text-text-default">{{ store.signableDocument.title }}</h2>
            <p v-if="store.signableDocument.signed" class="mt-1 flex items-center gap-1.5 text-sm text-text-brand">
              <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
              Firmado el {{ formatDate(store.signableDocument.signed_at) }}
            </p>
          </div>
          <div class="flex flex-wrap gap-2">
            <BaseButton variant="secondary" size="md" @click="download(store.signableDocument)">
              Descargar PDF
            </BaseButton>
            <BaseButton variant="primary" size="md" v-if="!store.signableDocument.signed" :disabled="!store.emailVerified" :title="store.emailVerified ? '' : 'Valida tu correo primero'" @click="openSign">
              Aceptar y firmar
            </BaseButton>
          </div>
        </div>
      </section>

      <!-- Annexes -->
      <section v-if="store.annexes.length" data-enter>
        <h3 class="mb-3 text-sm font-semibold uppercase tracking-wider text-text-muted">Anexos</h3>
        <ul class="space-y-2">
          <li
            v-for="doc in store.annexes"
            :key="doc.uuid"
            class="flex items-center justify-between rounded-2xl border border-border-default bg-surface px-4 py-3"
          >
            <span class="text-sm font-medium text-text-default">{{ doc.title }}</span>
            <BaseButton variant="secondary" size="sm" @click="download(doc)">
              Descargar
            </BaseButton>
          </li>
        </ul>
      </section>
    </template>

    <!-- Sign confirmation modal -->
    <div
      v-if="signModalOpen"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      @click.self="signModalOpen = false"
    >
      <div class="w-full max-w-md rounded-3xl border border-border-default bg-surface p-6 shadow-2xl">
        <h3 class="text-lg font-semibold text-text-default">Firmar documento</h3>
        <p class="mt-2 text-sm text-text-muted">
          Vas a aceptar y firmar <span class="font-medium text-text-default">{{ store.signableDocument?.title }}</span>.
          Esta acción queda registrada con tu nombre, fecha y hora.
        </p>

        <label class="mt-4 flex items-start gap-2 text-sm text-text-default">
          <input v-model="accepted" type="checkbox" class="mt-0.5 h-4 w-4 rounded border-border-default">
          <span>He leído el documento y acepto sus términos.</span>
        </label>

        <div v-if="feedback && !feedbackOk" class="mt-4 rounded-2xl border border-red-500/20 bg-red-50 px-4 py-3 text-sm text-red-600">
          {{ feedback }}
        </div>

        <div class="mt-6 flex justify-end gap-2">
          <BaseButton variant="ghost" size="md" @click="signModalOpen = false">
            Cancelar
          </BaseButton>
          <BaseButton variant="primary" size="md" :disabled="!accepted || store.isSigning" @click="confirmSign">
            {{ store.isSigning ? 'Firmando...' : 'Confirmar firma' }}
          </BaseButton>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { usePlatformDocumentsStore } from '~/stores/platform-documents'
import { formatDateTime } from '~/utils/formatDate'

definePageMeta({
  layout: 'platform',
  middleware: ['platform-auth'],
  platformRole: 'client',
})

useHead({ title: 'Mis documentos — ProjectApp' })

const store = usePlatformDocumentsStore()

const code = ref('')
const codeSent = ref(false)
const feedback = ref('')
const feedbackOk = ref(false)
const signModalOpen = ref(false)
const accepted = ref(false)

await store.fetchDocuments()

function formatDate(value) {
  return formatDateTime(value, { fallback: '' })
}

async function sendCode() {
  feedback.value = ''
  const result = await store.requestEmailVerification()
  feedbackOk.value = result.success
  feedback.value = result.success ? 'Te enviamos un código a tu correo.' : result.message
  if (result.success) codeSent.value = true
}

async function confirmCode() {
  feedback.value = ''
  const result = await store.confirmEmailVerification(code.value)
  if (result.success) {
    feedbackOk.value = true
    feedback.value = 'Correo validado correctamente.'
    code.value = ''
    codeSent.value = false
  } else {
    feedbackOk.value = false
    feedback.value = result.message
  }
}

function openSign() {
  accepted.value = false
  feedback.value = ''
  signModalOpen.value = true
}

async function confirmSign() {
  feedback.value = ''
  const doc = store.signableDocument
  if (!doc) return
  const result = await store.signDocument(doc.uuid)
  if (result.success) {
    signModalOpen.value = false
  } else {
    feedbackOk.value = false
    feedback.value = result.message
  }
}

async function download(doc) {
  await store.downloadPdf(doc.uuid, doc.title)
}
</script>
