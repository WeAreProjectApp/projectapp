"""Explicit billing fixtures for dedicated development/test databases only."""
import hashlib
from django.contrib.auth import get_user_model
from django.core.management.base import CommandError
from django.db import transaction
from django.db.models import Q

from accounts.models import (
    BillingContextEvent, CollectionAccountContext, ContractAmendment,
    HostingEvidence, HostingEvidenceGroup, HostingSubscription, Project,
    ProjectContract, ProjectHosting, ProjectHostingAccountingSource,
)
from accounts.services.billing_access import is_billing_admin
from accounts.services.billing_context import associate_account
from accounts.services.hosting_context import reconcile_hosting
from content.fake_data import ensure_fake_data_allowed
from content.models import Document, DocumentCollectionAccount, DocumentItem, HostingRecord
from content.services.document_type_utils import get_collection_account_document_type


def billing_seed_actor(actor=None):
    ensure_fake_data_allowed('billing_seed_helpers')
    if is_billing_admin(actor):
        return actor
    user, created = get_user_model().objects.get_or_create(
        username='billing-demo-admin', defaults={
            'email': 'billing-demo-admin@fake.projectapp.test',
            'is_staff': True, 'is_superuser': True,
        },
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=['password'])
    if not is_billing_admin(user):
        raise CommandError('The billing fixture actor already exists without administrative permission.')
    return user


def collection_context_for_seed(project, index, *, context, actor):
    """Choose a scripted fixture relation, never infer existing financial context."""
    ensure_fake_data_allowed('billing_seed_helpers')
    if project is None:
        return {}
    contracts = []
    project_key = f'{project.client.email}:{project.name}'
    for branch in ('a', 'b'):
        key = f'billing-demo-{branch}'
        source, _ = Document.objects.get_or_create(
            uuid=context.uuid(f'billing:{project_key}:contract:{branch}'),
            defaults={
                'title': f'[Demo] Contrato de cobros {branch.upper()}', 'project': project,
                'client_user': project.client, 'created_by': actor,
                'metadata': {'billing_fixture': 'source'},
                'content_markdown': '# Contrato ficticio\n\nExclusivo de la demostración de cobros.',
            },
        )
        contract, _ = ProjectContract.objects.get_or_create(project=project, key=key, defaults={
            'title': source.title, 'document': source,
        })
        amendments = []
        for number in (1, 2):
            document, _ = Document.objects.get_or_create(
                uuid=context.uuid(f'billing:{project_key}:amendment:{branch}:{number}'),
                defaults={
                    'title': f'[Demo] Otrosí {branch.upper()}-{number}', 'project': project,
                    'client_user': project.client, 'created_by': actor,
                    'metadata': {'billing_fixture': 'source'},
                    'content_markdown': '# Otrosí ficticio\n\nExclusivo de la demostración de cobros.',
                },
            )
            amendment, _ = ContractAmendment.objects.get_or_create(
                contract=contract, key=f'billing-demo-{number}',
                defaults={'title': document.title, 'document': document},
            )
            amendments.append(amendment)
        contracts.append((contract, amendments))
    contract, amendments = contracts[index % 2]
    return {
        'billing_nature': 'contract', 'contract_id': contract.pk,
        'amendment_id': amendments[(index // 2) % 2].pk if index % 3 else None,
    }


@transaction.atomic
def seed_fake_hosting_billing(*, context, actor=None):
    """Populate only marked fixture projects and sources, with recorded IDs."""
    ensure_fake_data_allowed('billing_seed_helpers')
    actor = billing_seed_actor(actor)
    projects = Project.objects.filter(client__email__endswith='@fake.projectapp.test').order_by('pk')
    for project in projects:
        records = list(HostingRecord.objects.filter(
            project=project, client__user=project.client, source_ref='fake:accounting',
        ).order_by('pk'))
        if not records or ProjectHosting.objects.filter(project=project).exists():
            continue
        # A fixture never reconciles manual/imported accounting alongside its
        # own rows. Those projects retain a real administrative pending state.
        if HostingRecord.objects.filter(project=project).exclude(pk__in=[row.pk for row in records]).exists():
            continue
        subscription = HostingSubscription.objects.filter(project=project).first()
        identity = reconcile_hosting(project.pk, actor, {
            'expected_version': 0, 'reason': 'Relaciones explícitas del escenario ficticio de hosting.',
            'subscription_id': subscription.pk if subscription else None,
            'hosting_record_ids': [row.pk for row in records],
            'operational_record_id': records[0].pk,
        })
        hosting = ProjectHosting.objects.get(pk=identity['id'])
        project_key = f'{project.client.email}:{project.name}'
        fixture_number = hashlib.sha256(project_key.encode()).hexdigest()[:8].upper()
        payments = list(subscription.payments.order_by('pk')[:3]) if subscription else []
        for index in range(3):
            payment = payments[index] if index < len(payments) else None
            document, created = Document.objects.get_or_create(
                uuid=context.uuid(f'billing:{project_key}:hosting-account:{index}'), defaults={
                    'title': f'[Demo] Hosting periódico {index + 1}', 'project': project,
                    'client_user': project.client, 'hosting_record': records[0],
                    'document_type': get_collection_account_document_type(),
                    'commercial_status': 'issued', 'issue_date': context.anchor_date,
                    'public_number': f'DEMO-H-{fixture_number}-{index + 1}',
                    'total': payment.amount if payment else records[0].payment_per_cycle,
                    'created_by': actor, 'metadata': {'billing_fixture': 'historical'},
                },
            )
            if created:
                DocumentCollectionAccount.objects.create(
                    document=document, customer_name=project.client.get_full_name() or project.client.email,
                    customer_project_name=project.name, billing_concept='Hosting ficticio periódico',
                )
                DocumentItem.objects.create(document=document, position=1, description='Período ficticio de hosting',
                                            quantity=1, unit_price=document.total, line_total=document.total)
                # The third row deliberately represents imported history still
                # awaiting association. No emitted PDF is rewritten afterwards.
                if index < 2:
                    associate_account(document.pk, actor, {
                        'billing_nature': 'hosting', 'project_hosting_id': hosting.pk,
                        'hosting_payment_id': payment.pk if payment else None,
                        'expected_version': 0, 'reason': 'Asociación explícita de evidencia ficticia.',
                    })
                from content.services.collection_account_snapshot_service import persist_collection_account_pdf
                persist_collection_account_pdf(document)


@transaction.atomic
def clear_fake_billing(projects, *, retention_context_ids=()):
    """Called before clearing protected contract/source roots in a fake reset."""
    ensure_fake_data_allowed('billing_seed_helpers')
    ids = list(projects.values_list('pk', flat=True))
    retention_context_ids = tuple(retention_context_ids)
    hosting_ids = list(ProjectHosting.objects.filter(
        Q(project_id__in=ids)
        | Q(retention_context_id__in=retention_context_ids)
    ).values_list('pk', flat=True))
    HostingEvidence.objects.filter(group__hosting_id__in=hosting_ids).delete()
    HostingEvidenceGroup.objects.filter(hosting_id__in=hosting_ids).delete()
    CollectionAccountContext.objects.filter(
        Q(document__project_id__in=ids)
        | Q(document__retention_context_id__in=retention_context_ids)
        | Q(hosting_id__in=hosting_ids)
    ).delete()
    BillingContextEvent.objects.filter(project_id__in=ids).delete()
    ProjectHosting.objects.filter(pk__in=hosting_ids).update(
        operational_accounting_source=None,
    )
    ProjectHostingAccountingSource.objects.filter(hosting_id__in=hosting_ids).delete()
    ProjectHosting.objects.filter(pk__in=hosting_ids).delete()
