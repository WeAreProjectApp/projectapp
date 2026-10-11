"""Emergency switch for Linktree template browser validation."""
import pytest

from content.models import Linktree, LinktreeTemplate, LinktreeTemplateVersion
from content.services.linktree_templates import validation
from content.services.linktree_templates.service import run_validation

pytestmark = pytest.mark.django_db


def pending_version():
    """Create a pending candidate exactly as an upload leaves it."""
    tree = Linktree.objects.create(handle='validator-switch', name='Validator switch')
    template = LinktreeTemplate.objects.create(
        owner=tree, name='Editorial', manifest={'editable_assets': []},
        html='<main>{{name}}</main>', assets={},
    )
    return LinktreeTemplateVersion.objects.create(
        linktree=tree, template=template, profile={}, profile_digest='0' * 64,
    )


def test_disabled_switch_rejects_candidate_without_starting_chromium(monkeypatch, settings):
    """Fails if turning the switch off still launches Chromium or lets the version pass."""
    settings.LINKTREE_BROWSER_VALIDATION = False
    launches = []
    monkeypatch.setattr(validation, 'sync_playwright', lambda: launches.append('chromium'))
    version = pending_version()

    run_validation(version.pk)

    version.refresh_from_db()
    assert version.status == 'invalid'
    assert [issue['code'] for issue in version.report['issues']] == ['validator_disabled']
    assert version.screenshots == {}
    assert launches == []
