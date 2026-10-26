import { computed } from 'vue';
import es from '~/locales/dashboardAttention/es';
import en from '~/locales/dashboardAttention/en';

export function useDashboardAttentionText() {
  const { locale } = useI18n();
  return computed(() => locale.value.startsWith('en') ? en : es);
}
