"""Schema and fail-closed gates for the PA-221 MCP surface matrix."""
import copy
import hashlib
import json

import pytest

from content.mcp.coverage import CoverageError, build_matrix, load_verified_report, validate_report


SYNTHETIC_EVIDENCE = ['docs/audits/PA-221/README.md']
PERMISSION_EVIDENCE = ['docs/audits/PA-221/README.md']
CONFIRMATION_EVIDENCE = ['docs/audits/PA-221/README.md']


def synthetic_verified_report():
    """Build a schema-complete synthetic report; it is not a functional-run artifact."""
    report = build_matrix()
    for row in report['rows']:
        assert row['candidate_view_ids'], f"{row['id']} has no assigned surface"
        row.update({
            'result': 'mapped_verified',
            'tested_role': 'QA MCP functional actor',
            'view_ids': row['candidate_view_ids'],
            'evidence': SYNTHETIC_EVIDENCE,
            'permission_evidence': PERMISSION_EVIDENCE,
        })
        if row['requires_confirmation']:
            row['confirmation_evidence'] = CONFIRMATION_EVIDENCE

    for surface in report['surfaces']:
        if surface['result'] == 'exempt':
            continue
        checks = [row['id'] for row in report['rows'] if surface['id'] in row['view_ids']]
        assert checks, f"{surface['id']} has no mapped tool"
        surface.update({
            'result': 'mapped_verified',
            'evidence': SYNTHETIC_EVIDENCE,
            'checks': checks,
        })
        for feature in surface['feature_checks']:
            assert feature['candidate_tools'], f"{feature['id']} has no assigned tool"
            feature.update({
                'result': 'mapped_verified',
                'evidence': SYNTHETIC_EVIDENCE,
                'checks': [feature['candidate_tools'][0]],
            })
    return report


@pytest.fixture(scope='module')
def verified_report():
    return synthetic_verified_report()


def _drop_operation_evidence(report):
    report['rows'][0]['evidence'] = []


def _drop_permission_evidence(report):
    report['rows'][0]['permission_evidence'] = []


def _drop_confirmation_evidence(report):
    row = next(item for item in report['rows'] if item['requires_confirmation'])
    row['confirmation_evidence'] = []


def _use_an_untrusted_evidence_reference(report):
    report['rows'][0]['evidence'] = ['https://example.test/coverage.json']


def _use_a_missing_local_evidence_reference(report):
    report['rows'][0]['evidence'] = ['docs/audits/PA-221/missing-functional-run.md']


def _make_role_a_boolean(report):
    report['rows'][0]['tested_role'] = False


def _change_revision(report):
    report['revision'] = '0' * 40


def _change_fingerprint(report):
    report['matrix_fingerprint'] = 'incorrect-fingerprint'


def _change_contracts(report):
    report['contracts'] = {}


def _remove_feature(report):
    surface = next(item for item in report['surfaces'] if item['result'] != 'exempt')
    surface['feature_checks'].pop()


def _check_a_different_surface(report):
    surface = next(item for item in report['surfaces'] if item['result'] != 'exempt')
    other = next(row for row in report['rows'] if surface['id'] not in row['view_ids'])
    surface['feature_checks'][0]['checks'] = [other['id']]


def _check_the_wrong_tool_for_a_feature(report):
    surface = next(item for item in report['surfaces'] if item['id'] == '/panel')
    feature = next(item for item in surface['feature_checks'] if item['id'] == 'panel-command-center')
    wrong_tool = next(item for item in report['rows'] if item['id'] == 'operations:list_monitoring_cases')
    assert surface['id'] in wrong_tool['view_ids']
    assert wrong_tool['id'] not in feature['candidate_tools']
    feature['checks'] = [wrong_tool['id']]


def test_static_matrix_stays_unverified_until_a_functional_run():
    """Fails if generated mappings alone are accidentally accepted as retirement evidence."""
    report = build_matrix()

    assert {row['result'] for row in report['rows']} == {'mapped_unverified'}
    assert all(
        feature['result'] == 'mapped_unverified'
        for surface in report['surfaces'] if surface['result'] != 'exempt'
        for feature in surface['feature_checks']
    )


def test_synthetic_report_requires_current_metadata_and_complete_checks(tmp_path, verified_report):
    """Fails if the evidence schema cannot preserve every current tool, view, and metadata field."""
    report_path = tmp_path / 'coverage.json'
    raw = json.dumps(verified_report, sort_keys=True).encode()
    report_path.write_bytes(raw)

    current = validate_report(copy.deepcopy(verified_report))
    evidence = load_verified_report(report_path)

    assert evidence == {
        'schema': 1,
        'report_sha256': hashlib.sha256(raw).hexdigest(),
        'report_path': str(report_path.resolve()),
        'revision': current['revision'],
        'matrix_fingerprint': current['matrix_fingerprint'],
        'contracts': current['contracts'],
        'operations': len(current['rows']),
        'surfaces': len(current['surfaces']),
    }


@pytest.mark.parametrize(
    ('corrupt', 'reason'),
    [
        (_drop_operation_evidence, 'operation functional evidence'),
        (_drop_permission_evidence, 'operation permission evidence'),
        (_drop_confirmation_evidence, 'confirmation evidence'),
        (_use_an_untrusted_evidence_reference, 'untrusted evidence reference'),
        (_use_a_missing_local_evidence_reference, 'missing local evidence reference'),
        (_make_role_a_boolean, 'non-string tested role'),
        (_change_revision, 'stale revision'),
        (_change_fingerprint, 'altered matrix fingerprint'),
        (_change_contracts, 'altered contracts'),
        (_remove_feature, 'missing feature check'),
        (_check_a_different_surface, 'feature check mapped to another surface'),
        (_check_the_wrong_tool_for_a_feature, 'feature check mapped to another tool in its surface'),
    ],
)
def test_verified_report_rejects_missing_or_mismatched_evidence(verified_report, corrupt, reason):
    """Fails if incomplete, stale, or cross-surface proof can authorize connector retirement."""
    report = copy.deepcopy(verified_report)
    corrupt(report)

    with pytest.raises(CoverageError):
        validate_report(report)
