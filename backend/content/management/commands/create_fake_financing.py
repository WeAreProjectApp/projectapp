"""Create representative financing agreements for development environments."""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Project, UserProfile
from content.fake_data import (
    add_seed_arguments,
    ensure_fake_data_allowed,
    seed_context,
)
from content.models import (
    BusinessProposal,
    CompanySettings,
    FinancingAgreement,
    FinancingAgreementTemplate,
)
from content.fake_data_files import fake_data_transaction, sample_pdf
from content.services.financing_agreement_service import (
    DEFAULT_FINANCING_TEMPLATE_MARKDOWN,
    add_months,
    archive_agreement,
    cancel_agreement,
    complete_agreement,
    create_agreement,
    create_second_cycle,
    mark_ready,
    register_signed_pdf,
    update_draft,
)


User = get_user_model()


class Command(BaseCommand):
    help = (
        'Create deterministic financing drafts and lifecycle examples for the '
        'administrative workspace. Disabled outside dedicated fake-data settings.'
    )

    def add_arguments(self, parser):
        add_seed_arguments(parser, count_default=8)

    @fake_data_transaction()
    def handle(self, *args, **options):
        ensure_fake_data_allowed('create_fake_financing')
        context = seed_context(options, 'financing')
        clients = list(
            UserProfile.objects.clients()
            .filter(archived_at__isnull=True)
            .order_by('pk')
        )
        if not clients:
            raise CommandError(
                'Create at least one active client before seeding financing agreements.',
            )

        actor = User.objects.filter(is_staff=True).order_by('pk').first()
        template = self._ensure_template()
        self._ensure_contractor_identity()
        target = min(max(1, options['count']), 8)
        states = ('draft', 'ready', 'active', 'completed', 'cancelled')
        created = []

        for index in range(target):
            client = clients[index % len(clients)]
            project = Project.objects.filter(client=client.user).order_by('pk').first()
            proposal = BusinessProposal.objects.filter(client=client).order_by('pk').first()
            if client.nit:
                client_id_type, client_id_number = 'NIT', client.nit
            elif client.cedula:
                client_id_type, client_id_number = 'C.C.', client.cedula
            else:
                # Financing snapshots must be contract-ready even when another
                # module deliberately seeded an incomplete client profile.
                client_id_type = 'C.C.'
                client_id_number = f'DEMO-{client.pk:06d}'
            client_email = (
                client.user.email
                if client.user.email and not client.is_email_placeholder
                else f'financiacion-{client.pk}@demo.test'
            )
            lifecycle = states[index % len(states)]
            modality = (
                FinancingAgreement.Modality.THREE_YEAR
                if lifecycle in {'draft', 'cancelled'}
                else FinancingAgreement.Modality.FIVE_YEAR
            )
            partnership_start = date(
                context.anchor_date.year,
                context.anchor_date.month,
                1,
            )
            first_due = add_months(partnership_start, 1).replace(day=5)
            total = Decimal('24000000.00') + Decimal(index * 1250000)
            agreement = create_agreement(
                {
                    'uuid': context.uuid(f'agreement-{index}'),
                    'client': client,
                    'client_id_type': client_id_type,
                    'client_id_number': client_id_number,
                    'client_email': client_email,
                    'source_proposal': proposal,
                    'source_project': project,
                    'original_contract_reference': f'Contrato DEMO-{index + 1:03d}',
                    'original_contract_date': context.anchor_date - timedelta(days=365),
                    'project_name': project.name if project else f'Producto financiado {index + 1}',
                    'financed_scope': (
                        'Diseño, desarrollo, pruebas y puesta en producción de la '
                        f'fase demostrativa {index + 1}.'
                    ),
                    'modality': modality,
                    'partnership_start_date': partnership_start,
                    'currency': 'COP',
                    'total_value': total,
                    'initial_payment': (total * Decimal('0.20')).quantize(
                        Decimal('0.01'),
                    ),
                    'hosting_value': Decimal('480000.00'),
                    'hosting_period': FinancingAgreement.HostingPeriod.MONTHLY,
                    'first_installment_date': first_due,
                    'template': template,
                },
                actor=actor,
            )
            self._advance_lifecycle(
                agreement,
                lifecycle=lifecycle,
                actor=actor,
                index=index,
            )
            created.append(agreement)

        self.stdout.write(self.style.SUCCESS(
            f'Created {len(created)} representative financing agreement roots.',
        ))

    @staticmethod
    def _ensure_template():
        template = FinancingAgreementTemplate.get_default()
        if template:
            return template
        return FinancingAgreementTemplate.objects.create(
            name='Otrosí de financiación',
            version=1,
            content_markdown=DEFAULT_FINANCING_TEMPLATE_MARKDOWN,
            is_default=True,
            is_active=True,
        )

    @staticmethod
    def _ensure_contractor_identity():
        company = CompanySettings.load()
        changed = []
        defaults = {
            'contractor_full_name': 'ProjectApp S.A.S.',
            'contractor_nit': '901.234.567-8',
            'contractor_email': 'contratos@projectapp.dev',
        }
        for field, value in defaults.items():
            if not getattr(company, field):
                setattr(company, field, value)
                changed.append(field)
        if changed:
            company.save(update_fields=[*changed, 'updated_at'])

    @staticmethod
    def _signed_pdf(index):
        return sample_pdf(f'otrosi-financiacion-demo-{index + 1}.pdf')

    def _advance_lifecycle(self, agreement, *, lifecycle, actor, index):
        if lifecycle == 'draft':
            return
        agreement = mark_ready(agreement, actor=actor)
        if lifecycle == 'ready':
            return
        agreement = register_signed_pdf(
            agreement,
            self._signed_pdf(index),
            actor=actor,
        )
        if lifecycle == 'active':
            return
        if lifecycle == 'cancelled':
            agreement = cancel_agreement(
                agreement,
                actor=actor,
                reason='Ejemplo de cancelación antes de completar la financiación.',
            )
            archive_agreement(agreement, actor=actor)
            return

        agreement = complete_agreement(
            agreement,
            actor=actor,
            note='Pago íntegro certificado para el conjunto de datos demostrativo.',
        )
        second = create_second_cycle(agreement, actor=actor)
        second_due = add_months(agreement.partnership_start_date, 18).replace(day=5)
        update_draft(
            second,
            {
                'partnership_start_date': agreement.partnership_start_date,
                'financed_scope': 'Segunda fase aprobada del producto financiado.',
                'total_value': Decimal('24000000.00'),
                'initial_payment': Decimal('4800000.00'),
                'first_installment_date': second_due,
            },
            actor=actor,
        )
