"""Reusable acceptance cases missing from the volume-oriented seeders."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError

from accounts.models import (
    Deliverable, HostingSubscription, Payment, Project, UserProfile,
)
from accounts.services import platform_resources
from content.fake_data import add_seed_arguments, ensure_fake_data_allowed, seed_context
from content.fake_data_files import fake_data_transaction, sample_pdf
from content.models import IncomeRecord
from content.services.project_state_service import ensure_initial_project_state


def _pdf_upload(version):
    content = sample_pdf(f'qa-recurso-v{version}.pdf', f'ProjectApp - recurso ficticio v{version}')
    return SimpleUploadedFile(content.name, content.read(), content_type='application/pdf')


class Command(BaseCommand):
    help = 'Ensure identifiable QA roles, empty scopes, real resource versions and pending income.'

    def add_arguments(self, parser):
        add_seed_arguments(parser)

    @fake_data_transaction()
    def handle(self, *args, **options):
        ensure_fake_data_allowed('create_fake_platform_cases')
        context = seed_context(options, 'platform-cases')
        project = Project.objects.filter(client__isnull=False).select_related('client').order_by('pk').first()
        if project is None:
            raise CommandError('Run seed_platform_data before create_fake_platform_cases.')

        roles = {}
        for name, staff, superuser, onboarded, verified, completed in (
            ('superuser', True, True, True, True, True),
            ('staff', True, False, True, True, True),
            ('admin', False, False, True, True, True),
            ('empty', False, False, True, True, True),
            ('limited', False, False, True, True, True),
            ('pending', False, False, False, False, False),
            ('profile', False, False, True, True, False),
        ):
            user, created = get_user_model().objects.get_or_create(username=f'qa-{name}@example.test', defaults={
                'email': f'qa-{name}@example.test', 'first_name': f'QA {name}',
                'is_staff': staff, 'is_superuser': superuser, 'is_active': True,
            })
            if created:
                user.set_unusable_password()
                user.save(update_fields=['password'])
            UserProfile.objects.update_or_create(user=user, defaults={
                'role': 'admin' if name in {'superuser', 'staff', 'admin'} else 'client',
                'is_onboarded': onboarded, 'email_verified': verified,
                'email_verified_at': context.anchor_now if verified else None,
                'profile_completed': completed, 'company_name': f'[QA] Perfil {name}',
            })
            roles[name] = user

        for name, owner in (('[QA] Proyecto vacío', project.client),
                            ('[QA] Proyecto de otro cliente', roles['limited'])):
            empty, _ = Project.objects.get_or_create(name=name, client=owner)
            ensure_initial_project_state(empty, actor=roles['superuser'])

        resource = Deliverable.objects.filter(project=project, title='[QA] Recurso PDF con tres versiones').first()
        if resource is None:
            result = platform_resources.create_resource(project.pk, roles['superuser'], {
                'title': '[QA] Recurso PDF con tres versiones',
                'description': 'Archivos locales válidos para descarga y comparación de versiones.',
                'category': 'documents', 'file': _pdf_upload(1),
            })
            resource = Deliverable.objects.get(pk=result['id'])
        for version in range(resource.current_version + 1, 4):
            platform_resources.upload_version(project.pk, roles['superuser'], resource.pk, {'file': _pdf_upload(version)})

        IncomeRecord.objects.get_or_create(source_ref='fake:accounting', concept='[QA] Ingreso grande pendiente', defaults={
            'created_by': roles['superuser'], 'client': project.client.profile, 'project': project,
            'kind': 'expected', 'ledger': 'company', 'origin': 'other', 'destination': 'partners',
            'period_date': context.anchor_date.replace(day=1), 'total_amount': Decimal('987654321012.00'),
            'gustavo_amount': Decimal('493827160506.00'), 'carlos_amount': Decimal('493827160506.00'),
        })

        # Distinct projects keep mutually exclusive subscription states honest.
        for index, status in enumerate(('active', 'pending', 'suspended', 'cancelled')):
            hosting_project, _ = Project.objects.get_or_create(
                client=project.client, name=f'[QA] Hosting {status}',
            )
            ensure_initial_project_state(hosting_project, actor=roles['superuser'])
            subscription, _ = HostingSubscription.objects.get_or_create(project=hosting_project, defaults={
                'status': status, 'base_monthly_amount': Decimal('150000.00'),
                'effective_monthly_amount': Decimal('150000.00'), 'billing_amount': Decimal('450000.00'),
                'plan': 'quarterly',
                'next_billing_date': context.anchor_date + timedelta(days=15) if status == 'active' else None,
                'start_date': context.anchor_date - timedelta(days=90),
            })
            if index == 0:
                for payment_status, _ in Payment.STATUS_CHOICES:
                    due = context.anchor_date + timedelta(days=-30 if payment_status in {'paid', 'overdue'} else 15)
                    Payment.objects.get_or_create(subscription=subscription, description=f'[QA] Pago {payment_status}', defaults={
                        'amount': subscription.billing_amount, 'status': payment_status,
                        'billing_period_start': due - timedelta(days=90), 'billing_period_end': due,
                        'due_date': due, 'paid_at': context.anchor_now if payment_status == 'paid' else None,
                    })
        self.stdout.write('QA cases ready: qa-<role>@example.test; [QA] Proyecto vacío; '
                          '[QA] Recurso PDF con tres versiones; [QA] Ingreso grande pendiente.')
