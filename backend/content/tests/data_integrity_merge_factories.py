"""Factories shared by the folder-merge and client-merge tests."""
from django.apps import apps
from django.contrib.auth import get_user_model
from django.utils import timezone

from content.models import Document, DocumentFolder, DocumentType
from content.services.document_type_codes import COLLECTION_ACCOUNT
from accounts.models import Project, UserProfile
from datetime import date, datetime, timezone as datetime_timezone
from decimal import Decimal


def document_type(code='markdown', name='Markdown'):
    kind, _ = DocumentType.objects.get_or_create(code=code, defaults={'name': name})
    return kind


def make_user(username, **values):
    return get_user_model().objects.create_user(username=username, email=values.pop('email', ''), **values)


def make_folder(name, parent=None, **values):
    return DocumentFolder.objects.create(name=name, parent=parent, **values)


def make_document(title, folder=None, **values):
    values.setdefault('document_type', document_type())
    values.setdefault('content_markdown', f'# {title}')
    return Document.objects.create(title=title, folder=folder, **values)


def make_collection_account(title, client_user, commercial_status, **values):
    return make_document(title, client_user=client_user, commercial_status=commercial_status,
                         document_type=document_type(COLLECTION_ACCOUNT, 'Cuenta de cobro'), **values)


def archived(**values):
    """Values for a row archived on its own (``archived_via_folder`` NULL)."""
    return {'is_archived': True, 'archived_at': timezone.now(), **values}


def make_client(key, *, email=None, user_values=None, **values):
    identity = {'first_name': 'Ana', 'last_name': 'Cliente', 'is_active': False, **(user_values or {})}
    user = make_user(key, email=email if email is not None else f'{key}@temp.example.com', **identity)
    return UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT, **values)


def client_pair(**duplicate_values):
    survivor = make_client('merge-survivor', email='ana@example.com', company_name='Ejemplo SAS')
    duplicate = make_client('merge-duplicate', email='ana@example.com', company_name='Ejemplo SAS', **duplicate_values)
    return survivor, duplicate


def merge_state(keys):
    """Every live column except modification timestamps, including untouched facts."""
    result = {}
    for label, pk in keys:
        values = apps.get_model(label)._base_manager.filter(pk=pk).values().get()
        values.pop('updated_at', None)
        result[(label, pk)] = values
    return result


def make_pending_intent(profile, *, expires_at):
    from content.models import McpActionIntent, McpConnector, McpCredential
    connector = McpConnector.objects.create(slug='merge-test', name='Test')
    credential = McpCredential.objects.create(connector=connector, actor=make_user('technical'),
                                               label='Test', token_hash='f' * 64)
    return McpActionIntent.objects.create(
        connector=connector, credential=credential, tool_name='test', arguments={'client_id': profile.pk},
        arguments_hash='f' * 64, expires_at=expires_at,
    )


def make_client_project(profile, name='Proyecto de prueba'):
    return Project.objects.create(client=profile.user, name=name)


def merge_selection(survivor, duplicate, *, rule_id='CL1', **params):
    from content.tests.data_integrity_helpers import only, scan, selection
    finding = next(row for row in only(scan(rule_ids=[rule_id]), rule_id)
                   if {survivor.pk, duplicate.pk} <= set(row.evidence['profiles']))
    return selection(finding, 'merge_clients', survivor=survivor.pk, duplicate=duplicate.pk, **params)


def make_income(profile, **values):
    from content.models import IncomeRecord
    defaults = {'concept': 'Servicio', 'kind': 'expected', 'period_date': date(2026, 1, 1),
                'total_amount': Decimal('100'), 'gustavo_amount': Decimal('50'), 'carlos_amount': Decimal('50')}
    return IncomeRecord.objects.create(client=profile, **{**defaults, **values})


def make_hosting(profile, **values):
    from content.models import HostingRecord
    defaults = {'client_name': 'Nombre anterior', 'domain_url': 'example.com', 'monthly_value': Decimal('100')}
    return HostingRecord.objects.create(client=profile, **{**defaults, **values})


def run_client_merge(actor, survivor, duplicate, **params):
    from content.tests.data_integrity_helpers import apply
    return apply(actor, [merge_selection(survivor, duplicate, **params)])


def make_secure_link(profile, token_hash, request_id):
    from secure_links.models import SecureLink
    return SecureLink.objects.create(
        owner=profile, client=profile, token_hash=token_hash, token_encrypted='test-token',
        secret_type='password', title='Enlace ficticio', payload_encrypted='test-payload',
        origin='client', audience='team', creation_request_id=request_id,
        expires_at=datetime(2030, 1, 1, tzinfo=datetime_timezone.utc),
    )
