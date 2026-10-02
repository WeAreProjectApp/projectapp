import { computed, ref } from 'vue';
import { usePanelNotify } from '~/composables/usePanelNotify';
import es from '~/locales/proposalApproval/es';
import en from '~/locales/proposalApproval/en';

/** A single review entry point for table status, card actions and editor launch. */
export function useProposalApproval() {
  const { locale } = useI18n();
  const notify = usePanelNotify();
  const approvalText = computed(() => locale.value.startsWith('en') ? en : es);
  const approvalProposal = ref(null);
  const approvalAccept = ref(true);
  function openApproval(proposal, accept = true) {
    approvalProposal.value = proposal;
    approvalAccept.value = accept;
  }
  function approvalCompleted(result) {
    const text = locale.value.startsWith('en') ? en : es;
    notify.success({ title: result.action === 'defer' ? (result.proposal?.status === 'accepted' ? text.accepted : text.reviewDeferred) : text.saved });
  }
  return { approvalText, approvalProposal, approvalAccept, openApproval, approvalCompleted };
}
