"""Emergency switch for Linktree template browser validation."""
import pytest

from content.models import Linktree, LinktreeTemplate, LinktreeTemplateVersion
from content.services.linktree_templates import fonts as google_fonts
from content.services.linktree_templates.service import run_validation
from linktree_sandbox import worker

pytestmark = pytest.mark.django_db


def pending_version():
    """Create a pending candidate exactly as an upload leaves it."""
    tree = Linktree.objects.create(handle='validator-switch', name='Validator switch')
    template = LinktreeTemplate.objects.create(
        owner=tree, name='Editorial', manifest={'editable_assets': [], 'fonts': ['Inter'], 'motion': False},
        html='<main>{{name}}</main>', assets={},
    )
    return LinktreeTemplateVersion.objects.create(
        linktree=tree, template=template, profile={}, profile_digest='0' * 64,
    )


def test_disabled_switch_rejects_candidate_without_starting_chromium(monkeypatch, settings):
    """Fails if turning the switch off still launches Chromium, downloads fonts or lets the version pass."""
    settings.LINKTREE_BROWSER_VALIDATION = False
    started = []
    monkeypatch.setattr(worker, 'sync_playwright', lambda: started.append('chromium'))
    monkeypatch.setattr(google_fonts, 'prefetch', lambda *args: started.append('fonts'))
    version = pending_version()

    run_validation(version.pk)

    version.refresh_from_db()
    assert version.status == 'invalid'
    assert [issue['code'] for issue in version.report['issues']] == ['validator_disabled']
    assert version.screenshots == {}
    assert started == []
