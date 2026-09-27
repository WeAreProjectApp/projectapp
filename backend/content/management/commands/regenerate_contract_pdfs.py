"""
Regenerate the stored contract PDF for proposals whose contract was built
from the default ContractTemplate, so they pick up the latest template
wording after a template update.

By default only proposals with ``status=negotiating`` are regenerated,
since ``accepted`` contracts were already signed by the client and
their PDF must match what was signed. Pass ``--include-accepted`` to
override that guard explicitly.

Only the documents of each proposal's closing modality are regenerated:
the single contract, or the product and service contracts.
"""

from django.core.management.base import BaseCommand

from content.models import ProposalDocument
from content.services import contract_variants
from content.views.proposal import _generate_and_save_contract_pdf


DEFAULT_STATUSES = ('negotiating',)


class Command(BaseCommand):
    help = 'Regenerate contract PDFs for proposals using the default template.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show which proposals would be regenerated without touching files.',
        )
        parser.add_argument(
            '--include-accepted',
            action='store_true',
            help='Also regenerate contracts for proposals in accepted status '
                 '(overwrites the PDF the client already signed).',
        )
        parser.add_argument(
            '--only',
            type=int,
            nargs='+',
            metavar='PROPOSAL_ID',
            help='Restrict to specific proposal IDs.',
        )

    def handle(self, *args, **opts):
        dry_run = opts['dry_run']
        statuses = list(DEFAULT_STATUSES)
        if opts['include_accepted']:
            statuses.append('accepted')
        only_ids = opts.get('only')

        qs = ProposalDocument.objects.filter(
            document_type__in=ProposalDocument.CONTRACT_DOC_TYPES,
            proposal__status__in=statuses,
        ).select_related('proposal')
        if only_ids:
            qs = qs.filter(proposal_id__in=only_ids)

        total = qs.count()
        if not total:
            self.stdout.write(self.style.WARNING('No contract PDFs match the filter.'))
            return

        regenerated = 0
        skipped_custom = 0
        for doc in qs:
            proposal = doc.proposal
            variant = contract_variants.DOC_TYPE_VARIANTS[doc.document_type]
            if variant not in contract_variants.active_variants(proposal):
                self.stdout.write(
                    f'[skip inactive] proposal id={proposal.id} variant={variant}'
                )
                continue
            params = proposal.contract_params or {}
            source = contract_variants.contract_source(params, variant)
            if source != 'default':
                skipped_custom += 1
                self.stdout.write(
                    f'[skip custom] proposal id={proposal.id} source={source}'
                )
                continue

            label = f'proposal id={proposal.id} status={proposal.status} variant={variant}'
            if dry_run:
                self.stdout.write(f'[would regenerate] {label}')
            else:
                _generate_and_save_contract_pdf(proposal, variant)
                regenerated += 1
                self.stdout.write(self.style.SUCCESS(f'[regenerated] {label}'))

        if dry_run:
            self.stdout.write(self.style.NOTICE(
                f'Dry run: {total} match(es), {skipped_custom} custom skipped.',
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Done: {regenerated} regenerated, {skipped_custom} custom skipped.',
            ))
