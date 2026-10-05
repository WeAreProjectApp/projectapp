"""Negative service behavior for versioned default contract templates."""
import pytest

from content.models import ContractTemplateVersion
from content.services import contract_template_service
from content.services.contract_template_validation import ContractTemplateError

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ('offset', 'limit'),
    [
        (-1, 20),
        (0, 0),
        (True, 20),
    ],
)
def test_list_versions_rejects_invalid_pagination(coherent_template, offset, limit):
    """Falla si la historia permite offset negativo, límite vacío o booleanos como enteros."""
    with pytest.raises(ContractTemplateError, match='offset >= 0'):
        contract_template_service.list_versions('combined', offset=offset, limit=limit)


def test_preview_rejects_a_non_object_update_request(coherent_template):
    """Falla si el servicio intenta interpretar una lista como una actualización contractual."""
    with pytest.raises(ContractTemplateError, match='deben ser un objeto'):
        contract_template_service.prepare_update([])


def test_preview_rejects_an_unknown_variant(coherent_template):
    """Falla si una actualización puede apuntar a un contrato que no existe."""
    with pytest.raises(ContractTemplateError, match='variant debe ser'):
        contract_template_service.prepare_update({
            'variant': 'legacy', 'markdown': 'Texto',
        })


def test_preview_rejects_blank_markdown(coherent_template):
    """Falla si una plantilla vacía llega a invalidar el contrato predeterminado."""
    with pytest.raises(ContractTemplateError, match='markdown debe ser texto'):
        contract_template_service.prepare_update({
            'variant': 'combined', 'markdown': '   ',
        })


def test_preview_rejects_an_unknown_top_level_argument(coherent_template):
    """Falla si un cliente puede colar datos fuera del contrato de actualización."""
    with pytest.raises(ContractTemplateError, match='argumentos desconocidos'):
        contract_template_service.prepare_update({
            'variant': 'combined',
            'markdown': contract_template_service.read_template('combined')['markdown'],
            'unexpected': 'value',
        })


@pytest.mark.parametrize(
    'related_updates',
    [
        'product',
        [{}, {}, {}],
        ['product'],
    ],
)
def test_preview_rejects_a_malformed_related_updates_collection(
    coherent_template, related_updates,
):
    """Falla si un lote coordinado no contiene hasta dos objetos de variantes."""
    with pytest.raises(ContractTemplateError, match='related_updates admite'):
        contract_template_service.prepare_update({
            'variant': 'combined',
            'markdown': contract_template_service.read_template('combined')['markdown'],
            'related_updates': related_updates,
        })


def test_preview_rejects_an_unknown_related_update_argument(coherent_template):
    """Falla si una variante relacionada acepta atributos fuera de su contrato público."""
    with pytest.raises(ContractTemplateError, match='desconocidos en related_updates'):
        contract_template_service.prepare_update({
            'variant': 'combined',
            'markdown': contract_template_service.read_template('combined')['markdown'],
            'related_updates': [{'variant': 'product', 'markdown': 'texto', 'extra': True}],
        })


def test_preview_rejects_a_duplicate_variant_in_coordinated_updates(coherent_template):
    """Falla si un lote intenta aplicar dos textos distintos a la misma variante."""
    current = contract_template_service.read_template('combined')['markdown']

    with pytest.raises(ContractTemplateError, match='No repitas variantes'):
        contract_template_service.prepare_update({
            'variant': 'combined', 'markdown': current,
            'related_updates': [{'variant': 'combined', 'markdown': current}],
        })


def test_preview_requires_exactly_one_text_source_per_variant(coherent_template):
    """Falla si una variante mezcla Markdown completo con parches en la misma revisión."""
    current = contract_template_service.read_template('combined')['markdown']

    with pytest.raises(ContractTemplateError, match='exactamente uno de markdown o patches'):
        contract_template_service.prepare_update({
            'variant': 'combined', 'markdown': current,
            'patches': [{'operation': 'replace', 'text': 'CONTRATO', 'markdown': 'CONTRATO'}],
        })


def test_restore_rejects_a_non_positive_version_id(coherent_template):
    """Falla si restaurar acepta una versión cero que no puede existir en el historial."""
    with pytest.raises(ContractTemplateError, match='entero positivo'):
        contract_template_service.prepare_update(
            {'variant': 'combined', 'version_id': 0}, restore=True,
        )


def test_restore_requires_a_primary_version_id(coherent_template):
    """Falla si restaurar intenta convertir Markdown en una restauración sin versión fuente."""
    with pytest.raises(ContractTemplateError, match='version_id es obligatorio'):
        contract_template_service.prepare_update(
            {
                'variant': 'combined',
                'markdown': contract_template_service.read_template('combined')['markdown'],
            },
            restore=True,
        )


def test_restore_rejects_a_revision_belonging_to_another_variant(coherent_template):
    """Falla si un ID de historial de producto puede restaurar el contrato combinado."""
    product_revision = ContractTemplateVersion.objects.get(
        template=coherent_template, variant='product', version=1,
    )

    with pytest.raises(ContractTemplateError) as exc_info:
        contract_template_service.prepare_update(
            {'variant': 'combined', 'version_id': product_revision.pk}, restore=True,
        )

    assert exc_info.value.code == 'NOT_FOUND'


def test_sensitive_update_requires_a_meaningful_change_note(coherent_template):
    """Falla si una actualización confirmable no deja una justificación auditable."""
    current = contract_template_service.read_template('combined')

    with pytest.raises(ContractTemplateError, match='change_note'):
        contract_template_service.prepare_update(
            {
                'variant': 'combined', 'markdown': current['markdown'],
                'if_match': current['etag'], 'change_note': '   ',
            },
            require_match=True,
        )


def test_apply_rejects_an_unavailable_mirror_without_creating_a_revision(
    initialized_contract_mirrors, superuser,
):
    """Falla si un espejo fuera de Contratos permite persistir una plantilla sin sincronizar."""
    current = contract_template_service.read_template('service')
    mirror = initialized_contract_mirrors.mirrors.get(variant='service')
    version_count = ContractTemplateVersion.objects.filter(
        template=initialized_contract_mirrors, variant='service',
    ).count()
    mirror.document.folder = None
    mirror.document.save(update_fields=['folder'])

    with pytest.raises(ContractTemplateError) as exc_info:
        contract_template_service.apply_update(
            {
                'variant': 'service', 'markdown': current['markdown'] + '\n',
                'if_match': current['etag'], 'change_note': 'No debe persistir.',
            },
            actor=superuser,
        )

    assert exc_info.value.code == 'MIRROR_SYNC_FAILED'
    assert exc_info.value.details['applied'] is False
    assert ContractTemplateVersion.objects.filter(
        template=initialized_contract_mirrors, variant='service',
    ).count() == version_count
    assert contract_template_service.read_template('service')['markdown'] == current['markdown']


def test_noop_update_preserves_the_current_mirror_snapshot(
    initialized_contract_mirrors, superuser,
):
    """Falla si reenviar el texto vigente crea una revisión huérfana o cambia el espejo."""
    current = contract_template_service.read_template('combined')
    mirror = initialized_contract_mirrors.mirrors.get(variant='combined')
    old_versions = ContractTemplateVersion.objects.filter(
        template=initialized_contract_mirrors, variant='combined',
    ).count()
    old_pdf = bytes(mirror.pdf_content)
    old_notes = mirror.document.document_notes.count()

    result = contract_template_service.apply_update(
        {
            'variant': 'combined', 'markdown': current['markdown'],
            'if_match': current['etag'], 'change_note': 'Revisión sin cambios.',
        },
        actor=superuser,
    )

    mirror.refresh_from_db()
    assert result['results'] == [{
        'variant': 'combined', 'changed': False, 'version': 1, 'document_id': mirror.document_id,
    }]
    assert ContractTemplateVersion.objects.filter(
        template=initialized_contract_mirrors, variant='combined',
    ).count() == old_versions
    assert bytes(mirror.pdf_content) == old_pdf
    assert mirror.document.document_notes.count() == old_notes


def test_console_update_rejects_a_service_obligation_inconsistent_with_combined(
    initialized_contract_mirrors, superuser,
):
    """Falla si la consola guarda una obligación de servicio distinta del contrato combinado."""
    current = contract_template_service.read_template('service')
    version_count = ContractTemplateVersion.objects.filter(
        template=initialized_contract_mirrors, variant='service',
    ).count()
    heading = '## CLÁUSULA NOVENA — CONFIDENCIALIDAD Y NO CIRCUNVENCIÓN'
    changed_markdown = current['markdown'].replace(
        heading,
        heading + '\n\nEL CONTRATISTA deberá conservar una copia adicional por cinco (5) años.',
        1,
    )

    with pytest.raises(ContractTemplateError) as exc_info:
        contract_template_service.apply_update(
            {
                'variant': 'service', 'markdown': changed_markdown,
                'if_match': current['etag'], 'change_note': 'Obligación no coordinada.',
            },
            actor=superuser,
        )

    assert exc_info.value.code == 'TEMPLATES_INCONSISTENT'
    assert contract_template_service.read_template('service')['markdown'] == current['markdown']
    assert ContractTemplateVersion.objects.filter(
        template=initialized_contract_mirrors, variant='service',
    ).count() == version_count
