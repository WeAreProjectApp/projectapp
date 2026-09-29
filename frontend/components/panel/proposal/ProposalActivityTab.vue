<template>
  <!-- Log activity form -->
  <div class="bg-surface rounded-xl shadow-sm border border-border-muted p-5 mb-6">
    <div class="flex items-center gap-1.5 mb-3">
      <h3 class="text-sm font-semibold text-text-default">Registrar actividad</h3>
      <BaseTooltip position="right">
        <template #trigger>
          <QuestionMarkCircleIcon class="w-3.5 h-3.5 text-text-subtle hover:text-text-muted transition-colors" />
        </template>
        {{ tt.logActivity }}
      </BaseTooltip>
    </div>
    <div class="flex flex-col sm:flex-row gap-3">
      <BaseSelect v-model="activityForm.change_type" size="sm" class="sm:w-40">
        <option value="call">📞 Llamada</option>
        <option value="meeting">🤝 Reunión</option>
        <option value="followup">📩 Seguimiento</option>
        <option value="note">📝 Nota</option>
      </BaseSelect>
      <BaseInput
        v-model="activityForm.description"
        type="text"
        size="sm"
        placeholder="Descripción de la actividad..."
        class="flex-1"
        @keydown.enter.prevent="submitActivity"
      />
      <BaseControlGate
        :reasons="!activityForm.description.trim() ? ['Escribe la descripción de la actividad.'] : []"
        label="Agregar actividad no disponible"
        align="end"
      >
        <template #default="{ describedBy }">
          <BaseButton
            variant="primary"
            size="md"
            class="whitespace-nowrap"
            :loading="isSubmittingActivity"
            :disabled="!activityForm.description.trim()"
            disabled-reason="Escribe la descripción de la actividad."
            :aria-describedby="describedBy"
            @click="submitActivity"
          >
            {{ isSubmittingActivity ? 'Guardando...' : 'Agregar' }}
          </BaseButton>
        </template>
      </BaseControlGate>
    </div>
  </div>

  <!-- Timeline -->
  <div class="bg-surface rounded-xl shadow-sm border border-border-muted p-5">
    <div class="flex items-center gap-1.5 mb-4">
      <h3 class="text-sm font-semibold text-text-default">Historial de actividad</h3>
      <BaseTooltip position="right">
        <template #trigger>
          <QuestionMarkCircleIcon class="w-3.5 h-3.5 text-text-subtle hover:text-text-muted transition-colors" />
        </template>
        {{ tt.activityHistory }}
      </BaseTooltip>
    </div>
    <div v-if="!changeLogs.length" class="text-center py-8 text-sm text-text-subtle">Sin actividad registrada.</div>
    <div v-else class="relative pl-6 space-y-0">
      <div class="absolute left-[9px] top-2 bottom-2 w-px bg-surface-raised" />
      <div v-for="log in changeLogs" :key="log.id" class="relative pb-5 last:pb-0">
        <div class="absolute -left-6 top-1 w-[18px] h-[18px] rounded-full border-2 border-border-default shadow-sm flex items-center justify-center text-[10px]" :class="activityDotClass(log.change_type)">
          {{ activityIcon(log.change_type) }}
        </div>
        <div class="ml-2">
          <div class="flex items-baseline gap-2">
            <span class="text-xs font-semibold" :class="activityLabelClass(log.change_type)">{{ activityLabel(log.change_type) }}</span>
            <span class="text-[10px] text-text-subtle">{{ formatLogDate(log.created_at) }}</span>
          </div>
          <!-- eslint-disable-next-line vue/no-v-html -->
          <p class="text-sm text-text-muted/60 mt-0.5" v-html="formatActivityDescription(log)"></p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue';
import { QuestionMarkCircleIcon } from '@heroicons/vue/24/outline';
import { useProposalStore } from '~/stores/proposals';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { useTooltipTexts } from '~/composables/useTooltipTexts';

const props = defineProps({
  proposal: {
    type: Object,
    default: null,
  },
});

const proposalStore = useProposalStore();
const notify = usePanelNotify();
const { proposalEdit: tt } = useTooltipTexts();

const activityForm = reactive({ change_type: 'note', description: '' });
const isSubmittingActivity = ref(false);
const changeLogs = computed(() => props.proposal?.change_logs || []);

async function submitActivity() {
  if (!activityForm.description.trim() || isSubmittingActivity.value) return;
  isSubmittingActivity.value = true;
  try {
    const result = await proposalStore.logActivity(props.proposal.id, {
      change_type: activityForm.change_type,
      description: activityForm.description.trim(),
    });
    if (result.success) {
      activityForm.description = '';
      await proposalStore.fetchProposal(props.proposal.id);
      notify.success({ title: 'Actividad registrada.' });
    } else {
      notify.error({ title: 'No se pudo registrar la actividad.' });
    }
  } finally {
    isSubmittingActivity.value = false;
  }
}

// Status-semantic entries use design tokens (they auto-flip in dark mode).
// purple/indigo/orange/sky are CATEGORICAL activity hues with no semantic
// token equivalent — they keep manual dark: overrides on purpose.
const AC = {
  gray:    { dot: 'bg-surface-raised',    text: 'text-text-muted' },
  grayMd:  { dot: 'bg-surface-raised',    text: 'text-text-muted' },
  blue:    { dot: 'bg-info-soft',    text: 'text-info-strong' },
  green:   { dot: 'bg-success-soft',   text: 'text-success-strong' },
  emerald: { dot: 'bg-primary-soft', text: 'text-text-brand' },
  red:     { dot: 'bg-danger-soft',     text: 'text-danger-strong' },
  yellow:  { dot: 'bg-warning-soft',  text: 'text-warning-strong' },
  purple:  { dot: 'bg-purple-100 dark:bg-purple-900/30',  text: 'text-purple-600 dark:text-purple-400' },
  indigo:  { dot: 'bg-indigo-100 dark:bg-indigo-900/30',  text: 'text-indigo-600 dark:text-indigo-400' },
  orange:  { dot: 'bg-orange-100 dark:bg-orange-900/30',  text: 'text-orange-600 dark:text-orange-400' },
  sky:     { dot: 'bg-sky-100 dark:bg-sky-900/30',     text: 'text-sky-600 dark:text-sky-400' },
  amber:   { dot: 'bg-warning-soft',   text: 'text-warning-strong' },
};
const activityMeta = {
  created:       { icon: '✨', label: 'Creada',                   ...AC.gray },
  updated:       { icon: '✏️', label: 'Editada',                  ...AC.gray },
  sent:          { icon: '📤', label: 'Enviada',                  ...AC.blue },
  viewed:        { icon: '👁',  label: 'Vista',                    ...AC.green },
  accepted:      { icon: '✅', label: 'Aceptada',                 ...AC.emerald },
  rejected:      { icon: '❌', label: 'Rechazada',                ...AC.red },
  resent:        { icon: '🔁', label: 'Re-enviada',               ...AC.blue },
  expired:       { icon: '⏰', label: 'Expirada',                 ...AC.yellow },
  duplicated:    { icon: '📋', label: 'Duplicada',                ...AC.gray },
  commented:     { icon: '💬', label: 'Comentario',               ...AC.purple },
  negotiating:   { icon: '🤝', label: 'Negociando',               ...AC.indigo },
  reengagement:  { icon: '🔔', label: 'Reengagement',             ...AC.orange },
  call:          { icon: '📞', label: 'Llamada',                  ...AC.sky },
  meeting:       { icon: '🤝', label: 'Reunión',                  ...AC.indigo },
  followup:      { icon: '📩', label: 'Seguimiento',              ...AC.amber },
  note:          { icon: '📝', label: 'Nota',                     ...AC.grayMd },
  module_interests: { icon: '🧩', label: 'Interés en módulos', ...AC.emerald },
  calc_confirmed:{ icon: '🧮', label: 'Calculadora confirmada',   ...AC.emerald },
  calc_abandoned:{ icon: '🧮', label: 'Calculadora abandonada',   ...AC.red },
  calc_followup: { icon: '🧮', label: 'Seguimiento calculadora',  ...AC.orange },
  auto_archived: { icon: '📦', label: 'Auto-archivada',           ...AC.gray },
  status_change: { icon: '🔄', label: 'Cambio de estado',         ...AC.blue },
  cond_accepted: { icon: '⚠️', label: 'Aceptación condicional',   ...AC.amber },
  req_clicked:   { icon: '🔗', label: 'Requerimiento consultado', ...AC.sky },
  email_sent:    { icon: '📧', label: 'Correo enviado',           ...AC.emerald },
};
function activityIcon(type) { return activityMeta[type]?.icon || '•'; }
function activityLabel(type) { return activityMeta[type]?.label || type; }
function activityDotClass(type) { return activityMeta[type]?.dot || AC.gray.dot; }
function activityLabelClass(type) { return activityMeta[type]?.text || AC.gray.text; }

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function fmtDate(val) {
  if (!val) return '(vacío)';
  const d = new Date(val);
  if (isNaN(d.getTime())) return escapeHtml(val);
  return escapeHtml(d.toLocaleString('es-CO', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' }));
}

function formatActivityDescription(log) {
  const desc = log.description || '';

  if (log.change_type === 'module_interests') {
    try {
      const modules = JSON.parse(desc);
      return modules.length ? `Módulos de interés: ${modules.map(module => escapeHtml(module.name_es)).join(', ')}` : 'Retiró su selección de intereses.';
    } catch { return escapeHtml(desc); }
  }

  // Calculator events — plain text (no v-html needed for counts)
  if (log.change_type === 'calc_abandoned' || log.change_type === 'calc_confirmed') {
    try {
      const data = JSON.parse(desc);
      const selected = data.selected || [];
      const deselected = data.deselected || [];
      const total = data.total;
      const elapsed = data.elapsed_seconds || 0;
      const mins = Math.floor(elapsed / 60);
      const secs = Math.round(elapsed % 60);
      const timeStr = mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
      const totalStr = total != null ? `<strong>$${Number(total).toLocaleString('es-CO')}</strong>` : '';
      if (log.change_type === 'calc_confirmed') {
        return `Confirmó <strong>${selected.length}</strong> módulo${selected.length !== 1 ? 's' : ''}`
          + (totalStr ? ` — Total: ${totalStr}` : '')
          + (elapsed ? ` — Tiempo en calculadora: <strong>${timeStr}</strong>` : '');
      }
      return `Abandonó calculadora con <strong>${selected.length}</strong> módulo${selected.length !== 1 ? 's' : ''} seleccionado${selected.length !== 1 ? 's' : ''}`
        + (deselected.length ? `, <strong>${deselected.length}</strong> desmarcado${deselected.length !== 1 ? 's' : ''}` : '')
        + (totalStr ? ` — Total: ${totalStr}` : '')
        + (elapsed ? ` — Tiempo: <strong>${timeStr}</strong>` : '');
    } catch (_e) {
      return escapeHtml(desc);
    }
  }

  // Requirement clicked
  if (log.change_type === 'req_clicked') {
    try {
      const data = JSON.parse(desc);
      return `Cliente consultó <strong>${escapeHtml(data.group_title || 'módulo')}</strong>`;
    } catch (_e) { return escapeHtml(desc); }
  }

  // Field updates with old/new values
  const FIELD_LABELS_MAP = {
    title: 'Título', total_investment: 'Inversión total', currency: 'Moneda',
    client_name: 'Nombre del cliente', client_email: 'Email del cliente',
    status: 'Estado', expires_at: 'Fecha de expiración',
    followup_scheduled_at: 'Seguimiento programado',
  };
  if (log.change_type === 'updated' && log.field_name) {
    const fieldLabel = FIELD_LABELS_MAP[log.field_name] || log.field_name;
    const isCurrency = log.field_name === 'total_investment';
    const isDate = ['expires_at', 'followup_scheduled_at'].includes(log.field_name);
    const fmtCurrency = (val) => {
      const num = parseFloat(val);
      if (isNaN(num)) return escapeHtml(val || '(vacío)');
      return `<strong>$${num.toLocaleString('es-CO', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</strong>`;
    };
    const oldDisplay = isCurrency ? fmtCurrency(log.old_value) : isDate ? fmtDate(log.old_value) : escapeHtml(log.old_value || '(vacío)');
    const newDisplay = isCurrency ? fmtCurrency(log.new_value) : isDate ? `<strong>${fmtDate(log.new_value)}</strong>` : `<strong>${escapeHtml(log.new_value || '(vacío)')}</strong>`;
    return `<strong>${escapeHtml(fieldLabel)}</strong>: ${oldDisplay} → ${newDisplay}`;
  }

  // Status change
  if (log.change_type === 'status_change' && log.old_value && log.new_value) {
    return `<strong>Estado</strong>: ${escapeHtml(log.old_value)} → <strong>${escapeHtml(log.new_value)}</strong>`;
  }

  // Client comment — bold the comment body
  if (log.change_type === 'commented') {
    const prefix = 'Client left a comment: ';
    if (desc.startsWith(prefix)) {
      return `Client left a comment: <strong>${escapeHtml(desc.slice(prefix.length))}</strong>`;
    }
    return escapeHtml(desc);
  }

  // Negotiating — bold the comment when present
  if (log.change_type === 'negotiating') {
    const key = ' Comment: ';
    const idx = desc.indexOf(key);
    if (idx !== -1) {
      return `${escapeHtml(desc.slice(0, idx))} Comment: <strong>${escapeHtml(desc.slice(idx + key.length))}</strong>`;
    }
    return escapeHtml(desc);
  }

  // Rejected — bold the rejection reason when present
  if (log.change_type === 'rejected') {
    const key = ' Reason: ';
    const idx = desc.indexOf(key);
    if (idx !== -1) {
      return `${escapeHtml(desc.slice(0, idx))} Reason: <strong>${escapeHtml(desc.slice(idx + key.length))}</strong>`;
    }
    return escapeHtml(desc);
  }

  // Conditional acceptance — bold the condition text
  if (log.change_type === 'cond_accepted') {
    const prefix = 'Conditional acceptance: ';
    if (desc.startsWith(prefix)) {
      return `Conditional acceptance: <strong>${escapeHtml(desc.slice(prefix.length))}</strong>`;
    }
    return escapeHtml(desc);
  }

  // Accepted — bold condition when present
  if (log.change_type === 'accepted') {
    const key = ' Condition: ';
    const idx = desc.indexOf(key);
    if (idx !== -1) {
      return `${escapeHtml(desc.slice(0, idx))} Condition: <strong>${escapeHtml(desc.slice(idx + key.length))}</strong>`;
    }
    return escapeHtml(desc);
  }

  // Sent / resent — bold the recipient email
  if (log.change_type === 'sent' || log.change_type === 'resent') {
    const key = ' to ';
    const idx = desc.indexOf(key);
    if (idx !== -1) {
      const afterTo = desc.slice(idx + key.length);
      const email = afterTo.endsWith('.') ? afterTo.slice(0, -1) : afterTo;
      return `${escapeHtml(desc.slice(0, idx))} to <strong>${escapeHtml(email)}</strong>.`;
    }
    return escapeHtml(desc);
  }

  // Created / duplicated — bold the proposal title between quotes
  if (log.change_type === 'created' || log.change_type === 'duplicated') {
    return escapeHtml(desc).replace(/&quot;(.+?)&quot;/, '<strong>&quot;$1&quot;</strong>');
  }

  return escapeHtml(desc);
}

function formatLogDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString('es-CO', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}
</script>
