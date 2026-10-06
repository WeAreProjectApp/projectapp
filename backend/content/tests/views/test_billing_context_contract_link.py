"""Panel billing-context contract source and linking boundaries."""
from django.core.files.base import ContentFile

import pytest

from accounts.models import Deliverable, Project, ProjectContract, ProjectPhase
from content.models import BusinessProposal, Document, ProposalDocument


pytestmark = pytest.mark.django_db


def _project_with_client(make_client_profile):
    profile = make_client_profile(company='Litigio SAS')
    return Project.objects.create(name='Litigio', client=profile.user)


def _proposal_contract(project, profile, superuser):
    deliverable = Deliverable.objects.create(
        project=project,
        title='Contrato del proyecto Litigio',
        uploaded_by=superuser,
    )
    proposal = BusinessProposal.objects.create(
        title='Propuesta Litigio',
        client=profile,
        client_name='Litigio SAS',
        client_email=profile.user.email,
        deliverable=deliverable,
    )
    ProjectPhase.objects.create(
        project=project,
        business_proposal=proposal,
        order=1,
    )
    return ProposalDocument.objects.create(
        proposal=proposal,
        document_type=ProposalDocument.DOC_TYPE_CONTRACT,
        title='Contrato firmado de propuesta',
        file=ContentFile(b'contract', name='litigio-contract.pdf'),
    )


def _link_payload(source_type, source_id, expected_version=0):
    return {
        'source_type': source_type,
        'source_id': source_id,
        'expected_version': expected_version,
        'request_id': f'link-{source_type}-{source_id}-{expected_version}',
    }


def test_options_list_project_document_and_client_proposal_contract_sources(
    super_client, superuser, make_client_profile,
):
    """Falla si el selector oculta contratos reales del proyecto o de su propuesta."""
    project = _project_with_client(make_client_profile)
    direct_contract = Document.objects.create(
        title='Contrato directo Litigio',
        project=project,
        client_user=project.client,
    )
    proposal_contract = _proposal_contract(project, project.client.profile, superuser)

    response = super_client.get(
        f'/api/admin/billing-context/projects/{project.pk}/options/',
    )

    assert response.status_code == 200, response.data
    assert response.data['contract_sources'] == [
        {
            'source_type': 'document',
            'id': direct_contract.pk,
            'title': 'Contrato directo Litigio',
            'origin_label': 'Documento del proyecto',
        },
        {
            'source_type': 'proposal_document',
            'id': proposal_contract.pk,
            'title': 'Contrato firmado de propuesta',
            'origin_label': 'Contrato de propuesta',
        },
    ]


def test_linking_same_document_source_reuses_the_existing_project_contract(
    super_client, make_client_profile,
):
    """Falla si dos intentos para una fuente crean contratos de seguimiento duplicados."""
    project = _project_with_client(make_client_profile)
    source = Document.objects.create(
        title='Contrato para cobro', project=project, client_user=project.client,
    )

    first = super_client.post(
        f'/api/admin/billing-context/projects/{project.pk}/contracts/link/',
        _link_payload('document', source.pk),
        format='json',
    )
    second = super_client.post(
        f'/api/admin/billing-context/projects/{project.pk}/contracts/link/',
        _link_payload('document', source.pk),
        format='json',
    )

    assert first.status_code == 200, first.data
    assert first.data['reused'] is False
    assert ProjectContract.objects.filter(project=project, document=source).count() == 1
    assert second.status_code == 200, second.data
    assert second.data == {
        'id': first.data['id'],
        'title': 'Contrato para cobro',
        'reused': True,
    }


def test_linking_a_foreign_document_returns_400_without_creating_a_contract(
    super_client, make_client_profile,
):
    """Falla si un documento ajeno se puede convertir en contrato facturable del proyecto."""
    project = _project_with_client(make_client_profile)
    other = _project_with_client(make_client_profile)
    source = Document.objects.create(
        title='Contrato de otro cliente', project=other, client_user=other.client,
    )

    response = super_client.post(
        f'/api/admin/billing-context/projects/{project.pk}/contracts/link/',
        _link_payload('document', source.pk),
        format='json',
    )

    assert response.status_code == 400
    assert response.data['detail'] == 'Selecciona un contrato existente de este proyecto y cliente.'
    assert ProjectContract.objects.filter(project=project).count() == 0


def test_linking_an_archived_project_document_returns_400_without_creating_a_contract(
    super_client, make_client_profile,
):
    """Falla si un contrato archivado vuelve a aparecer como fuente facturable."""
    project = _project_with_client(make_client_profile)
    source = Document.objects.create(
        title='Contrato archivado',
        project=project,
        client_user=project.client,
        is_archived=True,
    )

    response = super_client.post(
        f'/api/admin/billing-context/projects/{project.pk}/contracts/link/',
        _link_payload('document', source.pk),
        format='json',
    )

    assert response.status_code == 400
    assert response.data['detail'] == 'Selecciona un contrato existente de este proyecto y cliente.'
    assert ProjectContract.objects.filter(project=project).count() == 0


def test_linking_with_a_stale_delivery_version_leaves_no_contract(
    super_client, make_client_profile,
):
    """Falla si una edición vieja del seguimiento agrega un contrato tras una modificación nueva."""
    project = _project_with_client(make_client_profile)
    source = Document.objects.create(
        title='Contrato desactualizado', project=project, client_user=project.client,
    )
    created = super_client.post(
        f'/api/admin/billing-context/projects/{project.pk}/contracts/link/',
        _link_payload('document', source.pk),
        format='json',
    )
    assert created.status_code == 200, created.data
    second_source = Document.objects.create(
        title='Contrato con versión vieja', project=project, client_user=project.client,
    )

    response = super_client.post(
        f'/api/admin/billing-context/projects/{project.pk}/contracts/link/',
        _link_payload('document', second_source.pk, expected_version=0),
        format='json',
    )

    assert response.status_code == 409
    assert ProjectContract.objects.filter(project=project).count() == 1


def test_linking_a_proposal_contract_preserves_its_source(
    super_client, superuser, make_client_profile,
):
    """Falla si vincular un contrato de propuesta copia el documento o pierde su referencia."""
    project = _project_with_client(make_client_profile)
    source = _proposal_contract(project, project.client.profile, superuser)

    response = super_client.post(
        f'/api/admin/billing-context/projects/{project.pk}/contracts/link/',
        _link_payload('proposal_document', source.pk), format='json',
    )

    assert response.status_code == 200, response.data
    contract = ProjectContract.objects.get(pk=response.data['id'])
    assert contract.proposal_document_id == source.pk
    assert contract.document_id is None


def test_linking_a_source_with_another_client_in_the_same_project_is_rejected(
    super_client, make_client_profile,
):
    """Falla si el límite del proyecto permite facturar el documento de otro cliente."""
    project = _project_with_client(make_client_profile)
    foreign_profile = make_client_profile()
    source = Document.objects.create(
        title='Contrato ajeno', project=project, client_user=foreign_profile.user,
    )

    response = super_client.post(
        f'/api/admin/billing-context/projects/{project.pk}/contracts/link/',
        _link_payload('document', source.pk), format='json',
    )

    assert response.status_code == 400
    assert not ProjectContract.objects.filter(project=project).exists()


def test_client_cannot_register_a_billing_contract(api_client, make_client_profile):
    """Falla si la operación administrativa queda disponible para el cliente."""
    project = _project_with_client(make_client_profile)
    source = Document.objects.create(title='Contrato', project=project)
    api_client.force_authenticate(user=project.client)

    response = api_client.post(
        f'/api/admin/billing-context/projects/{project.pk}/contracts/link/',
        _link_payload('document', source.pk), format='json',
    )

    assert response.status_code == 403
    assert not ProjectContract.objects.filter(project=project).exists()
