"""Historical adoption requires a reviewed inventory and preserves exact assets."""
import json
from io import StringIO

import pytest
from django.core.management import call_command, CommandError

from content.models import Document, ProposalApprovalFile, ProposalDocumentBinding
from content.tests.views.test_proposal_shared_documents import confirmed_proposal, approval_client, reviewed_proposal

pytestmark = pytest.mark.django_db


@pytest.fixture
def historical_proposal(confirmed_proposal):
    document_ids = list(confirmed_proposal.document_bindings.values_list('document_id', flat=True))
    ProposalApprovalFile.objects.filter(proposal=confirmed_proposal).update(package=None, binding=None)
    confirmed_proposal.document_bindings.all().delete()
    confirmed_proposal.approval_packages.all().delete()
    Document.objects.filter(pk__in=document_ids).delete()
    return confirmed_proposal


def inventory(proposal):
    output = StringIO()
    call_command('reconcile_proposal_documents', proposal=proposal.pk, stdout=output)
    return json.loads(output.getvalue())


def test_reviewed_historical_adoption_preserves_asset_identity(historical_proposal, admin_user):
    before = list(historical_proposal.approval_files.values_list('id', 'file', 'sha256'))
    review = inventory(historical_proposal)

    call_command('reconcile_proposal_documents', proposal=historical_proposal.pk, actor=admin_user.pk,
                 expected_hash=review['expected_hash'], apply=True, stdout=StringIO())

    assert list(historical_proposal.approval_files.values_list('id', 'file', 'sha256')) == before
    assert historical_proposal.approval_packages.count() == 1
    assert ProposalDocumentBinding.objects.filter(proposal=historical_proposal).count() == len(before)


def test_repeated_historical_adoption_creates_no_second_package(historical_proposal, admin_user):
    review = inventory(historical_proposal)
    arguments = {'proposal': historical_proposal.pk, 'actor': admin_user.pk,
                 'expected_hash': review['expected_hash'], 'apply': True}
    call_command('reconcile_proposal_documents', **arguments, stdout=StringIO())

    call_command('reconcile_proposal_documents', **arguments, stdout=StringIO())

    assert historical_proposal.approval_packages.count() == 1


def test_changed_historical_source_requires_another_review(historical_proposal, admin_user):
    review = inventory(historical_proposal)
    historical_proposal.title = 'Changed after review'
    historical_proposal.save(update_fields=['title'])

    with pytest.raises(CommandError, match='huella|hash'):
        call_command('reconcile_proposal_documents', proposal=historical_proposal.pk, actor=admin_user.pk,
                     expected_hash=review['expected_hash'], apply=True, stdout=StringIO())

    assert historical_proposal.approval_packages.count() == 0
