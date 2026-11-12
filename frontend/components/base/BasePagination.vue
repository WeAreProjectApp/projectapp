<template>
  <nav
    v-if="totalPages > 1 || alwaysShow"
    class="flex flex-col gap-3 py-3 sm:grid sm:grid-cols-[1fr_auto_1fr] sm:items-center"
    :aria-label="ariaLabel"
  >
    <p v-if="totalItems > 0" class="text-xs text-text-muted text-center sm:text-left sm:col-start-1">
      Mostrando <span class="font-medium text-text-default">{{ rangeFrom }}</span>–<span class="font-medium text-text-default">{{ rangeTo }}</span>
      de <span class="font-medium text-text-default">{{ totalItems }}</span>
    </p>

    <div class="flex items-center justify-center gap-2 sm:col-start-2">
      <BaseActionButton
        action="previous"
        class="inline-flex items-center justify-center w-9 h-9 rounded-lg border border-border-default bg-surface text-text-muted hover:bg-surface-raised hover:text-text-default disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        :disabled="currentPage <= 1"
        disabled-reason="Ya estás en la primera página."
        :label="prevLabel"
        @click="$emit('prev')"
      />

      <div class="hidden sm:flex items-center gap-1">
        <template v-for="(p, idx) in pageList" :key="idx">
          <button
            v-if="p !== '…'"
            type="button"
            class="inline-flex items-center justify-center min-w-[36px] h-9 px-2 rounded-lg text-sm font-medium transition-colors"
            :class="p === currentPage
              ? 'bg-primary text-on-primary dark:bg-accent dark:text-on-accent'
              : 'border border-border-default bg-surface text-text-muted hover:bg-surface-raised hover:text-text-default'"
            :aria-current="p === currentPage ? 'page' : undefined"
            @click="$emit('go', p)"
          >
            {{ p }}
          </button>
          <span v-else class="px-1 text-xs text-text-subtle select-none">…</span>
        </template>
      </div>

      <span class="sm:hidden text-sm font-medium text-text-default">
        {{ currentPage }} / {{ totalPages }}
      </span>

      <BaseActionButton
        action="next"
        class="inline-flex items-center justify-center w-9 h-9 rounded-lg border border-border-default bg-surface text-text-muted hover:bg-surface-raised hover:text-text-default disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        :disabled="currentPage >= totalPages"
        disabled-reason="Ya estás en la última página."
        :label="nextLabel"
        @click="$emit('next')"
      />
    </div>
  </nav>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  currentPage: { type: Number, required: true },
  totalPages: { type: Number, required: true },
  totalItems: { type: Number, default: 0 },
  rangeFrom: { type: Number, default: 0 },
  rangeTo: { type: Number, default: 0 },
  ariaLabel: { type: String, default: 'Paginación' },
  prevLabel: { type: String, default: 'Página anterior' },
  nextLabel: { type: String, default: 'Página siguiente' },
  alwaysShow: { type: Boolean, default: false },
});

defineEmits(['prev', 'next', 'go']);

const pageList = computed(() => {
  const total = props.totalPages;
  const current = props.currentPage;
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);

  const pages = [1];
  const start = Math.max(2, current - 1);
  const end = Math.min(total - 1, current + 1);
  if (start > 2) pages.push('…');
  for (let i = start; i <= end; i++) pages.push(i);
  if (end < total - 1) pages.push('…');
  pages.push(total);
  return pages;
});
</script>
