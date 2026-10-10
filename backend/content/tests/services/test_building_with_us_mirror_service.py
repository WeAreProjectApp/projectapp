"""Building with Us mirror helpers preserve document-family behavior."""
import pytest

from content.models import Document
from content.services import contract_mirror_service as service

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('state', ['missing', 'unsaved'])
def test_mirror_lookup_requires_a_saved_document(state):
    """Fails if absent or unsaved documents trigger reverse-relation database lookups."""
    document = {'missing': None, 'unsaved': Document(title='Borrador sin guardar')}[state]

    mirror = service.building_with_us_mirror(document)

    assert mirror is None


def test_read_only_message_identifies_building_with_us(initialized_building_with_us_mirror):
    """Fails if alliance mirrors direct operators to the proposals writer."""
    message = service.mirror_read_only_message(initialized_building_with_us_mirror.document)

    assert message == (
        'Este contrato es de sólo lectura y permanece en Contratos. '
        'Su contenido se actualiza mediante el MCP de Building with Us.'
    )


def test_read_only_message_identifies_proposals(initialized_contract_mirrors):
    """Fails if proposal mirrors direct operators to the Building with Us writer."""
    document = initialized_contract_mirrors.mirrors.get(variant='combined').document

    message = service.mirror_read_only_message(document)

    assert message == (
        'Esta plantilla contractual es de solo lectura y permanece en Contratos. '
        'Su contenido se actualiza mediante el MCP de propuestas o la consola del servidor.'
    )


def test_mirror_pdf_refuses_an_empty_artifact(initialized_building_with_us_mirror):
    """Fails if a current mirror with no stored bytes is served as a valid PDF."""
    mirror = initialized_building_with_us_mirror
    mirror.pdf_content = b''
    mirror.save(update_fields=['pdf_content'])

    pdf = service.mirror_pdf(mirror.document)

    assert pdf is None
