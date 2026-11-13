import { computed, ref, shallowRef } from 'vue';
import { usePanelNotify } from '~/composables/usePanelNotify';
import es from '~/locales/proposalApproval/es';
import en from '~/locales/proposalApproval/en';

/** A single review entry point for table status, card actions and editor launch. */
export function useProposalApproval({ returnFocus = null } = {}) {
  const { locale } = useI18n();
  const notify = usePanelNotify();
  const approvalText = computed(() => locale.value.startsWith('en') ? en : es);
  const approvalProposal = ref(null);
  const approvalAccept = ref(true);
  const approvalReturnFocus = shallowRef(null);
  function openApproval(proposal, accept = true) {
    approvalReturnFocus.value = () => returnFocus?.(proposal);
    approvalProposal.value = proposal;
    approvalAccept.value = accept;
  }
  function approvalCompleted(result) {
    const text = locale.value.startsWith('en') ? en : es;
    notify.success({ title: result.action === 'defer' ? (result.proposal?.status === 'accepted' ? text.accepted : text.reviewDeferred) : text.saved });
  }
  return { approvalText, approvalProposal, approvalAccept, approvalReturnFocus, openApproval, approvalCompleted };
}
