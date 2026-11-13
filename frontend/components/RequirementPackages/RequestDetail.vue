<script setup>
import { computed, ref, watch } from "vue";
import ProposalEditor from "./ProposalEditor.vue";
import { packageError } from "~/services/requirementPackagesApi";

const props = defineProps({
  api: { type: Object, required: true },
  row: { type: Object, required: true },
  admin: { type: Boolean, default: false },
  canConsent: { type: Boolean, default: true },
  language: { type: String, default: "es" },
});
const emit = defineEmits(["saved"]);
const { t } = useI18n();
const tr = (key, params = {}) => t(`requirementPackages.${key}`, params);
const message = ref("");
const consent = ref(false);
const busy = ref(false);
const error = ref("");
const proposal = computed(() => props.row.proposal);
const canUsePackage = computed(
  () =>
    proposal.value?.warranty || ["XS", "S", "M"].includes(proposal.value?.size),
);
const canAccept = computed(
  () =>
    canUsePackage.value &&
    (proposal.value?.warranty || props.row.suggested_order_id),
);
watch(
  () => props.row.proposal?.id,
  () => {
    consent.value = false;
    message.value = "";
    error.value = "";
  },
);
async function decide(decision) {
  busy.value = true;
  error.value = "";
  try {
    await props.api.decide(props.row.id, {
      expected_version: props.row.version,
      proposal_id: proposal.value.id,
      decision,
      message: message.value,
      order_id: props.row.suggested_order_id,
    });
    emit("saved");
  } catch (err) {
    error.value = packageError(err);
    emit("saved");
  } finally {
    busy.value = false;
  }
}
async function begin() {
  busy.value = true;
  try {
    await props.api.evaluate(props.row.id, props.row.version);
    emit("saved");
  } catch (err) {
    error.value = packageError(err);
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <section
    class="space-y-5 rounded-xl border border-border-default p-4"
    data-testid="package-request-detail"
  >
    <div class="flex flex-wrap items-start justify-between gap-3">
      <h3 class="text-lg font-semibold text-text-default">{{ row.title }}</h3>
      <span class="text-sm text-text-muted">{{ tr(row.status) }}</span>
    </div>
    <p class="whitespace-pre-wrap text-sm text-text-muted">
      {{ row.description }}
    </p>
    <p v-if="error" role="alert" class="text-sm text-danger-strong">
      {{ error }}
    </p>
    <article v-if="proposal" class="space-y-3 rounded-xl bg-surface-raised p-4">
      <p class="text-lg font-semibold text-text-default">
        {{ tr("size") }} {{ proposal.size }}
        <span v-if="proposal.warranty" class="text-sm"
          >· {{ tr("warranty") }}</span
        >
      </p>
      <div
        v-for="key in [
          'scope',
          'explanation',
          'assumptions',
          'schedule_conditions',
        ]"
        :key="key"
        class="text-sm text-text-default"
      >
        <template v-if="proposal[key]"
          ><p class="font-semibold">
            {{ tr(key === "schedule_conditions" ? "scheduleConditions" : key) }}
          </p>
          <p class="whitespace-pre-wrap text-text-muted">
            {{ proposal[key] }}
          </p></template
        >
      </div>
      <p class="text-sm text-text-default">
        {{ tr("schedule") }}: {{ proposal.delivery_from }} —
        {{ proposal.delivery_until }}
      </p>
      <ul class="list-inside list-disc text-sm text-text-muted">
        <li v-for="example in proposal.examples" :key="example">
          {{ example }}
        </li>
      </ul>
      <p v-if="!canUsePackage" class="text-sm text-text-muted">
        {{ tr("outside") }}
      </p>
      <div v-if="!admin && row.status === 'offered'" class="space-y-3">
        <p v-if="!canAccept && canUsePackage" class="text-sm text-text-muted">
          {{ tr("noBalance") }}
        </p>
        <p
          v-if="row.suggested_order_id && !proposal.warranty"
          class="break-all text-xs text-text-muted"
        >
          {{ tr("source", { order: row.suggested_order_id }) }}
        </p>
        <BaseCheckbox
          v-model="consent"
          :disabled="busy || !canConsent"
          :disabled-reason="tr('ownDecision')"
          >{{ tr("consent") }}</BaseCheckbox
        >
        <label class="block space-y-2 text-sm text-text-default"
          ><span>{{ tr("objection") }}</span
          ><textarea
            v-model="message"
            rows="3"
            maxlength="8000"
            class="w-full rounded-lg border border-input-border bg-input-bg px-3 py-2 text-sm text-input-text"
          />
        </label>
        <div class="flex flex-wrap gap-3">
          <BaseButton
            variant="primary"
            :disabled="busy || !consent || !canAccept || !canConsent"
            :disabled-reason="
              !canConsent
                ? tr('ownDecision')
                : !canAccept
                  ? tr('noBalance')
                  : tr('consent')
            "
            data-testid="package-accept"
            @click="decide('accept')"
            >{{
              proposal.warranty
                ? tr("acceptWarranty")
                : tr("acceptance", { size: proposal.size })
            }}</BaseButton
          >
          <BaseButton
            variant="secondary"
            :disabled="busy || !message.trim() || !canConsent"
            :disabled-reason="!canConsent ? tr('ownDecision') : tr('objection')"
            data-testid="package-object"
            @click="decide('object')"
            >{{ tr("object") }}</BaseButton
          >
        </div>
      </div>
    </article>
    <div v-if="admin" class="space-y-4">
      <BaseButton
        v-if="['pending', 'objected'].includes(row.status)"
        variant="secondary"
        :disabled="busy"
        :disabled-reason="tr('busy')"
        @click="begin"
        >{{ tr("evaluate") }}</BaseButton
      >
      <ProposalEditor
        :key="`${row.id}-${row.version}`"
        :api="api"
        :row="row"
        :language="language"
        @saved="emit('saved')"
      />
    </div>
    <details v-if="row.proposals?.length" class="space-y-3">
      <summary class="cursor-pointer text-sm font-semibold text-text-default">
        {{ tr("history") }}
      </summary>
      <article
        v-for="item in row.proposals"
        :key="item.id"
        class="space-y-1 rounded-lg border border-border-default p-3 text-sm text-text-muted"
      >
        <p>#{{ item.id }} · {{ item.size }} · {{ item.created_at }}</p>
        <p>{{ item.explanation }}</p>
        <p v-if="item.decision">
          {{ item.decision.decision }} · {{ item.decision.message }}
        </p>
      </article>
    </details>
  </section>
</template>
