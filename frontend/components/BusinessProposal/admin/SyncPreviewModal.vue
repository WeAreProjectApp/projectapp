<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm p-0 panel-portrait:p-4"
      @click.self="$emit('cancel')"
    >
      <div class="flex h-dvh w-full flex-col overflow-hidden bg-surface shadow-overlay panel-portrait:h-auto panel-portrait:max-h-[90dvh] panel-portrait:max-w-2xl panel-portrait:rounded-2xl">
        <div class="min-h-0 flex-1 overflow-y-auto" data-modal-body>
          <!-- Header -->
          <div class="px-6 py-5 border-b border-border-muted">
            <h2 class="text-base font-semibold text-text-default">
              Vista previa de sincronización
            </h2>
            <p class="mt-1 text-sm text-text-muted">
              Al confirmar, estos cambios se aplicarán al proyecto vinculado.
            </p>
            <div class="mt-3 flex flex-col gap-1">
              <div class="flex items-center gap-2 text-sm text-text-default">
                <span class="font-medium">Proyecto:</span>
                <span>{{ projectInfo?.name }}</span>
                <span class="text-text-subtle">—</span>
                <span class="text-text-muted">{{ projectInfo?.client_email }}</span>
              </div>
              <div class="flex items-center gap-2 text-sm text-text-default">
                <span class="font-medium">Entregable:</span>
                <span>{{ deliverableInfo?.title }}</span>
              </div>
            </div>
          </div>

          <!-- Body -->
          <div class="px-6 py-5 max-h-[55vh] overflow-y-auto space-y-5">
            <!-- Empty state -->
            <div
              v-if="isEmpty"
              class="flex items-center justify-center py-8 text-sm text-text-subtle"
            >
              Sin cambios estructurales detectados.
            </div>

            <!-- Nuevos -->
            <div v-if="hasNew">
              <h3 class="flex items-center gap-2 text-sm font-semibold text-green-700 mb-2">
                <span class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-green-100 text-green-700 text-xs font-bold">+</span>
                Nuevos ({{ newCount }})
              </h3>
              <ul class="space-y-1.5">
                <li
                  v-for="item in diff.epics.to_create"
                  :key="'ec-' + item.epicKey"
                  class="flex items-start gap-2 text-sm"
                >
                  <span class="mt-0.5 shrink-0 inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-green-50 text-green-700 border border-green-200">
                    Módulo
                  </span>
                  <span class="text-text-default">{{ item.title }}</span>
                  <span class="text-text-subtle text-xs ml-auto">{{ item.epicKey }}</span>
                </li>
                <li
                  v-for="item in diff.requirements.to_create"
                  :key="'rc-' + item.flowKey"
                  class="flex items-start gap-2 text-sm"
                >
                  <span class="mt-0.5 shrink-0 inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-green-50 text-green-700 border border-green-200">
                    Req.
                  </span>
                  <span class="text-text-default">{{ item.title }}</span>
                  <span class="text-text-subtle text-xs ml-auto">{{ item.flowKey }}</span>
                </li>
              </ul>
            </div>

            <!-- Actualizados -->
            <div v-if="hasUpdated">
              <h3 class="flex items-center gap-2 text-sm font-semibold text-amber-700 mb-2">
                <span class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-amber-100 text-amber-700 text-xs font-bold">~</span>
                Actualizados ({{ updatedCount }})
              </h3>
              <ul class="space-y-1.5">
                <li
                  v-for="item in diff.epics.to_update"
                  :key="'eu-' + item.epicKey"
                  class="flex items-start gap-2 text-sm"
                >
                  <span class="mt-0.5 shrink-0 inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
                    Módulo
                  </span>
                  <span class="text-text-default">{{ item.title }}</span>
                  <span class="text-text-subtle text-xs ml-1">({{ item.changed_fields.join(', ') }})</span>
                </li>
                <li
                  v-for="item in diff.requirements.to_update"
                  :key="'ru-' + item.flowKey"
                  class="flex items-start gap-2 text-sm"
                >
                  <span class="mt-0.5 shrink-0 inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
                    Req.
                  </span>
                  <span class="text-text-default">{{ item.title }}</span>
                  <span class="text-text-subtle text-xs ml-1">({{ item.changed_fields.join(', ') }})</span>
                </li>
              </ul>
            </div>

            <!-- Se eliminarán -->
            <div v-if="hasDeleted">
              <h3 class="flex items-center gap-2 text-sm font-semibold text-red-700 mb-2">
                <span class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-red-100 text-red-700 text-xs font-bold">−</span>
                Se archivarán ({{ deletedCount }})
              </h3>
              <ul class="space-y-1.5">
                <li
                  v-for="item in diff.epics.to_delete"
                  :key="'ed-' + item.epicKey"
                  class="flex items-start gap-2 text-sm"
                >
                  <span class="mt-0.5 shrink-0 inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-red-50 text-red-700 border border-red-200">
                    Módulo
                  </span>
                  <span class="text-text-default line-through">{{ item.title }}</span>
                  <span class="text-text-subtle text-xs ml-auto">{{ item.epicKey }}</span>
                </li>
                <li
                  v-for="item in diff.requirements.to_delete"
                  :key="'rd-' + item.flowKey"
                  class="flex items-start gap-2 text-sm"
                >
                  <span class="mt-0.5 shrink-0 inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-red-50 text-red-700 border border-red-200">
                    Req.
                  </span>
                  <span class="text-text-default line-through">{{ item.title }}</span>
                  <span class="text-text-subtle text-xs ml-auto">{{ item.flowKey }}</span>
                </li>
              </ul>
            </div>
          </div>

          <!-- Footer -->
        </div>
        <BaseModalActions class="pb-[max(1rem,env(safe-area-inset-bottom))]">
          <BaseButton
            variant="ghost"
            :disabled="isApplying"
            @click="$emit('cancel')"
          >
            Cancelar
          </BaseButton>
          <BaseButton
            variant="primary"
            :loading="isApplying"
            @click="$emit('confirm')"
          >
            <BaseActionIcon v-if="!isApplying" action="approve" />
            {{ isApplying ? 'Aplicando...' : 'Confirmar y aplicar' }}
          </BaseButton>
        </BaseModalActions>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
const props = defineProps({
  visible: { type: Boolean, default: false },
  projectInfo: { type: Object, default: null },
  deliverableInfo: { type: Object, default: null },
  diff: { type: Object, default: null },
  isApplying: { type: Boolean, default: false },
})

defineEmits(['confirm', 'cancel'])

const newCount = computed(() => {
  if (!props.diff) return 0
  return (props.diff.epics?.to_create?.length ?? 0) + (props.diff.requirements?.to_create?.length ?? 0)
})

const updatedCount = computed(() => {
  if (!props.diff) return 0
  return (props.diff.epics?.to_update?.length ?? 0) + (props.diff.requirements?.to_update?.length ?? 0)
})

const deletedCount = computed(() => {
  if (!props.diff) return 0
  return (props.diff.epics?.to_delete?.length ?? 0) + (props.diff.requirements?.to_delete?.length ?? 0)
})

const hasNew = computed(() => newCount.value > 0)
const hasUpdated = computed(() => updatedCount.value > 0)
const hasDeleted = computed(() => deletedCount.value > 0)
const isEmpty = computed(() => !hasNew.value && !hasUpdated.value && !hasDeleted.value)
</script>
