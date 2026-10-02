/**
 * Given a proposal, return the descriptor for the single "next logical action"
 * to show on the right side of the admin editor's sticky action bar. Returns
 * null when no next action is appropriate (terminal states, or draft without
 * a client email).
 *
 * Descriptor shape: { key, label, colorClass }
 *   - key: 'send' | 'negotiate' | 'approve' | 'launch' | 'finish'
 *   - label: button label (Spanish)
 *   - colorClass: Tailwind classes for the button background / hover
 */
export function getProposalNextAction(proposal) {
  if (!proposal) return null;

  const status = proposal.status;
  const transitions = proposal.available_transitions || [];
  const hasEmail = Boolean(proposal.client_email);

  if (status === 'draft') {
    if (!hasEmail) return null;
    return {
      key: 'send',
      label: 'Enviar al Cliente',
      colorClass: 'bg-blue-600 text-white hover:bg-blue-700',
    };
  }

  if (status === 'sent' || status === 'viewed') {
    if (transitions.includes('negotiating')) {
      return {
        key: 'negotiate',
        label: 'Pasar a Negociación',
        colorClass: 'bg-amber-500 text-white hover:bg-amber-600',
      };
    }
    return null;
  }

  if (status === 'negotiating') {
    if (!proposal.platform_onboarding_completed_at) {
      return {
        key: 'launch',
        label: 'Completar revisión',
        colorClass: 'bg-indigo-600 text-white hover:bg-indigo-700',
      };
    }
    if (transitions.includes('accepted')) {
      return {
        key: 'approve',
        label: 'Aprobar',
        colorClass: 'bg-emerald-600 text-white hover:bg-emerald-700',
      };
    }
    return null;
  }

  if (status === 'accepted') {
    if (!proposal.platform_onboarding_completed_at) {
      return {
        key: 'launch',
        label: 'Completar revisión',
        colorClass: 'bg-indigo-600 text-white hover:bg-indigo-700',
      };
    }
    if (transitions.includes('finished')) {
      return {
        key: 'finish',
        label: 'Marcar como finalizada',
        colorClass: 'bg-violet-600 text-white hover:bg-violet-700',
      };
    }
    return null;
  }

  return null;
}
