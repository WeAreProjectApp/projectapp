"""Read-only choices for linking hosting while preparing a collection account."""


def hosting_selection(inventory):
    """Explain when one explicit choice is sufficient; never infer identities."""
    hosting = inventory['hosting'] or {}
    sources = inventory['accounting_sources']
    hosting_id = hosting.get('id')
    operational_id = hosting.get('operational_record_id')
    pending = [row for row in sources if row['mapped_hosting_id'] != hosting_id or not hosting_id]
    blockers = []
    for row in sources:
        conflicts = list(row['conflicts'])
        if row['mapped_hosting_id'] and row['mapped_hosting_id'] != hosting_id:
            conflicts.append('El registro está asociado al hosting de otro proyecto.')
        if conflicts:
            blockers.append({'code': 'source_conflict', 'record_id': row['id'],
                             'message': f"Hosting #{row['id']}: {' '.join(conflicts)} Corrige sus referencias antes de vincularlo."})
    if any(row['id'] != hosting.get('subscription_id') for row in inventory['subscriptions']):
        blockers.append({'code': 'subscription_pending',
                         'message': 'Falta confirmar la suscripción que corresponde al hosting del proyecto.'})
    if len(pending) > 1:
        blockers.append({'code': 'multiple_pending_sources',
                         'message': 'Hay varios registros de hosting pendientes. Revisa cuáles representan el servicio y cuál se usará para cobrar.'})
    if pending and operational_id and any(row['id'] != operational_id for row in pending):
        blockers.append({'code': 'operational_change',
                         'message': 'El proyecto ya tiene un hosting para cobrar y hay otro registro pendiente. Revisa su relación antes de cambiarlo.'})
    if len(sources) > 1 and not operational_id:
        blockers.append({'code': 'operational_missing',
                         'message': 'Falta elegir cuál de los registros asociados se usará para cobrar.'})
    candidates = []
    for row in sources:
        historical = bool(operational_id and row['id'] != operational_id)
        candidates.append({
            'hosting_record_id': row['id'], 'project_hosting_id': hosting_id,
            'domain_url': row['domain_url'], 'payment_modality': row['payment_modality'],
            'is_active': row['is_active'],
            'requires_association': row['mapped_hosting_id'] != hosting_id or not operational_id,
            'selectable': not blockers and not historical,
            'historical': historical,
        })
    # A subscription-only hosting is a real identity too; an empty administrative
    # container is not a hosting service the operator can recognize or bill.
    if not sources and hosting.get('subscription_id'):
        subscription = next((row for row in inventory['subscriptions'] if row['id'] == hosting['subscription_id']), {})
        candidates.append({'hosting_record_id': None, 'project_hosting_id': hosting_id,
                           'domain_url': '', 'payment_modality': subscription.get('plan', ''),
                           'is_active': subscription.get('status') == 'active',
                           'requires_association': False, 'selectable': not blockers, 'historical': False})
    return {'candidates': candidates, 'blockers': blockers,
            'can_create': not sources and not inventory['subscriptions'] and not hosting.get('subscription_id'),
            'requires_reconciliation': bool(blockers), 'version': inventory['version']}
