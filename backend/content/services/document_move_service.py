"""Atomic moves with the same serializer rules as the document editor."""

from content.mcp.errors import normalize_error
from content.models import Document, DocumentFolder
from content.serializers.document import DocumentCreateUpdateSerializer
from content.services.document_ownership_planner import (
    OwnershipPlanError,
    apply_ownership_plan,
)
from content.services.document_write_service import (
    document_write_payload,
    movement_blockers,
)
from django.db import DatabaseError, transaction


class DocumentMoveError(ValueError):
    def __init__(self, results):
        super().__init__("No se movió ningún documento: el lote contiene errores.")
        self.results = results


def _failure(pk, code, message, **details):
    return {'id': pk, 'status': 'failed', 'moved': False, 'code': code,
            'message': message, 'reason': details.pop('reason', message), **details}


def _policy_results(document_ids, plan, *, include_content=False, applied=False):
    rows = {row['id']: row for row in plan['rows'] if row['resource_type'] == 'document'}
    documents = {doc.pk: doc for doc in Document.objects.filter(pk__in=document_ids).select_related('folder', 'document_type')}
    results = []
    for pk in document_ids:
        row = rows[pk]
        common = {'before': row['before'], 'after': row['after']}
        if applied:
            moved = row['before'] != row['after']
            results.append({'id': pk, 'status': 'moved' if moved else 'unchanged',
                            'moved': moved, **common,
                            'document': document_write_payload(documents[pk], include_content=include_content)})
        elif row['blockers']:
            blocker = row['blockers'][0]
            results.append(_failure(pk, blocker['code'], blocker['message'], **common,
                                    reason=', '.join(item['code'] for item in row['blockers']),
                                    move_blockers=[item['code'] for item in row['blockers']]))
        else:
            results.append({'id': pk, 'status': 'aborted', 'moved': False, **common,
                            'code': 'batch_aborted', 'message': 'Lote cancelado por errores en otros documentos.',
                            'reason': 'Lote cancelado por errores en otros documentos.'})
    return results


def _policy_move(document_ids, folder_id, *, actor, include_content, client_policy, portal_policy, expected_plan_hash, document_decisions):
    try:
        plan = apply_ownership_plan({
            'document_ids': document_ids, 'destination_folder_id': folder_id,
            'client_policy': client_policy, 'portal_policy': portal_policy,
            'document_decisions': document_decisions,
        }, actor=actor, expected_plan_hash=expected_plan_hash)
    except OwnershipPlanError as exc:
        results = (_policy_results(document_ids, exc.plan) if exc.plan is not None else [
            {'id': pk, 'status': 'aborted', 'moved': False, 'code': exc.code,
             'message': str(exc.detail['detail']), 'before': {}, 'after': {}}
            for pk in document_ids
        ])
        exc.details['results'] = results
        exc.detail['results'] = results
        raise
    except DatabaseError as exc:
        raise DocumentMoveError([_failure(pk, 'write_failed', 'No se pudo guardar el movimiento; no se modificó ningún documento.') for pk in document_ids]) from exc
    return {'ok': True, 'results': _policy_results(document_ids, plan, include_content=include_content, applied=True),
            'plan_hash': plan['plan_hash'], 'warnings': plan['warnings']}


@transaction.atomic
def move_documents(document_ids, folder_id, *, actor, include_content=False, client_policy=None,
                   portal_policy='abort', expected_plan_hash=None, document_decisions=()):
    if not actor or not actor.is_active or not actor.is_staff:
        raise DocumentMoveError([_failure(pk, "permission_denied", "No tienes permiso para mover documentos.") for pk in document_ids])
    if client_policy is not None:
        return _policy_move(document_ids, folder_id, actor=actor, include_content=include_content,
                            client_policy=client_policy, portal_policy=portal_policy,
                            expected_plan_hash=expected_plan_hash, document_decisions=document_decisions)
    documents = {
        doc.pk: doc
        for doc in Document.objects.select_for_update()
        .filter(
            pk__in=document_ids,
        )
        .order_by("pk")
    }
    target = None
    if folder_id is not None:
        target = DocumentFolder.objects.select_for_update().filter(pk=folder_id).first()
    target_error = None
    if folder_id is not None and target is None:
        target_error = ('folder_not_found', 'La carpeta destino no existe.')
    elif target and target.is_archived:
        target_error = ('folder_archived', 'La carpeta destino está archivada.')
    elif target and target.is_system_managed:
        target_error = ('folder_not_movable', 'La carpeta destino está administrada por el sistema.')
    results, validated = [], {}
    for pk in document_ids:
        document = documents.get(pk)
        blockers = movement_blockers(document) if document else []
        if document is None:
            results.append(_failure(pk, 'not_found', 'El documento no existe.'))
            continue
        if blockers:
            code = 'archived' if document.is_archived else 'not_movable'
            message = 'El documento está archivado.' if document.is_archived else 'El documento no admite movimientos.'
            results.append(_failure(pk, code, message, reason=', '.join(blockers), move_blockers=blockers))
            continue
        if target_error:
            results.append(_failure(pk, *target_error))
            continue
        serializer = DocumentCreateUpdateSerializer(
            document,
            data={"folder_id": folder_id},
            partial=True,
        )
        if not serializer.is_valid():
            message, _code, details = normalize_error(serializer.errors)
            results.append(_failure(pk, 'not_movable', message, reason=serializer.errors, errors=details.get('errors', [])))
            continue
        validated[pk] = serializer
        results.append({"id": pk, "status": "pending", "moved": False})
    if any(result["status"] == "failed" for result in results):
        for result in results:
            if result["status"] == "pending":
                result.update(
                    status="aborted",
                    code="batch_aborted",
                    message="Lote cancelado por errores en otros documentos.",
                    reason="Lote cancelado por errores en otros documentos.",
                )
        raise DocumentMoveError(results)
    try:
        with transaction.atomic():
            for result in results:
                document = documents[result["id"]]
                changed = document.folder_id != folder_id
                if changed:
                    document = validated[document.pk].save(updated_by=actor)
                result.update(
                    status="moved" if changed else "unchanged",
                    moved=changed,
                    document=document_write_payload(
                        document, include_content=include_content
                    ),
                )
    except DatabaseError as exc:
        failed_id = result["id"]
        for row in results:
            row.pop("document", None)
            row.update(
                status="failed" if row["id"] == failed_id else "aborted",
                moved=False,
                code="write_failed" if row["id"] == failed_id else "batch_aborted",
                message="No se pudo guardar el movimiento; no se modificó ningún documento.",
                reason="No se pudo guardar el movimiento; no se modificó ningún documento.",
            )
        raise DocumentMoveError(results) from exc
    return {"ok": True, "results": results}
