import { config } from '@vue/test-utils';
import BaseButton from '../components/base/BaseButton.vue';
import BaseActionButton from '../components/base/BaseActionButton.vue';
import BaseActionIcon from '../components/base/BaseActionIcon.vue';
import BaseControlGate from '../components/base/BaseControlGate.vue';
import BaseFormRow from '../components/base/BaseFormRow.vue';
import BaseMobileTabSelect from '../components/base/BaseMobileTabSelect.vue';
import BaseModalActions from '../components/base/BaseModalActions.vue';

if (typeof globalThis.structuredClone === 'undefined') {
  globalThis.structuredClone = (obj) => JSON.parse(JSON.stringify(obj));
}

// Nuxt auto-imports everything under components/, so a component that renders
// <BaseButton> resolves it for free in the app. Jest has no such mechanism:
// without this, BaseButton silently renders as an unresolved component and any
// findAll('button') in a spec comes back empty. Registering it globally keeps
// specs honest as buttons migrate to the design system. Specs that register it
// locally still win — local components take precedence over global ones.
// BaseFormRow is here for the same reason, and because it provides the bands
// its BaseFormFields inject: unresolved, the fields would silently fall back to
// stacking and a spec could not tell an aligned row from a crooked one.
// BaseMobileTabSelect renders the mobile <select> of every tab control, so
// unresolved it would take the only <select> out of the DOM and the specs that
// drive a tab strip through `get('select')` would fail to find it.
config.global.components = {
  ...config.global.components,
  BaseActionButton,
  BaseActionIcon,
  BaseButton,
  BaseControlGate,
  BaseFormRow,
  BaseMobileTabSelect,
  BaseModalActions,
};
