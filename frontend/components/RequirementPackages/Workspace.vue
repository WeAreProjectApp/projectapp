<script setup>
import { computed, onMounted, ref, watch } from "vue";
import ExampleEditor from "./ExampleEditor.vue";
import RequestDetail from "./RequestDetail.vue";
import { packageError } from "~/services/requirementPackagesApi";

const props = defineProps({
  api: { type: Object, required: true },
  canConsent: { type: Boolean, default: true },
  initialRequest: { type: [String, Number], default: "" },
});
const { t, locale } = useI18n();
const route = useRoute();
const tr = (key, params = {}) => t(`requirementPackages.${key}`, params);
const language = computed(() => (locale.value.startsWith("en") ? "en" : "es"));
const data = ref(null);
const loading = ref(false);
const busy = ref(false);
const error = ref("");
const success = ref("");
const selected = ref(null);
const conditions = ref({});
const newRequest = ref({ title: "", description: "" });
const externalPayments = ref({});
const reasons = ref({});
const settings = ref({ nationality: "COL", tax_rate: 19, expected_version: 0 });
const pages = ref({ order_offset: 0, request_offset: 0, movement_offset: 0 });
const admin = computed(() => Boolean(data.value?.is_admin));
const fieldClass =
  "w-full rounded-lg border border-input-border bg-input-bg px-3 py-2 text-sm text-input-text";
const markets = computed(() =>
  ["COL", "EXT", "USA"].map((market) => ({
    label: market,
    onClick: () => {
      settings.value.nationality = market;
    },
  })),
);
const money = (value, currency) =>
  new Intl.NumberFormat(locale.value, { style: "currency", currency }).format(
    Number(value),
  );
const orderState = (state) =>
  tr(
    {
      pending: "orderPending",
      processing: "orderProcessing",
      paid: "orderPaid",
      failed: "orderFailed",
      cancelled: "cancelled",
    }[state] || "orderPending",
  );
const dateText = (date) =>
  date ? new Date(date).toLocaleDateString(locale.value) : "—";
let loadSequence = 0;

async function load() {
  const seq = ++loadSequence;
  loading.value = true;
  error.value = "";
  try {
    const result = await props.api.overview(language.value, pages.value);
    if (seq !== loadSequence) return;
    data.value = result;
    if (result.settings)
      settings.value = {
        ...result.settings,
        expected_version: result.settings.version,
      };
    for (const order of result.orders.results)
      if (!externalPayments.value[order.id])
        externalPayments.value[order.id] = {
          paid_at: "",
          payment_reference: "",
        };
    const requestId =
      selected.value?.id || props.initialRequest || route.query.request;
    if (requestId) selected.value = await props.api.request(Number(requestId));
  } catch (err) {
    if (seq === loadSequence) error.value = packageError(err);
  } finally {
    if (seq === loadSequence) loading.value = false;
  }
}
async function perform(action) {
  if (busy.value) return null;
  busy.value = true;
  error.value = "";
  success.value = "";
  try {
    const result = await action();
    success.value = tr("saved");
    await load();
    return result;
  } catch (err) {
    error.value = packageError(err);
    return null;
  } finally {
    busy.value = false;
  }
}
async function buy(pkg, method) {
  await perform(async () => {
    const order = await props.api.createOrder({
      package_id: pkg.package_id,
      method,
      language: language.value,
      conditions_accepted: Boolean(conditions.value[pkg.package_id]),
      quote_digest: pkg.quote_digest,
    });
    if (method === "online") {
      const checkout = await props.api.checkout(order.id);
      window.location.assign(checkout.checkout_url);
    }
  });
}
async function resumePayment(order) {
  await perform(async () => {
    const checkout = await props.api.checkout(order.id);
    window.location.assign(checkout.checkout_url);
  });
}
async function sendRequest() {
  await perform(async () => {
    const created = await props.api.createRequest(newRequest.value);
    selected.value = await props.api.request(created.id);
    newRequest.value = { title: "", description: "" };
    pages.value.request_offset = 0;
  });
}
async function openRequest(row) {
  try {
    selected.value = await props.api.request(row.id);
  } catch (err) {
    error.value = packageError(err);
  }
}
async function confirmExternal(order) {
  await perform(() =>
    props.api.confirmExternal(order.id, {
      ...externalPayments.value[order.id],
      paid_at: new Date(externalPayments.value[order.id].paid_at).toISOString(),
    }),
  );
}
async function saveSettings() {
  await perform(() =>
    props.api.settings({
      expected_version: settings.value.expected_version,
      nationality: settings.value.nationality,
      tax_rate: settings.value.tax_rate,
    }),
  );
}
async function verifyReturn() {
  const order = route.query.order;
  const tx = route.query.id || route.query.transaction_id;
  if (typeof order === "string" && typeof tx === "string")
    await perform(() => props.api.verify(order, tx));
}
async function changePage(key, amount) {
  pages.value[key] = Math.max(0, pages.value[key] + amount);
  await load();
}
watch(language, load);
onMounted(async () => {
  await load();
  await verifyReturn();
});
</script>

<template>
  <div
    class="min-w-0 space-y-6 [overflow-wrap:anywhere]"
    data-testid="requirement-packages-workspace"
  >
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 class="text-xl font-bold text-text-default">{{ tr("title") }}</h1>
        <p class="mt-2 text-sm text-text-muted">{{ tr("intro") }}</p>
      </div>
      <BaseButton
        variant="secondary"
        :disabled="busy || loading"
        :disabled-reason="tr('busy')"
        @click="load"
        >{{ tr("refresh") }}</BaseButton
      >
    </div>
    <p
      v-if="error"
      role="alert"
      class="rounded-lg bg-danger-soft p-3 text-sm text-danger-strong"
    >
      {{ error }}
    </p>
    <p v-if="success" role="status" class="text-sm text-text-brand">
      {{ success }}
    </p>
    <p v-if="loading" role="status" class="text-sm text-text-muted">
      {{ tr("loading") }}
    </p>
    <BaseButton v-if="!data && error" variant="secondary" @click="load">{{
      tr("retry")
    }}</BaseButton>
    <template v-if="data">
      <section class="space-y-3">
        <h2 class="text-lg font-semibold text-text-default">
          {{ tr("balances") }}
        </h2>
        <div class="grid grid-cols-3 gap-3">
          <div
            v-for="(count, size) in data.balances"
            :key="size"
            class="rounded-xl border border-border-default bg-surface-raised p-4 text-center"
          >
            <p class="text-sm text-text-muted">{{ size }}</p>
            <p
              class="mt-1 text-2xl font-bold text-text-default"
              :data-testid="`package-balance-${size}`"
            >
              {{ count }}
            </p>
          </div>
        </div>
      </section>
      <details
        class="space-y-3 rounded-xl border border-border-default p-4"
        open
      >
        <summary class="cursor-pointer text-lg font-semibold text-text-default">
          {{ tr("sizes") }}
        </summary>
        <div class="grid gap-3 sm:grid-cols-2">
          <article
            v-for="row in data.examples.sizes"
            :key="row.size"
            class="space-y-2 rounded-lg bg-surface-raised p-3"
            :data-testid="`package-size-${row.size}`"
          >
            <h3 class="font-semibold text-text-default">{{ row.size }}</h3>
            <p class="text-xs text-text-muted">
              {{
                row.source === "project"
                  ? tr("projectExample")
                  : tr("genericExample")
              }}
            </p>
            <ul class="list-inside list-disc text-sm text-text-muted">
              <li v-for="example in row.examples" :key="example">
                {{ example }}
              </li>
            </ul>
          </article>
        </div>
        <p class="text-sm text-text-muted">{{ tr("outside") }}</p>
      </details>
      <section class="space-y-3">
        <h2 class="text-lg font-semibold text-text-default">
          {{ tr("catalog") }}
        </h2>
        <p v-if="!data.catalog.length" class="text-sm text-text-muted">
          {{ tr("emptyCatalog") }}
        </p>
        <div class="grid gap-4 xl:grid-cols-3">
          <article
            v-for="pkg in data.catalog"
            :key="pkg.package_id"
            class="flex min-w-0 flex-col gap-3 rounded-xl border border-border-default p-4"
          >
            <h3 class="text-lg font-semibold text-text-default">
              {{ pkg.name }}
            </h3>
            <p class="text-sm text-text-default">
              {{
                Object.entries(pkg.counts)
                  .map(([size, count]) => `${count} ${size}`)
                  .join(" · ")
              }}
            </p>
            <p class="text-sm text-text-muted">
              {{ tr("subtotal") }}: {{ money(pkg.subtotal, pkg.currency) }} ·
              {{ pkg.tax_rate }} %
            </p>
            <p class="font-semibold text-text-default">
              {{ tr("total") }}: {{ money(pkg.total, pkg.currency) }}
            </p>
            <p class="text-sm text-text-muted">
              {{ tr("validity", { months: pkg.validity_months }) }}
            </p>
            <p class="text-sm text-text-muted">{{ pkg.terms }}</p>
            <BaseCheckbox v-model="conditions[pkg.package_id]">{{
              tr("conditions")
            }}</BaseCheckbox>
            <div class="mt-auto flex flex-wrap gap-2">
              <BaseButton
                v-if="pkg.online_available"
                variant="primary"
                :disabled="busy || !conditions[pkg.package_id]"
                :disabled-reason="busy ? tr('busy') : tr('confirmRequired')"
                @click="buy(pkg, 'online')"
                >{{ tr("online") }}</BaseButton
              ><BaseButton
                variant="secondary"
                :disabled="busy || !conditions[pkg.package_id]"
                :disabled-reason="busy ? tr('busy') : tr('confirmRequired')"
                @click="buy(pkg, 'external')"
                >{{ tr("external") }}</BaseButton
              >
            </div>
          </article>
        </div>
      </section>
      <section class="space-y-3">
        <h2 class="text-lg font-semibold text-text-default">
          {{ tr("newRequest") }}
        </h2>
        <form class="space-y-3" @submit.prevent="sendRequest">
          <label class="block space-y-2 text-sm text-text-default"
            ><span>{{ tr("requestTitle") }}</span
            ><input
              v-model="newRequest.title"
              :class="fieldClass"
              required
              maxlength="300"
          /></label>
          <label class="block space-y-2 text-sm text-text-default"
            ><span>{{ tr("description") }}</span
            ><textarea
              v-model="newRequest.description"
              :class="fieldClass"
              rows="4"
              required
              maxlength="15000"
            />
          </label>
          <BaseButton
            type="submit"
            variant="primary"
            :disabled="busy"
            :disabled-reason="tr('busy')"
            >{{ tr("send") }}</BaseButton
          >
        </form>
      </section>
      <section class="space-y-3">
        <h2 class="text-lg font-semibold text-text-default">
          {{ tr("requests") }}
        </h2>
        <p v-if="!data.requests.count" class="text-sm text-text-muted">
          {{ tr("emptyRequests") }}
        </p>
        <ul class="space-y-2">
          <li
            v-for="row in data.requests.results"
            :key="row.id"
            class="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border-default p-3"
          >
            <div>
              <p class="font-medium text-text-default">{{ row.title }}</p>
              <p class="text-sm text-text-muted">{{ tr(row.status) }}</p>
            </div>
            <BaseButton variant="secondary" @click="openRequest(row)">{{
              tr("detail")
            }}</BaseButton>
          </li>
        </ul>
        <div class="flex gap-2">
          <BaseButton
            v-if="pages.request_offset"
            variant="secondary"
            @click="changePage('request_offset', -20)"
            >{{ tr("previous") }}</BaseButton
          ><BaseButton
            v-if="data.requests.count > pages.request_offset + 20"
            variant="secondary"
            @click="changePage('request_offset', 20)"
            >{{ tr("more") }}</BaseButton
          >
        </div>
      </section>
      <RequestDetail
        v-if="selected"
        :key="selected.id"
        :api="api"
        :row="selected"
        :admin="admin"
        :can-consent="canConsent"
        :language="language"
        @saved="load"
      />
      <section class="space-y-3">
        <h2 class="text-lg font-semibold text-text-default">
          {{ tr("orders") }}
        </h2>
        <p v-if="!data.orders.count" class="text-sm text-text-muted">
          {{ tr("none") }}
        </p>
        <article
          v-for="order in data.orders.results"
          :key="order.id"
          class="space-y-3 rounded-xl border border-border-default p-4"
        >
          <p class="font-semibold text-text-default">
            {{ order.snapshot.name }} · {{ orderState(order.status) }} ·
            {{ money(order.total, order.currency) }}
          </p>
          <p class="break-all text-xs text-text-muted">{{ order.id }}</p>
          <p v-if="order.expires_at" class="text-sm text-text-muted">
            {{ tr("expires") }}: {{ dateText(order.expires_at) }}
          </p>
          <BaseButton
            v-if="
              order.method === 'online' &&
              ['pending', 'processing', 'failed'].includes(order.status)
            "
            variant="secondary"
            :disabled="busy"
            :disabled-reason="tr('busy')"
            @click="resumePayment(order)"
            >{{ tr("checkout") }}</BaseButton
          >
          <form
            v-if="
              admin && order.method === 'external' && order.status === 'pending'
            "
            class="grid items-end gap-3 sm:grid-cols-2"
            @submit.prevent="confirmExternal(order)"
          >
            <label class="space-y-2 text-sm text-text-default"
              ><span>{{ tr("paidAt") }}</span
              ><input
                v-model="externalPayments[order.id].paid_at"
                :class="fieldClass"
                type="datetime-local"
                required /></label
            ><label class="space-y-2 text-sm text-text-default"
              ><span>{{ tr("reference") }}</span
              ><input
                v-model="externalPayments[order.id].payment_reference"
                :class="fieldClass"
                required
                maxlength="200" /></label
            ><BaseButton
              type="submit"
              variant="primary"
              :disabled="busy"
              :disabled-reason="tr('busy')"
              >{{ tr("confirmPayment") }}</BaseButton
            >
          </form>
        </article>
        <div class="flex gap-2">
          <BaseButton
            v-if="pages.order_offset"
            variant="secondary"
            @click="changePage('order_offset', -20)"
            >{{ tr("previous") }}</BaseButton
          ><BaseButton
            v-if="data.orders.count > pages.order_offset + 20"
            variant="secondary"
            @click="changePage('order_offset', 20)"
            >{{ tr("more") }}</BaseButton
          >
        </div>
      </section>
      <section class="space-y-3">
        <h2 class="text-lg font-semibold text-text-default">
          {{ tr("movements") }}
        </h2>
        <p v-if="!data.movements.count" class="text-sm text-text-muted">
          {{ tr("noMovements") }}
        </p>
        <article
          v-for="row in data.movements.results"
          :key="row.id"
          class="space-y-2 rounded-lg border border-border-default p-3"
        >
          <p class="text-sm text-text-default">
            {{ tr(row.kind) }} · {{ row.quantity }} {{ row.size }} ·
            {{ dateText(row.created_at) }}
          </p>
          <p v-if="row.reason" class="text-sm text-text-muted">
            {{ row.reason }}
          </p>
          <form
            v-if="admin && row.kind === 'debit'"
            class="flex flex-wrap gap-2"
            @submit.prevent="
              perform(() => api.reverse(row.id, reasons[row.id]))
            "
          >
            <label class="min-w-0 flex-1 text-sm text-text-default"
              ><span>{{ tr("reason") }}</span
              ><input
                v-model="reasons[row.id]"
                :class="fieldClass"
                required
                maxlength="2000" /></label
            ><BaseButton
              type="submit"
              variant="secondary"
              :disabled="busy"
              :disabled-reason="tr('busy')"
              >{{ tr("reverse") }}</BaseButton
            >
          </form>
        </article>
        <div class="flex gap-2">
          <BaseButton
            v-if="pages.movement_offset"
            variant="secondary"
            @click="changePage('movement_offset', -20)"
            >{{ tr("previous") }}</BaseButton
          ><BaseButton
            v-if="data.movements.count > pages.movement_offset + 20"
            variant="secondary"
            @click="changePage('movement_offset', 20)"
            >{{ tr("more") }}</BaseButton
          >
        </div>
      </section>
      <template v-if="admin"
        ><ExampleEditor :api="api" :language="language" @saved="load" />
        <form
          class="space-y-3 rounded-xl border border-border-default p-4"
          @submit.prevent="saveSettings"
        >
          <h2 class="text-lg font-semibold text-text-default">
            {{ tr("market") }}
          </h2>
          <BaseDropdown :items="markets"
            ><template #trigger
              ><BaseButton variant="secondary">{{
                settings.nationality
              }}</BaseButton></template
            ></BaseDropdown
          ><label class="block space-y-2 text-sm text-text-default"
            ><span>{{ tr("taxRate") }}</span
            ><input
              v-model="settings.tax_rate"
              :class="fieldClass"
              type="number"
              min="0"
              max="100"
              step="0.01"
              required /></label
          ><BaseButton
            type="submit"
            variant="primary"
            :disabled="busy"
            :disabled-reason="tr('busy')"
            >{{ tr("saveSettings") }}</BaseButton
          >
        </form></template
      >
    </template>
  </div>
</template>
