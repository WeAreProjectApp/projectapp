"""Ownership rules CL6, PJ8, PJ9 and PR9: residual client rows, cross-client links, retention index, pricing.

Each inconsistency is made with a raw ``QuerySet.update``, the way it slips in
for real: the services and ``clean()`` methods that keep these invariants never run.
"""
import pytest

from content.models import BusinessProposal, CommunicationFolder, IncomeRecord, ProjectRetentionContext
from content.services.data_integrity.types import REPORT_ONLY
from content.tests.data_integrity_accounting_factories import make_income
from content.tests.data_integrity_documents_factories import make_communication_folder, make_document
from content.tests.data_integrity_helpers import make_project, make_proposal, scan
from content.tests.data_integrity_projects_factories import make_retention_context

pytestmark = pytest.mark.django_db

COMPLETE_SNAPSHOT = {'original_investment': '1000.00', 'total_investment': '1100.00', 'discount_percent': 10,
                     'currency': 'COP', 'discounted_investment': '900.00'}


def _found(rule_id):
    return scan(rule_ids=[rule_id])


# ── CL6 · client with no business left but rows that condition its delete ────

def test_client_keeping_a_folder_and_a_document_is_reported_with_both(make_client_profile):
    """Fails if a client with no business but a blocking folder and an unowned-on-delete document goes unreported."""
    client = make_client_profile()
    make_communication_folder(client)
    make_document(client_user=client.user)

    [finding] = _found('CL6')

    assert finding.evidence == {'profile': client.pk, 'blocking': ['content.communicationfolder.client'],
                                'traces': ['content.Document.client_user']}
    assert finding.fix_kinds == (REPORT_ONLY,)


def test_clients_with_business_or_with_nothing_are_not_cl6(make_client_profile):
    """Fails if a client with a proposal, or a true orphan (CL4's), is reported as residual."""
    make_proposal(make_client_profile(company='Con propuesta'))
    make_client_profile(company='Sin nada')

    assert _found('CL6') == []


# ── PJ8 · client records on another client's project ────────────────────────

def test_communication_folder_on_another_clients_project_is_reported(make_client_profile):
    """Fails if a communication folder pointing at another client's project goes unreported."""
    owner = make_client_profile(company='Dueño')
    foreign = make_project(make_client_profile(company='Otro'))
    folder = make_communication_folder(owner)
    CommunicationFolder.objects.filter(pk=folder.pk).update(project=foreign)

    [finding] = _found('PJ8')

    assert finding.evidence == {'model': 'content.communicationfolder', 'id': folder.pk, 'project': foreign.pk}
    assert finding.fix_kinds == (REPORT_ONLY,)


def test_folder_on_its_own_clients_project_is_quiet(make_client_profile):
    """Fails if a communication folder of the project's own client is reported."""
    owner = make_client_profile()
    make_communication_folder(owner, project=make_project(owner))

    assert _found('PJ8') == []


# ── PJ9 · retained rows the deletion index never listed ──────────────────────

def test_retained_row_missing_from_its_deletion_index_is_reported(make_client_profile, superuser):
    """Fails if a row marked as retained outside the audited deletion goes unreported."""
    client = make_client_profile()
    context = make_retention_context(client, superuser)
    income = make_income(client)
    IncomeRecord.objects.filter(pk=income.pk).update(retention_context=context)

    [finding] = _found('PJ9')

    assert finding.evidence == {'model': 'content.incomerecord', 'id': income.pk, 'context': context.pk}


def test_retained_row_listed_in_its_deletion_index_is_quiet(make_client_profile, superuser):
    """Fails if a row the deletion index lists is reported as unlisted."""
    client = make_client_profile()
    context = make_retention_context(client, superuser)
    income = make_income(client)
    IncomeRecord.objects.filter(pk=income.pk).update(retention_context=context)
    ProjectRetentionContext.objects.filter(pk=context.pk).update(
        retained_records={'content.incomerecord': [str(income.pk)]},
    )

    assert _found('PJ9') == []


# ── PR9 · historical pricing snapshot missing its keys ───────────────────────

def test_pricing_snapshot_without_original_investment_is_reported(make_client_profile):
    """Fails if a snapshot that would raise KeyError when the discount is read goes unreported (H3)."""
    proposal = make_proposal(make_client_profile(), discount_percent=10)
    incomplete = {key: value for key, value in COMPLETE_SNAPSHOT.items() if key != 'original_investment'}
    BusinessProposal.objects.filter(pk=proposal.pk).update(legacy_pricing_snapshot=incomplete)

    [finding] = _found('PR9')

    assert finding.evidence == {'proposal': proposal.pk, 'missing': ['original_investment']}
    assert finding.fix_kinds == (REPORT_ONLY,)


def test_snapshot_without_original_investment_but_no_discount_is_quiet(make_client_profile):
    """Fails if PR9 reports a key nothing reads: original_investment only matters with a discount."""
    proposal = make_proposal(make_client_profile())
    no_original = {key: value for key, value in COMPLETE_SNAPSHOT.items() if key != 'original_investment'}
    BusinessProposal.objects.filter(pk=proposal.pk).update(legacy_pricing_snapshot={**no_original,
                                                                                    'discount_percent': 0})

    assert _found('PR9') == []


def test_complete_or_empty_pricing_snapshots_are_quiet(make_client_profile):
    """Fails if the migration's complete snapshot, or the empty default, is reported."""
    client = make_client_profile()
    complete = make_proposal(client, title='Migrada', discount_percent=10)
    BusinessProposal.objects.filter(pk=complete.pk).update(legacy_pricing_snapshot=COMPLETE_SNAPSHOT)
    make_proposal(client, title='Nueva')

    assert _found('PR9') == []
