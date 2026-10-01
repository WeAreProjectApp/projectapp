from decimal import Decimal
from unittest.mock import patch

import pytest

from accounts.models import Project, ProjectContract
from content.models import Document, DocumentCollectionAccount
from content.services.document_type_codes import COLLECTION_ACCOUNT
from content.services.document_type_utils import get_collection_account_document_type


def project_context(project):
    """Select an actual contract explicitly in project-account test inputs."""
    contract = ProjectContract.objects.filter(project=project, key='billing-test').first()
    if contract is None:
        source = Document.objects.create(title='Billing contract', project=project, client_user=project.client)
        contract = ProjectContract.objects.create(project=project, key='billing-test', title='Billing contract', document=source)
    return {'billing_nature': 'contract', 'contract_id': contract.pk}


@pytest.mark.django_db
def test_admin_creates_collection_account_draft(api_client, admin_headers, project):
    resp = api_client.post(
        '/api/accounts/collection-accounts/',
        {
            'title': 'Invoice one',
            'project_id': project.id, **project_context(project),
            'payment_term_days': 15,
        },
        format='json',
        **admin_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data['commercial_status'] == 'draft'
    assert data['document_type']['code'] == COLLECTION_ACCOUNT


@pytest.mark.django_db
def test_client_list_excludes_draft_collection_accounts(
    api_client, admin_headers, client_headers, project,
):
    api_client.post(
        '/api/accounts/collection-accounts/',
        {'title': 'Hidden draft', 'project_id': project.id, **project_context(project)},
        format='json',
        **admin_headers,
    )
    resp = api_client.get('/api/accounts/collection-accounts/', **client_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.django_db
def test_issue_then_client_sees_account(
    api_client, admin_headers, client_headers, project,
):
    create = api_client.post(
        '/api/accounts/collection-accounts/',
        {'title': 'Issued doc', 'project_id': project.id, **project_context(project), 'payment_term_days': 5},
        format='json',
        **admin_headers,
    )
    assert create.status_code == 201
    aid = create.json()['id']

    patch = api_client.patch(
        f'/api/accounts/collection-accounts/{aid}/',
        {
            'items': [
                {
                    'description': 'Dev milestone',
                    'quantity': '1',
                    'unit_price': '100000.00',
                    'discount_amount': '0',
                    'tax_amount': '0',
                    'line_total': '100000.00',
                },
            ],
        },
        format='json',
        **admin_headers,
    )
    assert patch.status_code == 200

    issue = api_client.post(
        f'/api/accounts/collection-accounts/{aid}/issue/',
        format='json',
        **admin_headers,
    )
    assert issue.status_code == 200
    assert issue.json()['commercial_status'] == 'issued'
    assert issue.json()['public_number']

    lst = api_client.get('/api/accounts/collection-accounts/', **client_headers)
    assert len(lst.json()) == 1
    assert lst.json()[0]['id'] == aid


@pytest.mark.django_db
def test_client_cannot_patch_collection_account(
    api_client, admin_headers, client_headers, project,
):
    create = api_client.post(
        '/api/accounts/collection-accounts/',
        {'title': 'Doc', 'project_id': project.id, **project_context(project)},
        format='json',
        **admin_headers,
    )
    aid = create.json()['id']
    api_client.post(
        f'/api/accounts/collection-accounts/{aid}/issue/',
        format='json',
        **admin_headers,
    )
    resp = api_client.patch(
        f'/api/accounts/collection-accounts/{aid}/',
        {'title': 'Hacked'},
        format='json',
        **client_headers,
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_mark_paid_from_issued(api_client, admin_headers, project):
    create = api_client.post(
        '/api/accounts/collection-accounts/',
        {'title': 'Pay me', 'project_id': project.id, **project_context(project)},
        format='json',
        **admin_headers,
    )
    aid = create.json()['id']
    api_client.post(
        f'/api/accounts/collection-accounts/{aid}/issue/',
        format='json',
        **admin_headers,
    )
    resp = api_client.post(
        f'/api/accounts/collection-accounts/{aid}/mark-paid/',
        format='json',
        **admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()['commercial_status'] == 'paid'


@pytest.mark.django_db
def test_commercial_is_overdue_derived(project, client_user):
    dt = get_collection_account_document_type()
    doc = Document.objects.create(
        title='Overdue test',
        document_type=dt,
        commercial_status=Document.CommercialStatus.ISSUED,
        project=project,
        client_user=client_user,
        due_date='2020-01-01',
        total=Decimal('1'),
    )
    DocumentCollectionAccount.objects.create(document=doc)
    from content.services.collection_account_service import commercial_is_overdue

    assert commercial_is_overdue(doc) is True


@pytest.mark.django_db
def test_get_collection_account_detail_returns_404_for_unknown_id(api_client, admin_headers):
    resp = api_client.get(
        '/api/accounts/collection-accounts/999999/',
        **admin_headers,
    )

    assert resp.status_code == 404


@pytest.mark.django_db
def test_get_collection_account_pdf_returns_pdf_attachment_when_issued(
    api_client, admin_headers, project, settings, tmp_path,
):
    settings.MEDIA_ROOT = tmp_path
    create = api_client.post(
        '/api/accounts/collection-accounts/',
        {'title': 'PDF doc', 'project_id': project.id, **project_context(project)},
        format='json',
        **admin_headers,
    )
    aid = create.json()['id']
    issued = api_client.post(
        f'/api/accounts/collection-accounts/{aid}/issue/',
        format='json',
        **admin_headers,
    )

    document = Document.objects.get(pk=aid)
    with document.generated_file.open('rb') as archived_file:
        archived_pdf = archived_file.read()
    with patch(
        'content.services.collection_account_pdf_service'
        '.CollectionAccountPdfService.generate',
        side_effect=AssertionError('issued PDF must come from storage'),
    ) as generate:
        resp = api_client.get(
            f'/api/accounts/collection-accounts/{aid}/pdf/',
            **admin_headers,
        )

    assert resp.status_code == 200
    assert resp['Content-Type'] == 'application/pdf'
    assert resp.content == archived_pdf
    generate.assert_not_called()
    # The client saves the file under the consecutivo, exactly as the panel and
    # the email attachment name it — not a lowercased slug of it.
    public_number = issued.json()['public_number']
    assert public_number
    assert resp['Content-Disposition'] == (
        f'attachment; filename="{public_number}.pdf"'
    )


@pytest.mark.django_db
def test_issue_collection_account_returns_400_when_no_issuer_profile_exists(
    api_client, admin_headers, project,
):
    from content.models import IssuerProfile

    IssuerProfile.objects.all().delete()
    create = api_client.post(
        '/api/accounts/collection-accounts/',
        {'title': 'No issuer', 'project_id': project.id, **project_context(project)},
        format='json',
        **admin_headers,
    )
    aid = create.json()['id']

    resp = api_client.post(
        f'/api/accounts/collection-accounts/{aid}/issue/',
        format='json',
        **admin_headers,
    )

    assert resp.status_code == 400
    assert 'issuer' in resp.json()['detail'].lower()


@pytest.mark.django_db
def test_client_post_collection_account_returns_403(api_client, client_headers, project):
    resp = api_client.post(
        '/api/accounts/collection-accounts/',
        {'title': 'Blocked', 'project_id': project.id, **project_context(project)},
        format='json',
        **client_headers,
    )

    assert resp.status_code == 403


@pytest.mark.django_db
def test_admin_list_collection_accounts_filters_by_project_id_query_param(
    api_client, admin_headers, project,
):
    other = Project.objects.create(
        name='Other CA project',
        client=project.client,
        status=Project.STATUS_ACTIVE,
        progress=0,
    )
    api_client.post(
        '/api/accounts/collection-accounts/',
        {'title': 'On target project', 'project_id': project.id, **project_context(project)},
        format='json',
        **admin_headers,
    )
    api_client.post(
        '/api/accounts/collection-accounts/',
        {'title': 'On other project', 'project_id': other.id, **project_context(other)},
        format='json',
        **admin_headers,
    )

    resp = api_client.get(
        f'/api/accounts/collection-accounts/?project_id={project.id}',
        **admin_headers,
    )

    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]['title'] == 'On target project'


@pytest.mark.django_db
def test_client_get_pdf_for_draft_collection_account_returns_404(
    api_client, admin_headers, client_headers, project,
):
    create = api_client.post(
        '/api/accounts/collection-accounts/',
        {'title': 'Draft hidden', 'project_id': project.id, **project_context(project)},
        format='json',
        **admin_headers,
    )
    aid = create.json()['id']

    resp = api_client.get(
        f'/api/accounts/collection-accounts/{aid}/pdf/',
        **client_headers,
    )

    assert resp.status_code == 404


@pytest.mark.django_db
def test_create_collection_account_returns_400_when_project_id_is_invalid(
    api_client, admin_headers,
):
    resp = api_client.post(
        '/api/accounts/collection-accounts/',
        {'title': 'Bad project', 'project_id': 999999},
        format='json',
        **admin_headers,
    )

    assert resp.status_code == 400
    assert 'project_id' in resp.json()


@pytest.mark.django_db
def test_create_collection_account_returns_400_when_neither_project_nor_client_provided(
    api_client, admin_headers,
):
    resp = api_client.post(
        '/api/accounts/collection-accounts/',
        {'title': 'No context'},
        format='json',
        **admin_headers,
    )

    assert resp.status_code == 400


@pytest.mark.django_db
def test_admin_list_filters_by_client_user_id_query_param(
    api_client, admin_headers, client_headers, project, client_user,
):
    api_client.post(
        '/api/accounts/collection-accounts/',
        {'title': 'For client', 'project_id': project.id, **project_context(project)},
        format='json',
        **admin_headers,
    )
    resp = api_client.get(
        f'/api/accounts/collection-accounts/?client_user_id={client_user.id}',
        **admin_headers,
    )

    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]['title'] == 'For client'


@pytest.mark.django_db
def test_admin_list_filters_by_commercial_status_query_param(
    api_client, admin_headers, project,
):
    api_client.post(
        '/api/accounts/collection-accounts/',
        {'title': 'Draft one', 'project_id': project.id, **project_context(project)},
        format='json',
        **admin_headers,
    )
    resp = api_client.get(
        '/api/accounts/collection-accounts/?commercial_status=draft',
        **admin_headers,
    )

    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]['commercial_status'] == 'draft'


@pytest.mark.django_db
def test_admin_get_collection_account_detail_returns_200(
    api_client, admin_headers, project,
):
    create = api_client.post(
        '/api/accounts/collection-accounts/',
        {'title': 'Detail test', 'project_id': project.id, **project_context(project)},
        format='json',
        **admin_headers,
    )
    aid = create.json()['id']

    resp = api_client.get(
        f'/api/accounts/collection-accounts/{aid}/',
        **admin_headers,
    )

    assert resp.status_code == 200
    assert resp.json()['id'] == aid
    assert resp.json()['title'] == 'Detail test'


@pytest.mark.django_db
def test_patch_issued_collection_account_returns_400(
    api_client, admin_headers, project,
):
    create = api_client.post(
        '/api/accounts/collection-accounts/',
        {'title': 'Will be issued', 'project_id': project.id, **project_context(project)},
        format='json',
        **admin_headers,
    )
    aid = create.json()['id']
    api_client.post(
        f'/api/accounts/collection-accounts/{aid}/issue/',
        format='json',
        **admin_headers,
    )

    resp = api_client.patch(
        f'/api/accounts/collection-accounts/{aid}/',
        {'title': 'Try to modify issued'},
        format='json',
        **admin_headers,
    )

    assert resp.status_code == 400


@pytest.mark.django_db
def test_admin_cancels_issued_collection_account_returns_200(
    api_client, admin_headers, project,
):
    create = api_client.post(
        '/api/accounts/collection-accounts/',
        {'title': 'To cancel', 'project_id': project.id, **project_context(project)},
        format='json',
        **admin_headers,
    )
    aid = create.json()['id']
    api_client.post(
        f'/api/accounts/collection-accounts/{aid}/issue/',
        format='json',
        **admin_headers,
    )

    resp = api_client.post(
        f'/api/accounts/collection-accounts/{aid}/mark-cancelled/',
        format='json',
        **admin_headers,
    )

    assert resp.status_code == 200
    assert resp.json()['commercial_status'] == 'cancelled'


@pytest.mark.django_db
def test_mark_paid_returns_404_for_nonexistent_account(api_client, admin_headers):
    resp = api_client.post(
        '/api/accounts/collection-accounts/999999/mark-paid/',
        format='json',
        **admin_headers,
    )

    assert resp.status_code == 404


@pytest.mark.django_db
def test_mark_cancelled_returns_404_for_nonexistent_account(api_client, admin_headers):
    resp = api_client.post(
        '/api/accounts/collection-accounts/999999/mark-cancelled/',
        format='json',
        **admin_headers,
    )

    assert resp.status_code == 404


@pytest.mark.django_db
def test_admin_list_collection_accounts_for_project_returns_200(
    api_client, admin_headers, project,
):
    api_client.post(
        '/api/accounts/collection-accounts/',
        {'title': 'Project CA', 'project_id': project.id, **project_context(project)},
        format='json',
        **admin_headers,
    )

    resp = api_client.get(
        f'/api/accounts/projects/{project.id}/collection-accounts/',
        **admin_headers,
    )

    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]['title'] == 'Project CA'


@pytest.mark.django_db
def test_project_collection_accounts_returns_404_for_nonexistent_project(
    api_client, admin_headers,
):
    resp = api_client.get(
        '/api/accounts/projects/999999/collection-accounts/',
        **admin_headers,
    )

    assert resp.status_code == 404


@pytest.mark.django_db
def test_client_cannot_list_another_clients_project_collection_accounts(
    api_client, client_headers,
):
    from django.contrib.auth import get_user_model
    from accounts.models import UserProfile

    User = get_user_model()
    other = User.objects.create_user(
        username='other@test.com',
        email='other@test.com',
        password='pass12345',
    )
    UserProfile.objects.create(user=other, role=UserProfile.ROLE_CLIENT, is_onboarded=True)
    other_project = Project.objects.create(
        name='Other Project', client=other, status=Project.STATUS_ACTIVE, progress=0,
    )

    resp = api_client.get(
        f'/api/accounts/projects/{other_project.id}/collection-accounts/',
        **client_headers,
    )

    assert resp.status_code == 403


@pytest.mark.django_db
def test_admin_patch_items_auto_calculates_line_total(
    api_client, admin_headers, project,
):
    create = api_client.post(
        '/api/accounts/collection-accounts/',
        {'title': 'Auto calc', 'project_id': project.id, **project_context(project)},
        format='json',
        **admin_headers,
    )
    aid = create.json()['id']

    resp = api_client.patch(
        f'/api/accounts/collection-accounts/{aid}/',
        {
            'items': [
                {
                    'description': 'Work',
                    'quantity': '2',
                    'unit_price': '50000.00',
                    'discount_amount': '0',
                    'tax_amount': '0',
                    # line_total omitted — should be auto-calculated as 2 * 50000 = 100000
                },
            ],
        },
        format='json',
        **admin_headers,
    )

    assert resp.status_code == 200
    items = resp.json()['items']
    assert len(items) == 1
    assert float(items[0]['line_total']) == 100000.0


@pytest.mark.django_db
def test_issue_collection_account_returns_404_for_nonexistent_account(api_client, admin_headers):
    resp = api_client.post(
        '/api/accounts/collection-accounts/999999/issue/',
        format='json',
        **admin_headers,
    )

    assert resp.status_code == 404


@pytest.mark.django_db
def test_admin_list_project_collection_accounts_filters_by_deliverable_id(
    api_client, admin_headers, project,
):
    api_client.post(
        '/api/accounts/collection-accounts/',
        {'title': 'No deliverable', 'project_id': project.id, **project_context(project)},
        format='json',
        **admin_headers,
    )

    resp = api_client.get(
        f'/api/accounts/projects/{project.id}/collection-accounts/?deliverable_id=9999',
        **admin_headers,
    )

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.django_db
def test_admin_patch_updates_multiple_fields(api_client, admin_headers, project):
    create = api_client.post(
        '/api/accounts/collection-accounts/',
        {'title': 'Original', 'project_id': project.id, **project_context(project)},
        format='json',
        **admin_headers,
    )
    aid = create.json()['id']

    resp = api_client.patch(
        f'/api/accounts/collection-accounts/{aid}/',
        {
            'title': 'Updated',
            'city': 'Bogotá',
            'notes': 'Some notes',
            'terms_and_conditions': 'Terms here.',
            'billing_concept': 'Desarrollo de software',
            'payment_term_days': 30,
            'support_reference': 'REF-001',
        },
        format='json',
        **admin_headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data['title'] == 'Updated'
    assert data['city'] == 'Bogotá'
    assert data['notes'] == 'Some notes'


@pytest.mark.django_db
def test_admin_patch_with_payment_methods(api_client, admin_headers, project):
    create = api_client.post(
        '/api/accounts/collection-accounts/',
        {'title': 'With payment', 'project_id': project.id, **project_context(project)},
        format='json',
        **admin_headers,
    )
    aid = create.json()['id']

    resp = api_client.patch(
        f'/api/accounts/collection-accounts/{aid}/',
        {
            'payment_methods': [
                {
                    'bank_name': 'Bancolombia',
                    'account_type': 'savings',
                    'account_number': '123456789',
                    'account_holder_name': 'ProjectApp SAS',
                    'is_primary': True,
                },
            ],
        },
        format='json',
        **admin_headers,
    )

    assert resp.status_code == 200
    assert len(resp.json()['payment_methods']) == 1
    assert resp.json()['payment_methods'][0]['bank_name'] == 'Bancolombia'
