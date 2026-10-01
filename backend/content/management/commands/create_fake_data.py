"""Build the complete, deterministic development dataset."""

from django.apps import apps
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from content.fake_data import (
    DEFAULT_COUNT,
    DEFAULT_SEED,
    add_seed_arguments,
    ensure_fake_data_allowed,
    seed_context,
)


# Catalog/config rows are intentionally excluded: they may exist before the
# first seed and are preserved by delete_fake_data. Any business root below
# means an additive run would no longer be reproducible.
BUSINESS_ROOT_MODELS = (
    'accounts.Project',
    'accounts.UserProfile',
    'content.BlogPost',
    'content.BusinessProposal',
    'content.CommunicationThread',
    'content.Contact',
    'content.Document',
    'content.DocumentThread',
    'content.EmailLog',
    'content.ExpenseRecord',
    'content.FinancingAgreement',
    'content.HostingRecord',
    'content.IncomeRecord',
    'content.LinkedInPost',
    'content.Linktree',
    'content.McpRequestLog',
    'content.PortfolioWork',
    'content.QRCard',
    'content.Task',
    'content.WebAppDiagnostic',
)


class Command(BaseCommand):
    help = (
        'Create the complete representative development dataset. The command '
        'is deterministic for a given --seed and --anchor-date, fails '
        'atomically, and requires --replace when business data already exists.'
    )

    def add_arguments(self, parser):
        add_seed_arguments(parser, count_default=DEFAULT_COUNT)
        parser.add_argument(
            'count_pos', nargs='?', type=int, default=None,
            help='Positional alias for --count (fake-data-refresh compatibility).',
        )
        parser.add_argument(
            '--replace', action='store_true',
            help='Delete the current development dataset before recreating it.',
        )
        parser.add_argument('--skip-contacts', action='store_true')
        parser.add_argument('--skip-proposals', action='store_true')
        parser.add_argument('--skip-blog', action='store_true')
        parser.add_argument('--skip-portfolio', action='store_true')
        parser.add_argument('--skip-tasks', action='store_true')
        parser.add_argument('--skip-diagnostics', action='store_true')
        parser.add_argument('--skip-financing', action='store_true')
        parser.add_argument('--skip-platform', action='store_true')
        parser.add_argument('--skip-documents', action='store_true')
        parser.add_argument('--skip-communications', action='store_true')
        parser.add_argument('--skip-accounting', action='store_true')
        parser.add_argument('--skip-auxiliary', action='store_true')

    def handle(self, *args, **options):
        ensure_fake_data_allowed('create_fake_data')
        count = options['count_pos'] if options['count_pos'] is not None else options['count']
        if count < 1:
            raise CommandError('--count must be greater than zero.')
        if options['skip_accounting'] and not options['skip_documents']:
            raise CommandError(
                '--skip-accounting requires --skip-documents because every '
                'generated collection account must have an IncomeRecord origin.',
            )

        context = seed_context(options, 'orchestrator')
        self._seed_args = (
            '--seed', str(options.get('seed', DEFAULT_SEED)),
            '--anchor-date', context.anchor_date.isoformat(),
        )
        self._completed = []

        with transaction.atomic():
            if options['replace']:
                self._run('development reset', 'delete_fake_data', '--confirm')
            else:
                populated_model = self._first_populated_business_model()
                if populated_model:
                    raise CommandError(
                        f'Business data already exists ({populated_model}). '
                        'Run again with --replace for a reproducible refresh.',
                    )

            # Establish identities and the deliberately uneven project graph first.
            if not options['skip_platform']:
                self._run_seeded(
                    'platform base', 'seed_platform_data',
                    '--skip-collection-accounts',
                )
                self._run_seeded('demo clients', 'seed_demo_clients')
            self._run_seeded(
                'representative clients/projects',
                'create_fake_clients_projects', '--count', str(count),
            )

            if not options['skip_contacts']:
                self._run_seeded('contacts', 'create_contacts', str(count))
            if not options['skip_proposals']:
                self._run_seeded('hour packages', 'create_fake_hour_packages')
                self._run_seeded(
                    'proposals', 'create_fake_proposals', '--count', str(count),
                )
            if not options['skip_financing']:
                self._run_seeded(
                    'financing agreements', 'create_fake_financing',
                    '--count', str(count),
                )
            if not options['skip_blog']:
                self._run_seeded(
                    'blog', 'create_fake_blog_posts', '--count', str(count),
                )
            if not options['skip_portfolio']:
                self._run_seeded(
                    'portfolio', 'create_fake_portfolio', '--count', str(count),
                )
            if not options['skip_tasks']:
                self._run_seeded(
                    'tasks', 'create_fake_tasks', '--count', str(count),
                )
            if not options['skip_diagnostics']:
                self._run_seeded(
                    'diagnostics', 'create_fake_diagnostics', '--count', str(count),
                    '--with-pricing', '--with-states', '--with-views',
                )

            if not options['skip_platform']:
                self._run_seeded(
                    'platform enrichment', 'enrich_platform_data',
                    '--count', str(count), '--notifications', str(count),
                )
                self._run('saved filter tabs', 'seed_filter_tabs')

            # Accounting precedes documents: collection accounts must be
            # generated by the real service from their IncomeRecord origin.
            if not options['skip_accounting']:
                self._run_seeded(
                    'accounting', 'create_fake_accounting', '--count', str(count),
                )
            if not options['skip_documents']:
                self._run_seeded(
                    'documents', 'create_fake_documents', '--count', str(count),
                )
            if not options['skip_communications']:
                self._run_seeded(
                    'communications', 'create_fake_communications',
                    '--count', str(count),
                )
            if not options['skip_auxiliary']:
                self._run_seeded(
                    'auxiliary modules', 'create_fake_auxiliary',
                    '--count', str(count),
                )
            if not options['skip_accounting'] and not options['skip_documents']:
                from accounts.management.commands._billing_seed_helpers import seed_fake_hosting_billing
                seed_fake_hosting_billing(context=context)
                self._completed.append('project billing contexts')

        command = (
            f'python manage.py create_fake_data --replace --count {count} '
            f'--seed {options.get("seed", DEFAULT_SEED)} '
            f'--anchor-date {context.anchor_date.isoformat()}'
        )
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Complete dataset created atomically ({len(self._completed)} stages).',
        ))
        self.stdout.write(f'Replay exactly with: {command}')

    def _run_seeded(self, label, command, *args):
        self._run(label, command, *args, *self._seed_args)

    def _run(self, label, command, *args):
        self.stdout.write(self.style.SUCCESS(f'\u2192 {label} ({command})...'))
        # Deliberately do not catch exceptions. The outer transaction rolls
        # the entire graph back, and manage.py exits non-zero with the cause.
        call_command(command, *args)
        self._completed.append(label)

    @staticmethod
    def _first_populated_business_model():
        for label in BUSINESS_ROOT_MODELS:
            model = apps.get_model(label)
            queryset = model.objects.all()
            if label == 'accounts.UserProfile':
                queryset = queryset.filter(role='client')
            elif label in {
                'content.ExpenseRecord',
                'content.HostingRecord',
                'content.IncomeRecord',
            }:
                # delete_fake_data deliberately preserves imported/manual
                # accounting. Only a previous fake graph blocks additive seed.
                queryset = queryset.filter(source_ref='fake:accounting')
            if queryset.exists():
                return label
        return None
