"""Client rules: duplicate groups (CL1-CL3), orphan clients (CL4) and projects owned by a non-client (CL5)."""
from datetime import datetime
from datetime import timezone as dt_timezone

import pytest
from accounts.models import Project, UserProfile

from content.services.data_integrity.types import MERGE_CLIENTS, REPORT_ONLY
from content.tests.data_integrity_helpers import make_project, make_proposal, scan
from content.tests.data_integrity_projects_factories import (
    make_retention_context,
    make_user,
)

pytestmark = pytest.mark.django_db

ARCHIVED_AT = datetime(2026, 1, 15, 12, 0, tzinfo=dt_timezone.utc)


def _found(rule_id, scope_kind='all', scope_id=None):
    return scan(scope_kind, scope_id, rule_ids=[rule_id])


# ── CL1 · same email ─────────────────────────────────────────────────────────

def test_clients_sharing_an_email_form_one_merge_group(make_client_profile):
    """Fails if two profiles with the same email, case aside, are not offered as one merge group."""
    first = make_client_profile(company='Kore SAS', email='ana@kore.co', username='ana-1')
    second = make_client_profile(company='Kore', email='ANA@kore.co', username='ana-2')
    make_client_profile(company='Otra', email='otra@kore.co', username='otra')

    [finding] = _found('CL1')

    assert [subject.pk for subject in finding.subjects] == [first.pk, second.pk]
    assert finding.evidence == {'key': 'ana@kore.co', 'profiles': [first.pk, second.pk]}
    assert finding.fix_kinds == (MERGE_CLIENTS,)
    assert finding.suggestion == {'survivor': first.pk, 'duplicate': second.pk}


def test_shared_placeholder_emails_are_not_a_duplicate_group(make_client_profile):
    """Fails if the provisional email every email-less client gets is taken for one person."""
    make_client_profile(company='Uno', email='tmp@temp.example.com', username='tmp-1')
    make_client_profile(company='Dos', email='tmp@temp.example.com', username='tmp-2')
    real = make_client_profile(company='Tres', email='tres@kore.co', username='tres-1')
    twin = make_client_profile(company='Cuatro', email='tres@kore.co', username='tres-2')

    assert [finding.evidence['profiles'] for finding in _found('CL1')] == [[real.pk, twin.pk]]


def test_duplicate_whose_twin_is_outside_the_client_scope_is_still_reported(make_client_profile):
    """Fails if a client-scoped scan hides a group because the twin is another client, or leaks it elsewhere."""
    first = make_client_profile(company='Uno', email='ana@kore.co', username='ana-1')
    second = make_client_profile(company='Dos', email='ana@kore.co', username='ana-2')
    unrelated = make_client_profile(company='Tres', email='tres@kore.co', username='tres')

    [finding] = _found('CL1', 'client', second.pk)

    assert finding.evidence['profiles'] == [first.pk, second.pk]
    assert _found('CL1', 'client', unrelated.pk) == []


# ── CL2 · provisional clone ──────────────────────────────────────────────────

def test_provisional_client_named_like_a_real_one_is_grouped_with_it(make_client_profile):
    """Fails if a provisional clone goes unreported or the real client is not the suggested survivor."""
    clone = make_client_profile(company='', first_name='Laura', last_name='Gómez',
                                email='x1@temp.example.com', username='x1')
    real = make_client_profile(company='Kore SAS', first_name='Laura', last_name='Gomez',
                               email='laura@kore.co', username='laura')

    [finding] = _found('CL2')

    assert finding.evidence == {'key': 'laura gomez', 'profiles': [clone.pk, real.pk]}
    assert finding.suggestion == {'survivor': real.pk, 'duplicate': clone.pk}


def test_namesakes_with_real_emails_are_not_a_provisional_clone(make_client_profile):
    """Fails if two real clients that share a name are reported as a provisional duplicate."""
    make_client_profile(company='Uno SAS', first_name='Laura', last_name='Gómez', email='l@uno.co', username='l1')
    make_client_profile(company='Dos SAS', first_name='Laura', last_name='Gómez', email='l@dos.co', username='l2')
    clone = make_client_profile(company='Tres SAS', first_name='Pedro', last_name='Ruiz',
                                email='x2@temp.example.com', username='x2')
    real = make_client_profile(company='Cuatro', first_name='Pedro', last_name='Ruiz',
                               email='pedro@kore.co', username='pedro')

    assert [finding.evidence['profiles'] for finding in _found('CL2')] == [[clone.pk, real.pk]]


def test_short_provisional_names_are_detected(make_client_profile):
    """Fails if a valid short name is silently excluded from provisional duplicate detection."""
    provisional = make_client_profile(company='', first_name='Li', last_name='', email='li@temp.example.com')
    real = make_client_profile(company='', first_name='Li', last_name='', email='li@example.com')

    [finding] = _found('CL2')

    assert finding.evidence == {'key': 'li', 'profiles': [provisional.pk, real.pk]}


def test_a_name_matching_another_clients_company_is_not_a_clone(make_client_profile):
    """Fails if comparing a person's name to a different company's name creates a duplicate."""
    make_client_profile(company='Otra', first_name='Kore', last_name='', email='pending@temp.example.com')
    make_client_profile(company='Kore', first_name='Ana', last_name='Pérez')

    assert _found('CL2') == []


def test_padded_placeholder_addresses_are_excluded_from_real_email_duplicates(make_client_profile):
    """Fails if whitespace or case makes a provisional address count as a real shared email."""
    make_client_profile(company='Uno', email=' shared@TEMP.EXAMPLE.COM ')
    make_client_profile(company='Dos', email='shared@TEMP.EXAMPLE.COM')

    assert _found('CL1') == []


# ── CL3 · same cédula ────────────────────────────────────────────────────────

def test_clients_with_the_same_id_digits_form_one_merge_group(make_client_profile):
    """Fails if a cédula written with and without dots is not recognised as the same person."""
    first = make_client_profile(company='Uno', cedula='1.234.567', email='uno@kore.co', username='uno')
    second = make_client_profile(company='Dos', cedula='1234567', email='dos@kore.co', username='dos')

    [finding] = _found('CL3')

    assert finding.evidence == {'key': '1234567', 'profiles': [first.pk, second.pk]}
    assert finding.fix_kinds == (MERGE_CLIENTS,)


def test_ids_too_short_to_identify_anyone_are_not_grouped(make_client_profile):
    """Fails if shared ids under five digits produce a merge group."""
    make_client_profile(company='Uno', cedula='1234', email='uno@kore.co', username='uno')
    make_client_profile(company='Dos', cedula='12-34', email='dos@kore.co', username='dos')
    first = make_client_profile(company='Tres', cedula='98765', email='tres@kore.co', username='tres')
    second = make_client_profile(company='Cuatro', cedula='98.765', email='cuatro@kore.co', username='cuatro')

    assert [finding.evidence['profiles'] for finding in _found('CL3')] == [[first.pk, second.pk]]


# ── CL4 · orphan client ──────────────────────────────────────────────────────

def test_client_with_nothing_linked_is_reported_for_manual_deletion(make_client_profile):
    """Fails if an orphan client goes unreported or is offered an engine fix instead of the manual delete."""
    orphan = make_client_profile(company='Sin nada SAS')

    [finding] = _found('CL4')

    assert finding.subjects[0].key() == ('accounts.userprofile', orphan.pk)
    assert finding.evidence == {'profile': orphan.pk}
    assert finding.fix_kinds == (REPORT_ONLY,)
    assert 'Huérfanos' in finding.message


def test_clients_with_a_proposal_a_project_or_archived_are_not_orphans(make_client_profile):
    """Fails if a client that still owns a proposal or a project, or was archived on purpose, is reported."""
    make_proposal(make_client_profile(company='Con propuesta'))
    make_project(make_client_profile(company='Con proyecto'))
    make_client_profile(company='Archivado', archived_at=ARCHIVED_AT)
    orphan = make_client_profile(company='Sin nada')

    assert [finding.evidence['profile'] for finding in _found('CL4')] == [orphan.pk]


def test_orphan_scan_scoped_to_one_client_reports_only_that_client(make_client_profile):
    """Fails if a client-scoped scan reports another client's orphan status."""
    mine = make_client_profile(company='Mío')
    make_client_profile(company='Ajeno')

    assert [finding.evidence['profile'] for finding in _found('CL4', 'client', mine.pk)] == [mine.pk]


# ── CL5 · project owned by a non-client ──────────────────────────────────────

def test_project_of_a_user_without_profile_is_reported(make_client_profile):
    """Fails if a project owned by a user with no profile goes unreported, or a client's project is flagged."""
    owner = make_user('sinperfil')
    project = Project.objects.create(name='Huérfano', client=owner)
    make_project(make_client_profile(company='Kore SAS'), 'Kore')

    [finding] = _found('CL5')

    assert [subject.key() for subject in finding.subjects] == [('accounts.project', project.pk), ('auth.user', owner.pk)]
    assert finding.evidence == {'project': project.pk, 'user': owner.pk, 'role': None}
    assert finding.fix_kinds == (REPORT_ONLY,)


def test_project_of_an_admin_account_is_reported_with_its_role():
    """Fails if a project owned by an admin account passes for a client project."""
    owner = make_user('equipo', role=UserProfile.ROLE_ADMIN)
    project = Project.objects.create(name='Interno', client=owner)

    [finding] = _found('CL5')

    assert finding.evidence == {'project': project.pk, 'user': owner.pk, 'role': UserProfile.ROLE_ADMIN}
    assert 'administrador' in finding.message


@pytest.mark.parametrize(('rule_id', 'live', 'archived'), [
    ('CL1', {'email': 'same@example.com'}, {'email': 'same@example.com'}),
    ('CL2', {'company': 'Kore'}, {'company': 'Kore', 'email': 'merged@temp.example.com'}),
    ('CL3', {'cedula': '1234567'}, {'cedula': '1.234.567'}),
])
def test_archived_profiles_do_not_recreate_duplicate_groups(make_client_profile, rule_id, live, archived):
    """Fails if a retired duplicate's preserved identity is reported as a fresh merge candidate."""
    make_client_profile(**live)
    make_client_profile(archived_at=ARCHIVED_AT, **archived)

    assert _found(rule_id) == []


def test_provisional_company_match_groups_clients_with_different_names(make_client_profile):
    """Fails if a shared company is ignored when the contacts have different names."""
    provisional = make_client_profile(company='Kóre SAS', first_name='Laura', email='new@temp.example.com')
    real = make_client_profile(company=' kore  sas ', first_name='Pedro')

    [finding] = _found('CL2')

    assert finding.evidence == {'key': 'kore sas', 'profiles': [provisional.pk, real.pk]}
    assert 'la empresa' in finding.message


def test_client_with_retained_income_is_not_an_orphan(make_client_profile, make_income, superuser):
    """Fails if a client with conserved accounting history is offered manual orphan deletion."""
    client = make_client_profile()
    make_income(client=client, retention_context=make_retention_context(client, superuser))

    assert _found('CL4') == []
