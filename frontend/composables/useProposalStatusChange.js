import { ref } from 'vue';
import { useProposalStore } from '~/stores/proposals';
import { usePanelNotify } from '~/composables/usePanelNotify';
import {
  isNaturalTransition,
  proposalTransitionStatusLabel,
} from '~/utils/proposalStatuses';

/**
 * Shared confirm + PATCH + notify orchestration for proposal status changes
 * (admin mode: any status can be set; the backend fires side effects only on
 * natural transitions).
 *
 * The owning page provides its ConfirmModal via `requestConfirm`
 * (useConfirmModal) and may intercept the natural `negotiating` transition
 * with `onNegotiate` (contract modal), intercept acceptance with `onAccept`
 * (approval review), and offer a resend action on email
 * failures via `resend`.
 *
 * Usage:
 *   const { updatingId, changeStatus } = useProposalStatusChange({
 *     requestConfirm,
 *     onNegotiate: (proposal) => openContractModal(proposal),
 *     resend: (proposalId) => handleResend(proposalId),
 *   });
 *
 * `changeStatus(proposal, newStatus)` returns the store result
 * ({ success, ... }) or `null` when the change was cancelled/intercepted.
 */
export function useProposalStatusChange({ requestConfirm, onNegotiate = null, onAccept = null, resend = null }) {
  const proposalStore = useProposalStore();
  const notify = usePanelNotify();
  const updatingId = ref(null);

  async function confirmChange(proposal, newStatus, natural) {
    if (!natural) {
      let message = `La propuesta pasará de «${proposalTransitionStatusLabel(proposal.status)}» a `
        + `«${proposalTransitionStatusLabel(newStatus)}» fuera del flujo normal. No se enviarán `
        + 'correos ni se ejecutarán automatizaciones.';
      if (proposal.status === 'expired') {
        message += ' Si la fecha de expiración ya pasó, una visita del cliente puede volver a expirarla.';
      }
      return requestConfirm({
        title: 'Forzar cambio de estado',
        message,
        variant: 'warning',
        confirmText: 'Forzar cambio',
      });
    }
    if (newStatus === 'sent') {
      return requestConfirm({
        title: 'Enviar propuesta',
        message: 'Se enviará un email al cliente con el enlace y se programarán recordatorios. ¿Continuar?',
        variant: 'primary',
        confirmText: 'Enviar',
      });
    }
    if (newStatus === 'finished') {
      return requestConfirm({
        title: 'Marcar como finalizada',
        message: 'El proyecto pasará al estado Finalizada y se notificará al cliente por correo. ¿Deseas continuar?',
        variant: 'primary',
        confirmText: 'Marcar como finalizada',
      });
    }
    return true;
  }

  async function changeStatus(proposal, newStatus) {
    if (!proposal || !newStatus || newStatus === proposal.status) return null;

    const natural = isNaturalTransition(proposal, newStatus);

    if (natural && newStatus === 'negotiating' && onNegotiate) {
      onNegotiate(proposal);
      return null;
    }

    const confirmed = await confirmChange(proposal, newStatus, natural);
    if (!confirmed) return null;

    if (newStatus === 'accepted' && onAccept) {
      onAccept(proposal);
      return null;
    }

    updatingId.value = proposal.id;
    try {
      const result = await proposalStore.updateProposalStatus(proposal.id, newStatus);
      if (result.success) {
        const delivery = result.email_delivery;
        if (delivery && delivery.ok === false) {
          notify.warning({
            title: 'Estado actualizado',
            detail: delivery.detail
              || 'No se pudo enviar el correo al cliente. Verifica el correo e intenta reenviar.',
            action: resend ? { label: 'Reenviar', handler: () => resend(proposal.id) } : null,
          });
        } else {
          notify.success({ title: 'Estado actualizado correctamente' });
        }
      } else {
        notify.error({
          title: result?.message || 'No se pudo actualizar el estado',
          detail: result?.hint || '',
        });
      }
      return result;
    } finally {
      updatingId.value = null;
    }
  }

  return { updatingId, changeStatus };
}
