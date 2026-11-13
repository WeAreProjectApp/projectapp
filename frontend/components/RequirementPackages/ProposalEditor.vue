<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { packageError } from "~/services/requirementPackagesApi";

const props = defineProps({
  api: { type: Object, required: true },
  row: { type: Object, required: true },
  language: { type: String, default: "es" },
});
const emit = defineEmits(["saved"]);
const { t } = useI18n();
const tr = (key) => t(`requirementPackages.${key}`);
const busy = ref(false);
const error = ref("");
const context = ref(null);
const form = ref({
  size: "XS",
  scope: "",
  explanation: "",
  assumptions: "",
  delivery_from: "",
  delivery_until: "",
  schedule_conditions: "",
  signal_ids: [],
  warranty: false,
});
const fieldClass =
  "w-full rounded-lg border border-input-border bg-input-bg px-3 py-2 text-sm text-input-text";
const sizes = ["XS", "S", "M", "L", "XL", "PROJECT"];
const sizeItems = computed(() =>
  sizes.map((size) => ({
    label: size,
    onClick: () => {
      form.value.size = size;
      form.value.signal_ids = [];
    },
  })),
);
const signals = computed(
  () =>
    context.value?.definition.signals.filter(
      (row) => row.size === form.value.size,
    ) || [],
);
function initialize() {
  form.value = {
    size: props.row.proposal?.size || "XS",
    scope: props.row.proposal?.scope || props.row.description,
    explanation: props.row.proposal?.explanation || "",
    assumptions: props.row.proposal?.assumptions || "",
    delivery_from: "",
    delivery_until: "",
    schedule_conditions: "",
    signal_ids: [],
    warranty: false,
  };
}
async function loadContext() {
  try {
    context.value = await props.api.context();
  } catch (err) {
    error.value = packageError(err);
  }
}
async function publish() {
  busy.value = true;
  error.value = "";
  try {
    await props.api.offer(props.row.id, {
      ...form.value,
      expected_version: props.row.version,
      language: props.language,
    });
    emit("saved");
  } catch (err) {
    error.value = packageError(err);
  } finally {
    busy.value = false;
  }
}
watch(() => props.row.id, initialize, { immediate: true });
onMounted(loadContext);
</script>

<template>
  <form
    class="space-y-4 rounded-xl border border-border-default p-4"
    data-testid="package-proposal-editor"
    @submit.prevent="publish"
  >
    <p v-if="error" role="alert" class="text-sm text-danger-strong">
      {{ error }}
    </p>
    <p v-if="context?.warning" class="text-sm text-text-muted">
      {{ context.warning }}
    </p>
    <div class="flex flex-wrap items-center gap-4">
      <BaseDropdown :items="sizeItems"
        ><template #trigger
          ><BaseButton variant="secondary"
            >{{ tr("size") }}: {{ form.size }}</BaseButton
          ></template
        ></BaseDropdown
      >
      <BaseCheckbox v-model="form.warranty">{{ tr("warranty") }}</BaseCheckbox>
    </div>
    <label class="block space-y-2 text-sm text-text-default"
      ><span>{{ tr("scope") }}</span
      ><textarea
        v-model="form.scope"
        :class="fieldClass"
        rows="3"
        required
        maxlength="15000"
      />
    </label>
    <label class="block space-y-2 text-sm text-text-default"
      ><span>{{ tr("explanation") }}</span
      ><textarea
        v-model="form.explanation"
        :class="fieldClass"
        rows="3"
        required
        maxlength="8000"
      />
    </label>
    <label class="block space-y-2 text-sm text-text-default"
      ><span>{{ tr("assumptions") }}</span
      ><textarea
        v-model="form.assumptions"
        :class="fieldClass"
        rows="2"
        maxlength="8000"
      />
    </label>
    <div class="grid gap-4 sm:grid-cols-2">
      <label class="space-y-2 text-sm text-text-default"
        ><span>{{ tr("from") }}</span
        ><input
          v-model="form.delivery_from"
          :class="fieldClass"
          type="date"
          required
      /></label>
      <label class="space-y-2 text-sm text-text-default"
        ><span>{{ tr("until") }}</span
        ><input
          v-model="form.delivery_until"
          :class="fieldClass"
          type="date"
          required
          :min="form.delivery_from"
      /></label>
    </div>
    <label class="block space-y-2 text-sm text-text-default"
      ><span>{{ tr("scheduleConditions") }}</span
      ><textarea
        v-model="form.schedule_conditions"
        :class="fieldClass"
        rows="2"
        maxlength="4000"
      />
    </label>
    <fieldset class="space-y-2">
      <legend class="mb-2 text-sm font-medium text-text-default">
        {{ tr("signals") }}
      </legend>
      <div
        class="max-h-64 space-y-2 overflow-y-auto rounded-lg border border-border-default p-3"
      >
        <BaseCheckbox
          v-for="signal in signals"
          :key="signal.id"
          v-model="form.signal_ids"
          :value="signal.id"
          class="flex"
          >{{ signal.label }}</BaseCheckbox
        >
      </div>
    </fieldset>
    <BaseButton
      type="submit"
      variant="primary"
      :disabled="
        busy || !context || (form.size !== 'PROJECT' && !form.signal_ids.length)
      "
      :disabled-reason="busy ? tr('busy') : tr('noSignals')"
      >{{ tr("publish") }}</BaseButton
    >
  </form>
</template>
