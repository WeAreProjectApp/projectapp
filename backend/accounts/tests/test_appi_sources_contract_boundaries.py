"""Contract evidence and visibility boundaries for Appi source projections."""
from hashlib import sha256

import pytest
from content.models import Document
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.utils import timezone

from accounts.models import (
    ContractAmendment,
    ContractSignatureEvidence,
    Project,
    ProjectContract,
    UserProfile,
)
from accounts.services import appi_sources
from accounts.tests.delivery_authoring_helpers import pdf_bytes

pytestmark = pytest.mark.django_db
pytest_plugins = ('accounts.tests.appi_test_support',)


def document_for(project, actor, title, markdown):
    """Persist a client document that can be linked to one contractual node."""
    return Document.objects.create(
        title=title,
        project=project,
        client_user=actor,
        is_client_visible=True,
        content_markdown=markdown,
        include_portada=False,
        include_subportada=False,
        include_contraportada=False,
    )


def contractual_query(entity_id=None):
    """Return the closed contractual question shape used by the source projection."""
    query = {'scenario': 'contract_clause', 'topic': 'confidentiality', 'explain': False}
    if entity_id is not None:
        query['entity_id'] = entity_id
    return query


def test_contract_clause_uses_the_preserved_signed_evidence(appi_context):
    """Fails if live contract markdown replaces an available signed contractual artifact."""
    contract = ProjectContract.objects.create(
        project=appi_context.project,
        key='signed-contract',
        title='Signed confidentiality contract',
        document=document_for(appi_context.project, appi_context.actor, 'Live contract', 'LIVE DRAFT MUST NOT APPEAR'),
        client_visible=True,
    )
    body = pdf_bytes('Confidentiality obligations remain in force.')
    ContractSignatureEvidence.objects.create(
        contract=contract,
        file=ContentFile(body, name='signed-contract.pdf'),
        sha256=sha256(body).hexdigest(),
        signer_name='Appi owner',
        signed_at=timezone.now(),
        attestation='External signature verified.',
        attested_by=appi_context.actor,
        source_snapshot={'title': 'Signed confidentiality contract'},
    )

    result = appi_sources.snapshot(
        appi_context.actor,
        appi_context.project.pk,
        contractual_query(f'contract:{contract.pk}'),
        'es',
    )

    facts = '\n'.join(item['text'] for item in result['facts'])
    assert 'Confidentiality obligations remain in force.' in facts
    assert 'LIVE DRAFT MUST NOT APPEAR' not in facts


def test_contract_clause_rejects_a_document_linked_to_another_project(appi_context):
    """Fails if a cross-project document is extracted as a clause for the current client."""
    other = get_user_model().objects.create_user('contract-other', email='contract-other@appi.test')
    UserProfile.objects.update_or_create(user=other, defaults={'role': UserProfile.ROLE_CLIENT})
    foreign_project = Project.objects.create(client=other, name='Foreign contract project')
    incompatible = document_for(foreign_project, other, 'Foreign contract', 'FOREIGN CONFIDENTIALITY CONTENT')
    contract = ProjectContract.objects.create(
        project=appi_context.project,
        key='incompatible-document',
        title='Incompatible document contract',
        document=incompatible,
        client_visible=True,
    )

    result = appi_sources.snapshot(
        appi_context.actor,
        appi_context.project.pk,
        contractual_query(f'contract:{contract.pk}'),
        'es',
    )

    facts = '\n'.join(item['text'] for item in result['facts'])
    assert 'FOREIGN CONFIDENTIALITY CONTENT' not in facts
    assert 'No hay un fragmento verificable' in facts


def test_contract_catalog_keeps_only_authorized_visible_nodes(appi_context):
    """Fails if hidden amendments or another client's contract enter the contractual catalog."""
    visible = ProjectContract.objects.create(
        project=appi_context.project,
        key='visible-contract',
        title='Visible contract',
        document=document_for(appi_context.project, appi_context.actor, 'Visible contract document', 'Visible terms'),
        client_visible=True,
    )
    amendment = ContractAmendment.objects.create(
        contract=visible,
        key='visible-amendment',
        title='Visible amendment',
        document=document_for(appi_context.project, appi_context.actor, 'Visible amendment document', 'Visible amendment terms'),
        client_visible=True,
    )
    hidden = ContractAmendment.objects.create(
        contract=visible,
        key='hidden-amendment',
        title='Hidden amendment',
        document=document_for(appi_context.project, appi_context.actor, 'Hidden amendment document', 'Hidden terms'),
        client_visible=False,
    )
    other = get_user_model().objects.create_user('catalog-other', email='catalog-other@appi.test')
    UserProfile.objects.update_or_create(user=other, defaults={'role': UserProfile.ROLE_CLIENT})
    foreign_project = Project.objects.create(client=other, name='Foreign project')
    foreign = ProjectContract.objects.create(
        project=foreign_project,
        key='foreign-contract',
        title='Foreign contract',
        document=document_for(foreign_project, other, 'Foreign document', 'Foreign terms'),
        client_visible=True,
    )

    result = appi_sources.snapshot(
        appi_context.actor,
        appi_context.project.pk,
        contractual_query(),
        'es',
    )

    candidate_ids = {item['id'] for item in result['candidates']}
    source_ids = {item['id'] for item in result['sources']}
    assert candidate_ids == {f'contract:{visible.pk}', f'amendment:{amendment.pk}'}
    assert source_ids == {f'contract:{visible.pk}', f'amendment:{amendment.pk}'}
    assert f'amendment:{hidden.pk}' not in candidate_ids
    assert f'contract:{foreign.pk}' not in candidate_ids


def test_contract_entity_selection_returns_only_the_visible_amendment(appi_context):
    """Fails if the selected amendment's answer includes its parent contract's facts or sources."""
    contract = ProjectContract.objects.create(
        project=appi_context.project,
        key='selected-contract',
        title='Parent contract',
        document=document_for(appi_context.project, appi_context.actor, 'Parent document', 'Parent terms'),
        client_visible=True,
    )
    amendment = ContractAmendment.objects.create(
        contract=contract,
        key='selected-amendment',
        title='Selected amendment',
        document=document_for(appi_context.project, appi_context.actor, 'Selected amendment document', 'Selected terms'),
        client_visible=True,
    )

    result = appi_sources.snapshot(
        appi_context.actor,
        appi_context.project.pk,
        contractual_query(f'amendment:{amendment.pk}'),
        'es',
    )

    assert result['sources'] == [{
        'id': f'amendment:{amendment.pk}',
        'label': 'Selected amendment',
        'href': f'/platform/projects/{appi_context.project.pk}/delivery',
    }]
    facts = '\n'.join(item['text'] for item in result['facts'])
    assert 'Selected amendment' in facts
    assert 'Parent contract' not in facts
