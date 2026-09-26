<template>
  <div class="bg-surface rounded-xl border border-border-muted shadow-sm overflow-hidden mt-2">
    <p v-if="aliases.length === 0" class="px-5 py-6 text-sm text-text-subtle">
      Aún no hay alias aprendidos. Se crean al aprobar comercios en el chat.
    </p>
    <div v-else class="overflow-x-auto">
      <table class="statement-alias-table w-full">
        <thead>
          <tr class="border-b border-border-muted text-left">
            <th
              class="px-1.5 py-2 panel-landscape:w-14"
              aria-label="Acciones"
              data-testid="statement-alias-actions-header"
            />
            <th class="px-2.5 py-2 first:pl-4 last:pr-4 text-xs font-medium text-text-muted uppercase tracking-wider">Texto a mapear</th>
            <th class="px-2.5 py-2 first:pl-4 last:pr-4 text-xs font-medium text-text-muted uppercase tracking-wider">Comercio</th>
            <th class="px-2.5 py-2 first:pl-4 last:pr-4 text-xs font-medium text-text-muted uppercase tracking-wider">Categoría</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-border-muted">
          <tr
            v-for="alias in aliases"
            :key="alias.id"
            class="statement-alias-row h-9 transition-colors hover:bg-surface-raised"
            :data-testid="`statement-alias-${alias.id}`"
          >
            <td
              data-field="actions"
              class="px-1.5 py-1.5 text-center panel-landscape:w-14"
              @click.stop
            >
              <AccountingRowActionsButton
                :label="`Acciones de ${alias.match_text}`"
                :test-id="`statement-alias-actions-${alias.id}`"
                @open="actionsAlias = alias"
              />
            </td>
            <td
              data-field="match_text"
              class="px-2.5 py-1.5 first:pl-4 last:pr-4 text-xs text-text-subtle font-mono max-w-[240px]"
              :title="alias.match_text"
              :data-testid="`alias-cell-match_text-${alias.id}`"
            >
              <span class="statement-mobile-label panel-landscape:hidden">Texto a mapear</span>
              <AccountingInlineCell
                :value="alias.match_text"
                :saving="inlineSavingKey === `${alias.id}:match_text`"
                @save="$emit('inline-save', alias, 'match_text', $event)"
              >
                <span class="block truncate">{{ alias.match_text }}</span>
              </AccountingInlineCell>
            </td>
            <td
              data-field="merchant_name"
              class="px-2.5 py-1.5 first:pl-4 last:pr-4 text-sm text-text-default"
              :data-testid="`alias-cell-merchant_name-${alias.id}`"
            >
              <span class="statement-mobile-label panel-landscape:hidden">Comercio</span>
              <AccountingInlineCell
                type="merchant"
                :value="alias.merchant_name"
                :options="merchantOptions"
                :saving="inlineSavingKey === `${alias.id}:merchant_name`"
                @save="$emit('inline-save', alias, 'merchant_name', $event)"
              >
                {{ alias.merchant_name }}
              </AccountingInlineCell>
            </td>
            <td
              data-field="default_category"
              class="px-2.5 py-1.5 first:pl-4 last:pr-4 text-sm text-text-muted"
              :data-testid="`alias-cell-default_category-${alias.id}`"
            >
              <span class="statement-mobile-label panel-landscape:hidden">Categoría</span>
              <AccountingInlineCell
                type="select"
                :value="alias.default_category"
                :options="categoryOptions"
                :saving="inlineSavingKey === `${alias.id}:default_category`"
                @save="$emit('inline-save', alias, 'default_category', $event)"
              >
                {{ alias.default_category_label }}
              </AccountingInlineCell>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <AccountingRowActionsModal
      :open="actionsAlias !== null"
      :record="actionsAlias"
      :title="actionsAlias?.match_text || ''"
      :subtitle="actionsAlias?.merchant_name || ''"
      :actions="aliasActions"
      test-id-prefix="statement-alias"
      @close="actionsAlias = null"
      @select="runAliasAction"
    />

    <EntityHistoryRecordModal
      :open="historyAlias !== null"
      entity-type="merchant_alias"
      :record="historyAlias"
      @close="historyAlias = null"
    />

    <AccountingNoteModal
      :open="noteAlias !== null"
      :subtitle="noteAlias?.match_text || ''"
      :notes="noteAlias?.notes ?? ''"
      @close="noteAlias = null"
    />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue';
import EntityHistoryRecordModal from '~/components/history/EntityHistoryRecordModal.vue';
import AccountingInlineCell from '~/components/accounting/AccountingInlineCell.vue';
import AccountingNoteModal from '~/components/accounting/AccountingNoteModal.vue';
import AccountingRowActionsButton from '~/components/accounting/AccountingRowActionsButton.vue';
import AccountingRowActionsModal from '~/components/accounting/AccountingRowActionsModal.vue';
import { leadingRowActions } from '~/utils/accountingRowActions';

/**
 * Learned merchants (aliases) mapped from an statement descriptor to a merchant
 * name and its default category. The three columns are click-to-edit, exactly
 * like the statement transaction rows — an alias learned wrong used to force a
 * delete-and-relearn round trip through the assistant chat.
 *
 * The merchant column reuses the `merchant` combobox so renaming an alias
 * offers the names already in use instead of quietly creating near-duplicates.
 * The combobox also emits the picked merchant's default category as save
 * metadata; here it is ignored on purpose, since the category of an alias is
 * the value being defined rather than one to inherit.
 */
defineProps({
  aliases: { type: Array, default: () => [] },
  /** Category choices for the inline select: [{ value, label }]. */
  categoryOptions: { type: Array, default: () => [] },
  /** Learned merchants for the inline combobox: [{ value, category, categoryLabel }]. */
  merchantOptions: { type: Array, default: () => [] },
  /** `${aliasId}:${field}` of the cell whose PATCH is in flight. */
  inlineSavingKey: { type: String, default: null },
});

const emit = defineEmits(['inline-save', 'delete']);

// ── Alias row menu ──
// No Editar entry: every column is click-to-edit. The page still receives
// `delete` and asks for confirmation.

const actionsAlias = ref(null);
const historyAlias = ref(null);
const noteAlias = ref(null);

const aliasActions = computed(() => (actionsAlias.value
  ? [
    ...leadingRowActions(actionsAlias.value),
    { id: 'delete', action: 'delete', label: 'Eliminar', danger: true },
  ]
  : []));

const aliasActionHandlers = {
  history: (alias) => { historyAlias.value = alias; },
  notes: (alias) => { noteAlias.value = alias; },
  delete: (alias) => emit('delete', alias),
};

function runAliasAction(id, alias) {
  aliasActionHandlers[id]?.(alias);
}
</script>

<style scoped>
.statement-mobile-label {
  display: block;
  margin-bottom: 0.125rem;
  font-size: 0.6875rem;
  font-weight: 600;
  line-height: 1rem;
  color: var(--color-text-subtle);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

@media (max-width: 1023px) {
  .statement-alias-table,
  .statement-alias-table tbody {
    display: block;
    width: 100%;
  }

  .statement-alias-table thead {
    display: none;
  }

  /* Cells are placed by field: the kebab leads the card and the three
   * editable values stack beside it. */
  .statement-alias-row {
    display: grid;
    grid-template-columns: 2.75rem minmax(0, 1fr);
    gap: 0.625rem 0.75rem;
    height: auto;
    padding: 0.875rem 1rem;
  }

  .statement-alias-row > td {
    min-width: 0;
    max-width: none;
    padding: 0;
  }

  .statement-alias-row > [data-field="actions"] {
    grid-column: 1;
    grid-row: 1;
    align-self: start;
  }

  .statement-alias-row > [data-field="match_text"] {
    grid-column: 2;
    grid-row: 1;
  }

  .statement-alias-row > [data-field="merchant_name"],
  .statement-alias-row > [data-field="default_category"] {
    grid-column: 2;
  }
}
</style>
