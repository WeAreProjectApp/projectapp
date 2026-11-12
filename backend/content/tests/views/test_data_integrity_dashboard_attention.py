"""The dashboard radar exposes only current, unaccepted integrity findings."""
import pytest
from django.utils import timezone

from content.models import DataIntegrityFinding, DataIntegrityScan
from content.services.panel_dashboard_service import build_panel_dashboard

pytestmark = pytest.mark.django_db


def _scan():
    return DataIntegrityScan.objects.create(
        request_id='dashboard-scan', scope={'kind': 'all', 'id': None}, filters={},
        source='scheduled', catalog_version='1.2.0', status='completed',
        finished_at=timezone.now(),
    )


def _finding(scan, fingerprint, *, accepted=False):
    return DataIntegrityFinding.objects.create(
        fingerprint=fingerprint, rule_id='DC11', domain='documents', severity='high',
        payload={'title': 'Documento sin carpeta', 'message': 'Revisar ubicación'},
        is_present=True, is_accepted=accepted, last_seen_at=timezone.now(), last_scan=scan,
    )


def test_dashboard_counts_only_pending_integrity_findings():
    """Fails if an accepted integrity observation remains in the dashboard attention total."""
    scan = _scan()
    _finding(scan, 'b' * 64)
    _finding(scan, 'c' * 64, accepted=True)

    attention = build_panel_dashboard(include_finance=False)['attention']
    item = next(row for row in attention if row['type'] == 'data_integrity')

    assert (item['count'], item['severity'], item['meta']['last_review_at']) == (
        1, 'danger', scan.finished_at.isoformat(),
    )


def test_dashboard_detail_targets_the_integrity_panel(admin_client):
    """Fails if a dashboard integrity alert no longer opens the finding in the integrity workspace."""
    scan = _scan()
    finding = _finding(scan, 'd' * 64)

    response = admin_client.get('/api/panel/dashboard/attention/data_integrity/')

    assert response.status_code == 200
    assert response.data['results'][0]['destination'] == f'/panel/data-integrity?finding={finding.fingerprint}'


def test_staff_dashboard_omits_accounting_integrity_summary():
    scan = _scan()
    finding = _finding(scan, 'e' * 64)
    DataIntegrityFinding.objects.filter(pk=finding.pk).update(domain='accounting', rule_id='AC12')

    attention = build_panel_dashboard(include_finance=False)['attention']

    assert [row['type'] for row in attention].count('data_integrity') == 0


def test_staff_dashboard_refuses_accounting_integrity_detail(api_client, django_user_model):
    staff = django_user_model.objects.create_user(username='integrity-staff', is_staff=True)
    api_client.force_authenticate(staff)
    scan = _scan()
    finding = _finding(scan, 'f' * 64)
    DataIntegrityFinding.objects.filter(pk=finding.pk).update(domain='accounting', rule_id='AC12')

    response = api_client.get(f'/api/panel/dashboard/attention/data_integrity/{finding.pk}/')

    assert response.status_code == 403
    assert response.data['detail'] == 'Consulta este hallazgo desde Integridad de datos.'
