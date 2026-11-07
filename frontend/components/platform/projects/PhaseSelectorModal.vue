<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="visible" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4 backdrop-blur-sm" @click.self="$emit('close')">
        <div
          ref="dialogRef"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="titleId"
          tabindex="-1"
          class="w-full max-w-3xl rounded-3xl border border-border-default bg-surface p-6 shadow-2xl focus:outline-none focus:ring-2 focus:ring-focus-ring"
        >
          <div class="mb-6 flex items-center justify-between">
            <h2 :id="titleId" class="text-xl font-medium text-text-default">{{ mode === 'create' ? 'Nuevo proyecto' : 'Agregar fases' }}</h2>
            <BaseButton variant="ghost" icon-only size="sm" aria-label="Cerrar" @click="$emit('close')">×</BaseButton>
          </div>

          <!-- Step 1: client -->
          <section v-if="step === 1">
            <p class="mb-3 text-sm text-green-light">Selecciona el cliente.</p>
            <select
              data-testid="client-select"
              v-model.number="selectedClientId"
              class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-3 py-2 text-text-default"
            >
              <option :value="0" disabled>Elegir…</option>
              <option v-for="c in clients" :key="c.user_id" :value="c.user_id">
                {{ c.first_name }} {{ c.last_name }} · {{ c.email }}
              </option>
            </select>
            <p v-if="error" class="mt-2 text-sm text-red-600">{{ error }}</p>
          </section>

          <!-- Step 2: proposals -->
          <section v-if="step === 2" class="grid gap-4 sm:grid-cols-2">
            <div>
              <p class="mb-2 text-xs uppercase tracking-wider text-green-light/70">Propuestas elegibles</p>
              <div v-if="!eligibleProposals.length" class="rounded-xl border border-border-default p-4 text-sm text-green-light/60">
                No hay propuestas elegibles (firmadas / aprobadas, sin proyecto activo) para este cliente.
              </div>
              <label v-for="p in eligibleProposals" :key="p.id" class="mb-2 flex items-center gap-2 rounded-xl border border-border-default px-3 py-2">
                <input type="checkbox" :value="p.id" v-model="selectedIds" />
                <span class="text-text-default">{{ p.title }}</span>
                <span class="ml-auto text-xs text-green-light/60">${{ p.total_amount }}</span>
              </label>
            </div>
            <div>
              <p class="mb-2 text-xs uppercase tracking-wider text-green-light/70">Fases (en orden)</p>
              <div v-if="!selectedProposals.length" class="rounded-xl border border-dashed border-border-default p-4 text-sm text-green-light/60">
                Selecciona al menos una propuesta.
              </div>
              <div
                v-for="(p, idx) in selectedProposals" :key="p.id"
                class="mb-2 flex items-center gap-2 rounded-xl border border-border-muted bg-surface-muted/30 px-3 py-2"
              >
                <span class="font-medium text-text-default">{{ idx + 1 }}. {{ p.title }}</span>
                <span class="ml-auto text-xs text-green-light/60">${{ p.total_amount }}</span>
                <BaseButton variant="danger-ghost" icon-only size="sm" aria-label="Quitar fase" @click="unselect(p.id)">×</BaseButton>
              </div>
            </div>
            <p v-if="error" class="text-sm text-red-600 sm:col-span-2">{{ error }}</p>
          </section>

          <!-- Step 3: confirm -->
          <section v-if="step === 3">
            <p class="text-sm text-green-light">Confirmación</p>
            <p class="mt-2 text-base font-medium text-text-default">Cliente: {{ selectedClient?.email || '—' }}</p>
            <ol class="mt-3 space-y-1">
              <li v-for="(p, idx) in selectedProposals" :key="p.id" class="text-sm text-text-default">
                {{ idx + 1 }}. {{ p.title }} — ${{ p.total_amount }}
              </li>
            </ol>
            <p class="mt-3 text-sm font-medium text-text-default">Total: ${{ totalAmount }}</p>
          </section>

          <!-- Footer -->
          <div class="mt-6 flex justify-between">
            <BaseButton v-if="step > 1 && mode === 'create'" variant="secondary" @click="step--">Atrás</BaseButton>
            <span v-else></span>
            <BaseButton
              v-if="(mode === 'create' && step < 3) || (mode === 'add' && step < 2)"
              data-testid="next-step"
              variant="primary"
              @click="nextStep"
            >Siguiente</BaseButton>
            <BaseButton
              v-else
              variant="primary"
              :loading="busy"
              :disabled="!selectedProposals.length"
              @click="submit"
            >{{ mode === 'create' ? 'Crear proyecto' : 'Agregar fases' }}</BaseButton>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, ref, toRef, useId, watch } from 'vue'
import { useFocusTrap } from '~/composables/useFocusTrap'
import { usePlatformProjectsStore } from '~/stores/platform-projects'

const props = defineProps({
  visible: { type: Boolean, default: false },
  mode: { type: String, default: 'create' },
  clients: { type: Array, default: () => [] },
  projectId: { type: [Number, String], default: null },
  clientId: { type: Number, default: 0 },
})
const emit = defineEmits(['close', 'created', 'phases-added'])

const dialogRef = ref(null)
const titleId = `${useId()}-title`
useFocusTrap(dialogRef, { active: toRef(props, 'visible') })

const store = usePlatformProjectsStore()
const step = ref(1)
const selectedClientId = ref(props.clientId || 0)
const eligibleProposals = ref([])
const selectedIds = ref([])
const error = ref('')
const busy = ref(false)

const selectedClient = computed(() => props.clients.find((c) => c.user_id === selectedClientId.value))
const selectedProposals = computed(() =>
  selectedIds.value.map((id) => eligibleProposals.value.find((p) => p.id === id)).filter(Boolean),
)
const totalAmount = computed(() => selectedProposals.value.reduce((acc, p) => acc + Number(p.total_amount || 0), 0))

watch(() => props.visible, async (v) => {
  if (v) {
    step.value = props.mode === 'add' ? 2 : 1
    selectedClientId.value = props.clientId || 0
    selectedIds.value = []
    eligibleProposals.value = []
    error.value = ''
    if (props.mode === 'add' && props.clientId) await loadEligible()
  }
})

async function loadEligible() {
  if (!selectedClientId.value) return
  eligibleProposals.value = await store.loadEligibleProposals(selectedClientId.value)
}

async function nextStep() {
  error.value = ''
  if (step.value === 1) {
    if (!selectedClientId.value) { error.value = 'Selecciona un cliente'; return }
    await loadEligible()
  }
  if (step.value === 2 && !selectedIds.value.length) {
    error.value = 'Selecciona al menos una propuesta'; return
  }
  step.value++
}

function unselect(id) {
  selectedIds.value = selectedIds.value.filter((x) => x !== id)
}

async function submit() {
  busy.value = true
  try {
    if (props.mode === 'create') {
      // Create project bare then append phases (backend currently doesn't accept inline phases).
      const created = await store.createProject({
        name: selectedProposals.value[0]?.title || 'Nuevo proyecto',
        client_id: selectedClientId.value,
      })
      const newProject = created?.project || created
      if (newProject?.id) {
        for (let i = 0; i < selectedProposals.value.length; i++) {
          await store.addPhase(newProject.id, selectedProposals.value[i].id, i + 1)
        }
      }
      emit('created', newProject)
    } else {
      for (let i = 0; i < selectedProposals.value.length; i++) {
        await store.addPhase(props.projectId, selectedProposals.value[i].id, null)
      }
      emit('phases-added')
    }
    emit('close')
  } finally {
    busy.value = false
  }
}
</script>
