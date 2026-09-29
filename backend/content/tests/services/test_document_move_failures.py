"""Per-document error outcomes for rejected document moves."""
import pytest

from content.models import Document, DocumentFolder, DocumentType
from content.services.document_move_service import DocumentMoveError, move_documents

pytestmark = pytest.mark.django_db


@pytest.fixture
def markdown_type():
    return DocumentType.objects.create(code='move-markdown', name='Move Markdown')


@pytest.fixture
def movable_document(markdown_type):
    return Document.objects.create(
        title='Movable document', document_type=markdown_type, content_markdown='# Movable',
    )


@pytest.fixture
def move_target():
    return DocumentFolder.objects.create(name='Move target')


def test_missing_identifier_aborts_the_valid_document(movable_document, move_target, admin_user):
    """Falla si un ID inexistente permite mover otro documento del mismo pedido rechazado."""
    with pytest.raises(DocumentMoveError) as captured:
        move_documents([movable_document.pk, 999999], move_target.pk, actor=admin_user)

    assert captured.value.results == [
        {
            'id': movable_document.pk, 'status': 'aborted', 'moved': False,
            'code': 'batch_aborted', 'message': 'Lote cancelado por errores en otros documentos.',
            'reason': 'Lote cancelado por errores en otros documentos.',
        },
        {
            'id': 999999, 'status': 'failed', 'moved': False,
            'code': 'not_found', 'message': 'El documento no existe.', 'reason': 'El documento no existe.',
        },
    ]
    movable_document.refresh_from_db()
    assert movable_document.folder_id is None


def test_archived_document_reports_its_blocker(movable_document, move_target, admin_user):
    """Falla si un documento archivado oculta el motivo que impide moverlo."""
    movable_document.is_archived = True
    movable_document.save(update_fields=['is_archived', 'updated_at'])

    with pytest.raises(DocumentMoveError) as captured:
        move_documents([movable_document.pk], move_target.pk, actor=admin_user)

    assert captured.value.results[0] == {
        'id': movable_document.pk, 'status': 'failed', 'moved': False,
        'code': 'archived', 'message': 'El documento está archivado.',
        'reason': 'archived', 'move_blockers': ['archived'],
    }
    movable_document.refresh_from_db()
    assert movable_document.folder_id is None


def test_generated_snapshot_reports_its_blocker(movable_document, move_target, admin_user):
    """Falla si una captura generada deja de explicar por qué no admite movimiento."""
    movable_document.generated_file.name = 'documents/generated/snapshot.pdf'
    movable_document.save(update_fields=['generated_file', 'updated_at'])

    with pytest.raises(DocumentMoveError) as captured:
        move_documents([movable_document.pk], move_target.pk, actor=admin_user)

    assert captured.value.results[0] == {
        'id': movable_document.pk, 'status': 'failed', 'moved': False,
        'code': 'not_movable', 'message': 'El documento no admite movimientos.',
        'reason': 'generated_snapshot', 'move_blockers': ['generated_snapshot'],
    }
    movable_document.refresh_from_db()
    assert movable_document.folder_id is None


def test_missing_destination_reports_every_requested_identifier(
    movable_document, markdown_type, admin_user,
):
    """Falla si un destino inexistente omite el resultado de alguno de los documentos pedidos."""
    second_document = Document.objects.create(
        title='Second movable document', document_type=markdown_type, content_markdown='# Second',
    )

    with pytest.raises(DocumentMoveError) as captured:
        move_documents([movable_document.pk, second_document.pk], 999999, actor=admin_user)

    assert captured.value.results == [
        {
            'id': movable_document.pk, 'status': 'failed', 'moved': False,
            'code': 'folder_not_found', 'message': 'La carpeta destino no existe.',
            'reason': 'La carpeta destino no existe.',
        },
        {
            'id': second_document.pk, 'status': 'failed', 'moved': False,
            'code': 'folder_not_found', 'message': 'La carpeta destino no existe.',
            'reason': 'La carpeta destino no existe.',
        },
    ]
    movable_document.refresh_from_db()
    second_document.refresh_from_db()
    assert movable_document.folder_id is None
    assert second_document.folder_id is None


@pytest.mark.parametrize(
    ('actor_state', 'is_active', 'is_staff'),
    [('inactive', False, True), ('non_staff', True, False)],
)
def test_unprivileged_actor_reports_permission_for_every_identifier(
    movable_document, move_target, django_user_model, actor_state, is_active, is_staff,
):
    """Falla si un actor sin permiso devuelve un rechazo genérico sin IDs afectados."""
    actor = django_user_model.objects.create_user(
        username=f'{actor_state}@example.com',
        email=f'{actor_state}@example.com',
        password='pass12345',
        is_staff=is_staff,
        is_active=is_active,
    )

    with pytest.raises(DocumentMoveError) as captured:
        move_documents([movable_document.pk, 999997], move_target.pk, actor=actor)

    assert captured.value.results == [
        {
            'id': movable_document.pk, 'status': 'failed', 'moved': False,
            'code': 'permission_denied', 'message': 'No tienes permiso para mover documentos.',
            'reason': 'No tienes permiso para mover documentos.',
        },
        {
            'id': 999997, 'status': 'failed', 'moved': False,
            'code': 'permission_denied', 'message': 'No tienes permiso para mover documentos.',
            'reason': 'No tienes permiso para mover documentos.',
        },
    ]
    movable_document.refresh_from_db()
    assert movable_document.folder_id is None
