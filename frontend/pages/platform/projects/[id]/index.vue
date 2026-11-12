<template>
  <ProjectShell>
    <section v-if="project" class="space-y-8">
      <!-- KPIs -->
      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div class="rounded-2xl border border-border-default bg-surface p-4">
          <p class="text-xs uppercase tracking-wider text-text-muted">Progreso</p>
          <p class="mt-2 text-2xl font-semibold text-text-default">{{ project.progress ?? 0 }}%</p>
        </div>
        <div v-if="features.enabled('platform.bugs')" class="rounded-2xl border border-border-default bg-surface p-4">
          <p class="text-xs uppercase tracking-wider text-text-muted">Bugs abiertos</p>
          <p class="mt-2 text-2xl font-semibold" :class="(project.bugs_open_count || 0) > 0 ? 'text-red-600' : 'text-text-default'">
            {{ project.bugs_open_count ?? 0 }}
          </p>
        </div>
        <div v-if="features.enabled('platform.change_requests')" class="rounded-2xl border border-border-default bg-surface p-4">
          <p class="text-xs uppercase tracking-wider text-text-muted">Solicitudes pendientes</p>
          <p class="mt-2 text-2xl font-semibold" :class="(project.changes_pending_count || 0) > 0 ? 'text-amber-600' : 'text-text-default'">
            {{ project.changes_pending_count ?? 0 }}
          </p>
        </div>
        <div class="rounded-2xl border border-border-default bg-surface p-4">
          <p class="text-xs uppercase tracking-wider text-text-muted">Próximo pago de hosting</p>
          <p class="mt-2 text-2xl font-semibold text-text-default">
            {{ project.next_hosting_payment ? formatCurrency(project.next_hosting_payment.amount) : '—' }}
          </p>
          <p v-if="project.next_hosting_payment?.date" class="text-xs text-text-muted">
            {{ formatDate(project.next_hosting_payment.date) }}
            <span v-if="project.next_hosting_payment.plan" class="ml-1">· {{ planLabel(project.next_hosting_payment.plan) }}</span>
          </p>
        </div>
      </div>

      <!-- Phases -->
      <PhaseList
        :project-id="project.id"
        :phases="phases"
        @add-phase="onAddPhase"
        @changed="loadPhases"
      />

      <!-- Actions -->
      <div v-if="authStore.isAdmin" class="rounded-2xl border border-border-default bg-surface p-6">
        <h2 class="text-base font-medium text-text-default">Acciones</h2>
        <p class="mt-1 text-xs text-text-muted">
          Edita los datos descriptivos aquí. Los estados y sus consecuencias se administran en la ficha comercial.
        </p>
        <div class="mt-3 flex flex-wrap gap-2">
          <BaseButton variant="secondary" size="md" @click="openEditModal">
            Editar
          </BaseButton>
          <BaseButton variant="secondary" size="md" @click="openPanelLifecycle">
            {{ t('projectAccess.commercialRecord.changeState') }}
          </BaseButton>
        </div>
      </div>

      <PhaseSelectorModal
        v-if="project"
        :visible="showAddPhase"
        mode="add"
        :project-id="project.id"
        :client-id="project.client_id"
        @close="showAddPhase = false"
        @phases-added="onPhasesAdded"
      />

      <!-- Edit project modal -->
      <Teleport to="body">
        <Transition name="modal-overlay">
          <div
            v-if="isEditOpen"
            role="dialog"
            aria-modal="true"
            aria-labelledby="platform-project-editor-title"
            class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4 backdrop-blur-sm"
            @click.self="isEditOpen = false"
          >
            <Transition name="modal-content" appear>
              <div
                v-if="isEditOpen"
                ref="editDialogRef"
                role="dialog"
                aria-modal="true"
                :aria-labelledby="editTitleId"
                tabindex="-1"
                class="w-full max-w-md rounded-3xl border border-border-default bg-surface p-6 shadow-2xl focus:outline-none focus:ring-2 focus:ring-focus-ring sm:p-8"
              >
                <h2 :id="editTitleId" class="mb-5 text-lg font-bold text-text-default">Editar proyecto</h2>
                <form class="space-y-4" @submit.prevent="handleEditSubmit">
                  <div>
                    <label class="mb-1.5 block text-xs font-medium text-esmerald/70 dark:text-white/70">Nombre <span class="text-red-400">*</span></label>
                    <input v-model="editForm.name" type="text" required class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition focus:border-border-default dark:bg-surface-muted dark:text-white" />
                  </div>
                  <div>
                    <label class="mb-1.5 block text-xs font-medium text-esmerald/70 dark:text-white/70">Descripción</label>
                    <textarea v-model="editForm.description" rows="3" class="w-full resize-none rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition focus:border-border-default dark:bg-surface-muted dark:text-white" />
                  </div>
                  <p v-if="editError" class="rounded-xl border border-red-500/30 bg-red-500/5 px-3 py-2 text-xs text-red-600 dark:text-red-400">{{ editError }}</p>
                  <div class="flex justify-end gap-3 pt-2">
                    <BaseButton variant="ghost" size="md" @click="isEditOpen = false">Cancelar</BaseButton>
                    <BaseButton variant="accent" size="md" type="submit" :disabled="!editForm.name.trim() || projectsStore.isUpdating">
                      {{ projectsStore.isUpdating ? 'Guardando…' : 'Guardar cambios' }}
                    </BaseButton>
                  </div>
                </form>
              </div>
            </Transition>
          </div>
        </Transition>
      </Teleport>
    </section>
    <div v-else class="px-6 py-12 text-center text-text-muted">Cargando proyecto…</div>
  </ProjectShell>
</template>

<script setup>
import { usePlatformFeaturesStore } from '~/stores/platform-features'
const features = usePlatformFeaturesStore()
import { computed, onMounted, reactive, ref, useId, watch } from 'vue'
import { useFocusTrap } from '~/composables/useFocusTrap'
import { usePlatformAuthStore } from '~/stores/platform-auth'
import { usePlatformProjectsStore } from '~/stores/platform-projects'
import { formatDate as formatDateUtil } from '~/utils/formatDate'
import ProjectShell from '~/components/platform/projects/ProjectShell.vue'
import PhaseList from '~/components/platform/projects/PhaseList.vue'
import PhaseSelectorModal from '~/components/platform/projects/PhaseSelectorModal.vue'

definePageMeta({
  middleware: ['platform-auth'],
  layout: 'platform',
})

const authStore = usePlatformAuthStore()
const projectsStore = usePlatformProjectsStore()
const localePath = useLocalePath()
const { t } = useI18n()

const project = computed(() => projectsStore.currentProject)
const phases = ref([])
const showAddPhase = ref(false)

const isEditOpen = ref(false)
const editDialogRef = ref(null)
const editTitleId = `${useId()}-edit-title`
useFocusTrap(editDialogRef, { active: isEditOpen })
const editForm = reactive({ name: '', description: '' })
const editError = ref('')

async function loadPhases() {
  if (!project.value) return
  phases.value = await projectsStore.loadPhases(project.value.id)
}

onMounted(loadPhases)
watch(() => project.value?.id, loadPhases)

function onAddPhase() { showAddPhase.value = true }
async function onPhasesAdded() {
  await loadPhases()
  showAddPhase.value = false
}

function formatDate(iso) {
  return formatDateUtil(iso, { fallback: '' })
}

function formatCurrency(value) {
  const n = Number(value || 0)
  if (!n) return '—'
  return new Intl.NumberFormat('es-CO', {
    style: 'currency', currency: 'COP', maximumFractionDigits: 0,
  }).format(n)
}

function planLabel(plan) {
  const map = {
    monthly: 'Mensual (histórico)',
    quarterly: 'Trimestral',
    semiannual: 'Semestral',
    nine_month: 'Cada 9 meses',
    annual: 'Anual (histórico)',
  }
  return map[plan] || plan
}

function openEditModal() {
  editForm.name = project.value?.name || ''
  editForm.description = project.value?.description || ''
  editError.value = ''
  isEditOpen.value = true
}

async function handleEditSubmit() {
  if (!editForm.name.trim()) return
  editError.value = ''
  const result = await projectsStore.updateProject(project.value.id, { ...editForm })
  if (result.success) {
    isEditOpen.value = false
  } else {
    editError.value = result.message
  }
}

function openPanelLifecycle() {
  window.open(localePath({ path: '/panel/projects', query: { highlight: project.value.id } }), '_blank')
}
</script>
