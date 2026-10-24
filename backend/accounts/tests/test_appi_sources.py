"""Appi contract projections expose only the client's visible evidence."""
import pytest
from django.utils import timezone

from accounts.models import ContractAmendment, ProjectContract
from accounts.services import appi_sources
from content.models import Document


pytestmark = pytest.mark.django_db
pytest_plugins = ('accounts.tests.appi_test_support',)


def contract_document(context, title, markdown):
    """Persist a signed live document whose post-signature markdown is untrusted evidence."""
    return Document.objects.create(
        title=title,
        project=context.project,
        client_user=context.actor,
        requires_signature=True,
        signed_by=context.actor,
        signed_at=timezone.now(),
        signature_name='Appi owner',
        is_client_visible=True,
        content_markdown=markdown,
        include_portada=False,
        include_subportada=False,
        include_contraportada=False,
    )


def test_contract_projection_includes_visible_amendment_without_live_draft_text(appi_context):
    """Fails if Appi leaks an invisible/live contract draft or omits a visible amendment from client sources."""
    contract = ProjectContract.objects.create(
        project=appi_context.project,
        key='base-contract',
        title='Visible contract',
        document=contract_document(appi_context, 'Base contract', 'LIVE PRIVATE DRAFT: revised intellectual property'),
        client_visible=True,
    )
    visible = ContractAmendment.objects.create(
        contract=contract,
        key='visible-amendment',
        title='Visible amendment',
        document=contract_document(appi_context, 'Visible amendment document', 'LIVE PRIVATE DRAFT: amendment terms'),
        client_visible=True,
    )
    hidden = ContractAmendment.objects.create(
        contract=contract,
        key='hidden-amendment',
        title='Hidden amendment',
        document=contract_document(appi_context, 'Hidden amendment document', 'INVISIBLE LIVE DRAFT'),
        client_visible=False,
    )

    result = appi_sources.snapshot(
        appi_context.actor,
        appi_context.project.pk,
        {'scenario': 'contract_clause', 'topic': 'intellectual_property', 'explain': False},
        'es',
    )

    source_ids = [source['id'] for source in result['sources']]
    fact_text = '\n'.join(fact['text'] for fact in result['facts'])
    assert f'amendment:{visible.pk}' in source_ids
    assert f'amendment:{hidden.pk}' not in source_ids
    assert 'LIVE PRIVATE DRAFT' not in fact_text
    assert 'No hay un fragmento verificable' in fact_text
