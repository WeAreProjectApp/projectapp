"""Targeted tests for the WebAppDiagnostic feature (JSON sections model)."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from content.models import DiagnosticChangeLog, WebAppDiagnostic
from content.services import diagnostic_service

# ── Service tests ──────────────────────────────────────────────────────────

def test_create_diagnostic_seeds_eight_sections(diagnostic):
    """Creating a diagnostic must seed the full set of 8 JSON sections."""
    sections = diagnostic.sections.order_by('order')
    assert sections.count() == 8
    types = list(sections.values_list('section_type', flat=True))
    assert types == [
        'purpose', 'radiography', 'categories', 'delivery_structure',
        'executive_summary', 'cost', 'timeline', 'scope',
    ]
    # Each section has a content_json dict with at least a title.
    for section in sections:
        assert isinstance(section.content_json, dict)
        assert section.content_json.get('title')


def test_create_diagnostic_writes_creation_change_log(diagnostic):
    logs = diagnostic.change_logs.filter(
        change_type=DiagnosticChangeLog.ChangeType.CREATED,
    )
    assert logs.count() == 1


def test_categories_seed_includes_fourteen_entries(diagnostic):
    categories_section = diagnostic.sections.get(section_type='categories')
    entries = categories_section.content_json.get('categories', [])
    assert len(entries) == 14
    keys = {e['key'] for e in entries}
    # Sanity-check a few of the canonical categories.
    assert {'architecture', 'security', 'testing', 'documentation'} <= keys


def test_reset_section_restores_default_content(diagnostic):
    section = diagnostic.sections.get(section_type='scope')
    section.content_json = {'considerations': ['edited']}
    section.save()

    diagnostic_service.reset_section(section)
    section.refresh_from_db()
    assert section.content_json.get('considerations') != ['edited']
    assert section.content_json.get('title') == 'Alcance y Consideraciones'


def test_transition_status_validates_and_stamps_timestamp(diagnostic):
    diagnostic_service.transition_status(
        diagnostic, WebAppDiagnostic.Status.SENT,
    )
    diagnostic.refresh_from_db()
    assert diagnostic.status == WebAppDiagnostic.Status.SENT
    assert diagnostic.initial_sent_at is not None

    # Invalid jump SENT → FINISHED must raise (FINISHED only after ACCEPTED).
    with pytest.raises(ValueError, match='invalid_transition'):
        diagnostic_service.transition_status(
            diagnostic, WebAppDiagnostic.Status.FINISHED,
        )


def test_transition_status_logs_change(diagnostic):
    diagnostic_service.transition_status(
        diagnostic, WebAppDiagnostic.Status.SENT,
    )
    log = diagnostic.change_logs.filter(
        change_type=DiagnosticChangeLog.ChangeType.STATUS_CHANGE,
    ).first()
    assert log is not None
    assert log.old_value == WebAppDiagnostic.Status.DRAFT
    assert log.new_value == WebAppDiagnostic.Status.SENT


def test_register_view_increments_count(diagnostic):
    assert diagnostic.view_count == 0
    diagnostic_service.register_view(diagnostic)
    diagnostic_service.register_view(diagnostic)
    assert diagnostic.view_count == 2
    assert diagnostic.last_viewed_at is not None


def test_visible_sections_respects_status_and_phase(diagnostic):
    # DRAFT → no visible sections.
    assert diagnostic_service.visible_sections(diagnostic) == []

    # Initial SENT (no final_sent_at) → only `initial` + `both` visibility.
    diagnostic_service.transition_status(diagnostic, WebAppDiagnostic.Status.SENT)
    visible = diagnostic_service.visible_sections(diagnostic)
    visibilities = {s.visibility for s in visible}
    assert visibilities <= {'initial', 'both'}
    # Delivery structure is initial-only; executive summary is final-only.
    types = {s.section_type for s in visible}
    assert 'delivery_structure' in types
    assert 'executive_summary' not in types

    # Final SENT → swaps in `final` + `both`.
    diagnostic_service.transition_status(diagnostic, WebAppDiagnostic.Status.NEGOTIATING)
    diagnostic_service.transition_status(diagnostic, WebAppDiagnostic.Status.SENT)
    visible = diagnostic_service.visible_sections(diagnostic)
    types = {s.section_type for s in visible}
    assert 'executive_summary' in types
    assert 'delivery_structure' not in types


# ── API tests ──────────────────────────────────────────────────────────────

def test_create_diagnostic_endpoint(admin_client, diag_client_profile):
    response = admin_client.post(
        '/api/diagnostics/create/',
        {'client_id': diag_client_profile.id, 'language': 'es'},
        format='json',
    )
    assert response.status_code == 201
    body = response.json()
    assert body['status'] == 'draft'
    assert len(body['sections']) == 8


def test_new_english_diagnostic_uses_english_system_titles(admin_client, diag_client_profile):
    response = admin_client.post('/api/diagnostics/create/', {
        'client_id': diag_client_profile.pk, 'language': 'en',
    }, format='json')

    assert response.status_code == 201
    diagnostic = WebAppDiagnostic.objects.get(pk=response.data['id'])
    assert diagnostic.title.startswith('Diagnostic — ')
    assert list(diagnostic.sections.order_by('order').values_list('title', flat=True)) == [
        'Purpose', 'Application Overview', 'Evaluation Categories', 'Deliverable Structure',
        'Executive Summary', 'Cost and Payment Terms', 'Timeline', 'Scope and Considerations',
    ]


@pytest.mark.parametrize('language', ['es', 'en'])
def test_general_defaults_save_preserves_custom_diagnostic_template(admin_client, diag_client_profile, language):
    from content.models import DiagnosticDefaultConfig
    custom = [{
        'section_type': 'purpose', 'title': f'Título elegido {language}', 'order': 4,
        'content_json': {'title': 'Un encabezado propio', 'paragraphs': ['Texto propio']},
        'visibility': 'both', 'is_enabled': True,
    }]
    DiagnosticDefaultConfig.objects.update_or_create(language=language, defaults={'sections_json': custom})

    saved = admin_client.put('/api/diagnostics/defaults/', {
        'language': language, 'default_currency': 'USD',
    }, format='json')
    loaded = admin_client.get('/api/diagnostics/defaults/', {'lang': language})
    created = admin_client.post('/api/diagnostics/create/', {
        'client_id': diag_client_profile.pk, 'language': language, 'title': 'Diagnóstico personalizado',
    }, format='json')

    assert saved.status_code == 200
    assert loaded.data['sections_json'] == custom
    assert 'effective_sections_json' not in loaded.data
    assert created.status_code == 201
    diagnostic = WebAppDiagnostic.objects.get(pk=created.data['id'])
    section = diagnostic.sections.get()
    assert (section.title, section.order, section.content_json) == (
        custom[0]['title'], custom[0]['order'], custom[0]['content_json'],
    )


def test_create_diagnostic_requires_client_id(admin_client):
    response = admin_client.post('/api/diagnostics/create/', {}, format='json')
    assert response.status_code == 400
    assert response.json()['code'] == 'client_id_required'


def test_send_initial_transitions_status(admin_client, diagnostic, mailoutbox):
    response = admin_client.post(
        f'/api/diagnostics/{diagnostic.id}/send-initial/', {}, format='json',
    )
    assert response.status_code == 200
    diagnostic.refresh_from_db()
    assert diagnostic.status == 'sent'
    assert diagnostic.initial_sent_at is not None
    assert len(mailoutbox) == 1
    assert 'diag@example.com' in mailoutbox[0].to


def test_public_retrieve_does_not_increment_view_count(api_client, diagnostic):
    """GET /public/ only returns data; only POST /track/ bumps view_count.

    This avoids double-counting (frontend always does GET + POST /track/).
    """
    diagnostic_service.transition_status(diagnostic, WebAppDiagnostic.Status.SENT)
    response = api_client.get(f'/api/diagnostics/public/{diagnostic.uuid}/')
    assert response.status_code == 200
    body = response.json()
    assert body['client_name']
    returned_types = {s['section_type'] for s in body['sections']}
    assert 'executive_summary' not in returned_types
    diagnostic.refresh_from_db()
    assert diagnostic.view_count == 0

    # The track endpoint is what creates the event + bumps the counter.
    api_client.post(
        f'/api/diagnostics/public/{diagnostic.uuid}/track/',
        {'session_id': 'abc123'}, format='json',
    )
    diagnostic.refresh_from_db()
    assert diagnostic.view_count == 1
    assert diagnostic.view_events.count() == 1


def test_staff_session_does_not_track_diagnostic_view(
    client,
    admin_user,
    diagnostic,
):
    diagnostic_service.transition_status(diagnostic, WebAppDiagnostic.Status.SENT)
    client.force_login(admin_user)

    response = client.post(
        f'/api/diagnostics/public/{diagnostic.uuid}/track/',
        {'session_id': 'internal-preview'},
        content_type='application/json',
    )

    diagnostic.refresh_from_db()
    assert response.status_code == 200
    assert response.json()['status'] == 'skipped'
    assert diagnostic.view_count == 0
    assert diagnostic.last_viewed_at is None
    assert diagnostic.view_events.count() == 0


def test_staff_session_does_not_track_diagnostic_section(
    client,
    admin_user,
    diagnostic,
):
    diagnostic_service.transition_status(diagnostic, WebAppDiagnostic.Status.SENT)
    client.force_login(admin_user)

    response = client.post(
        f'/api/diagnostics/public/{diagnostic.uuid}/track-section/',
        {
            'session_id': 'internal-preview',
            'section_type': 'purpose',
            'section_title': 'Propósito',
            'time_spent_seconds': 8,
        },
        content_type='application/json',
    )

    assert response.status_code == 200
    assert response.json()['status'] == 'skipped'
    assert diagnostic.view_events.count() == 0


def test_track_section_rejects_non_numeric_time_spent(api_client, diagnostic):
    """Passing a non-numeric time_spent_seconds returns 400, not 500."""
    diagnostic_service.transition_status(diagnostic, WebAppDiagnostic.Status.SENT)
    response = api_client.post(
        f'/api/diagnostics/public/{diagnostic.uuid}/track-section/',
        {
            'session_id': 'abc123',
            'section_type': 'purpose',
            'section_title': 'Propósito',
            'time_spent_seconds': 'abc',
        },
        format='json',
    )
    assert response.status_code == 400
    assert response.json().get('code') == 'invalid_time_spent_seconds'


def test_track_section_respects_client_entered_at(api_client, diagnostic):
    """entered_at from payload is stored verbatim; fallback is now() if missing."""
    from content.models import DiagnosticSectionView
    diagnostic_service.transition_status(diagnostic, WebAppDiagnostic.Status.SENT)
    response = api_client.post(
        f'/api/diagnostics/public/{diagnostic.uuid}/track-section/',
        {
            'session_id': 'abc123',
            'section_type': 'purpose',
            'section_title': 'Propósito',
            'time_spent_seconds': 5,
            'entered_at': '2026-04-01T10:30:00Z',
        },
        format='json',
    )
    assert response.status_code == 200
    section_view = DiagnosticSectionView.objects.filter(
        view_event__diagnostic=diagnostic, section_type='purpose',
    ).first()
    assert section_view is not None
    assert section_view.entered_at.isoformat().startswith('2026-04-01T10:30:00')


def test_track_reuses_view_event_for_same_session(api_client, diagnostic):
    """Two POST /track/ with the same session_id collapse to one event row."""
    diagnostic_service.transition_status(diagnostic, WebAppDiagnostic.Status.SENT)
    url = f'/api/diagnostics/public/{diagnostic.uuid}/track/'
    r1 = api_client.post(url, {'session_id': 'session-xyz'}, format='json')
    r2 = api_client.post(url, {'session_id': 'session-xyz'}, format='json')
    assert r1.status_code == 200
    assert r2.status_code == 200
    diagnostic.refresh_from_db()
    # view_count is bumped on each register_view call (second-click re-visit
    # is a real signal), but the view_event row is unique per session.
    assert diagnostic.view_events.filter(session_id='session-xyz').count() == 1


def test_public_respond_accept_finalizes_status(api_client, diagnostic):
    diagnostic_service.transition_status(diagnostic, WebAppDiagnostic.Status.SENT)
    diagnostic_service.transition_status(diagnostic, WebAppDiagnostic.Status.NEGOTIATING)
    diagnostic_service.transition_status(diagnostic, WebAppDiagnostic.Status.SENT)

    response = api_client.post(
        f'/api/diagnostics/public/{diagnostic.uuid}/respond/',
        {'decision': 'accept'},
        format='json',
    )
    assert response.status_code == 200
    diagnostic.refresh_from_db()
    assert diagnostic.status == 'accepted'
    assert diagnostic.responded_at is not None


def test_update_section_persists_content_json(admin_client, diagnostic):
    section = diagnostic.sections.get(section_type='scope')
    response = admin_client.patch(
        f'/api/diagnostics/{diagnostic.id}/sections/{section.id}/update/',
        {
            'content_json': {
                'title': 'Alcance y Consideraciones',
                'considerations': ['Uno', 'Dos'],
            },
            'is_enabled': True,
        },
        format='json',
    )
    assert response.status_code == 200
    section.refresh_from_db()
    assert section.content_json['considerations'] == ['Uno', 'Dos']


def test_bulk_update_sections(admin_client, diagnostic):
    sections = list(diagnostic.sections.order_by('order'))
    payload = [
        {'id': sections[0].id, 'is_enabled': False},
        {'id': sections[1].id, 'title': 'Radiografía editada'},
    ]
    response = admin_client.post(
        f'/api/diagnostics/{diagnostic.id}/sections/bulk-update/',
        {'sections': payload},
        format='json',
    )
    assert response.status_code == 200
    sections[0].refresh_from_db()
    sections[1].refresh_from_db()
    assert sections[0].is_enabled is False
    assert sections[1].title == 'Radiografía editada'


def test_activity_log_endpoints(admin_client, diagnostic):
    response = admin_client.post(
        f'/api/diagnostics/{diagnostic.id}/activity/create/',
        {'change_type': 'note', 'description': 'Primer seguimiento con el cliente.'},
        format='json',
    )
    assert response.status_code == 201

    response = admin_client.get(f'/api/diagnostics/{diagnostic.id}/activity/')
    assert response.status_code == 200
    body = response.json()
    assert any(entry['change_type'] == 'note' for entry in body)


def test_track_section_view_records_time(api_client, diagnostic):
    diagnostic_service.transition_status(diagnostic, WebAppDiagnostic.Status.SENT)
    api_client.post(
        f'/api/diagnostics/public/{diagnostic.uuid}/track/',
        {'session_id': 'sess-1'}, format='json',
    )
    response = api_client.post(
        f'/api/diagnostics/public/{diagnostic.uuid}/track-section/',
        {
            'session_id': 'sess-1',
            'section_type': 'purpose',
            'section_title': 'Propósito',
            'time_spent_seconds': 12.5,
        },
        format='json',
    )
    assert response.status_code == 200
    diagnostic.refresh_from_db()
    event = diagnostic.view_events.first()
    assert event is not None
    view = event.section_views.first()
    assert view is not None
    assert view.section_type == 'purpose'
    assert view.time_spent_seconds == pytest.approx(12.5)


def test_analytics_endpoint_summary(admin_client, api_client, diagnostic):
    diagnostic_service.transition_status(diagnostic, WebAppDiagnostic.Status.SENT)
    api_client.post(
        f'/api/diagnostics/public/{diagnostic.uuid}/track/',
        {'session_id': 'sess-x'}, format='json',
    )
    api_client.post(
        f'/api/diagnostics/public/{diagnostic.uuid}/track-section/',
        {
            'session_id': 'sess-x',
            'section_type': 'purpose',
            'section_title': 'Propósito',
            'time_spent_seconds': 9.0,
        },
        format='json',
    )

    response = admin_client.get(f'/api/diagnostics/{diagnostic.id}/analytics/')
    assert response.status_code == 200
    body = response.json()
    assert body['unique_sessions'] == 1
    purpose_row = next(
        (row for row in body['sections'] if row['section_type'] == 'purpose'),
        None,
    )
    assert purpose_row is not None
    assert purpose_row['total_time_seconds'] == pytest.approx(9.0)


# ── Edge cases ─────────────────────────────────────────────────────────────

def test_bulk_update_rejects_non_list_payload(admin_client, diagnostic):
    response = admin_client.post(
        f'/api/diagnostics/{diagnostic.id}/sections/bulk-update/',
        {'sections': {'id': 1}},
        format='json',
    )
    assert response.status_code == 400
    assert response.json()['code'] == 'sections_must_be_list'


def test_bulk_update_skips_unknown_section_ids(admin_client, diagnostic):
    valid = diagnostic.sections.first()
    payload = [
        {'id': 999_999, 'title': 'ghost'},  # skipped silently
        {'id': valid.id, 'title': 'Edited'},
    ]
    response = admin_client.post(
        f'/api/diagnostics/{diagnostic.id}/sections/bulk-update/',
        {'sections': payload}, format='json',
    )
    assert response.status_code == 200
    valid.refresh_from_db()
    assert valid.title == 'Edited'


def test_respond_public_rejects_invalid_decision(api_client, diagnostic):
    response = api_client.post(
        f'/api/diagnostics/public/{diagnostic.uuid}/respond/',
        {'decision': 'maybe'}, format='json',
    )
    assert response.status_code == 400
    assert response.json()['code'] == 'invalid_decision'


def test_respond_public_conflict_when_status_not_sent(api_client, diagnostic):
    # DRAFT cannot transition to ACCEPTED — expect 409 from the view.
    response = api_client.post(
        f'/api/diagnostics/public/{diagnostic.uuid}/respond/',
        {'decision': 'accept'}, format='json',
    )
    assert response.status_code == 409


def test_create_activity_rejects_invalid_change_type(admin_client, diagnostic):
    response = admin_client.post(
        f'/api/diagnostics/{diagnostic.id}/activity/create/',
        {'change_type': 'bogus', 'description': 'x'}, format='json',
    )
    assert response.status_code == 400
    assert response.json()['code'] == 'invalid_change_type'


def test_create_activity_requires_description(admin_client, diagnostic):
    response = admin_client.post(
        f'/api/diagnostics/{diagnostic.id}/activity/create/',
        {'change_type': 'note', 'description': '   '}, format='json',
    )
    assert response.status_code == 400
    assert response.json()['code'] == 'description_required'


def test_track_section_requires_session_and_type(api_client, diagnostic):
    response = api_client.post(
        f'/api/diagnostics/public/{diagnostic.uuid}/track-section/',
        {'section_type': 'purpose'}, format='json',
    )
    assert response.status_code == 400


def test_public_retrieve_on_draft_is_hidden(api_client, diagnostic):
    """DRAFT diagnostics must not leak client metadata through the public URL."""
    response = api_client.get(f'/api/diagnostics/public/{diagnostic.uuid}/')
    assert response.status_code == 404
    assert response.json()['code'] == 'not_available'


def test_public_render_context_is_whitelisted(api_client, diagnostic):
    diagnostic_service.transition_status(diagnostic, WebAppDiagnostic.Status.SENT)
    response = api_client.get(f'/api/diagnostics/public/{diagnostic.uuid}/')
    assert response.status_code == 200
    keys = set(response.json()['render_context'].keys())
    # Admin-only fields must NOT bleed into the public response.
    assert 'controllers_disconnected' not in keys
    assert 'routes_protected' not in keys
    assert 'routes_public' not in keys
    # A client-facing staple must be present.
    assert 'client_name' in keys


def test_update_section_logs_section_updated_change(admin_client, diagnostic):
    section = diagnostic.sections.get(section_type='scope')
    admin_client.patch(
        f'/api/diagnostics/{diagnostic.id}/sections/{section.id}/update/',
        {'content_json': {'title': 'Alcance', 'considerations': ['x']}},
        format='json',
    )
    log = diagnostic.change_logs.filter(
        change_type=DiagnosticChangeLog.ChangeType.SECTION_UPDATED,
    ).first()
    assert log is not None
    assert log.field_name == 'scope'


def test_public_pdf_blocked_on_draft(api_client, diagnostic):
    response = api_client.get(f'/api/diagnostics/public/{diagnostic.uuid}/pdf/')
    assert response.status_code == 404


def test_public_pdf_returns_pdf_when_sent(api_client, diagnostic):
    diagnostic_service.transition_status(diagnostic, WebAppDiagnostic.Status.SENT)
    response = api_client.get(f'/api/diagnostics/public/{diagnostic.uuid}/pdf/')
    assert response.status_code == 200
    assert response['Content-Type'] == 'application/pdf'
    assert 'attachment' in response['Content-Disposition']
    assert 'Diagnostico_' in response['Content-Disposition']
    body = response.content
    assert body.startswith(b'%PDF')
    assert len(body) > 500


def test_send_initial_response_exposes_email_ok(admin_client, diagnostic):
    response = admin_client.post(
        f'/api/diagnostics/{diagnostic.id}/send-initial/', {}, format='json',
    )
    assert response.status_code == 200
    assert 'email_ok' in response.json()


# ── Status transitions ─────────────────────────────────────────────────────

def test_mark_in_analysis_transitions_to_negotiating(admin_client, diagnostic):
    diagnostic_service.transition_status(diagnostic, WebAppDiagnostic.Status.SENT)
    response = admin_client.post(
        f'/api/diagnostics/{diagnostic.id}/mark-in-analysis/', {}, format='json',
    )
    assert response.status_code == 200
    diagnostic.refresh_from_db()
    assert diagnostic.status == WebAppDiagnostic.Status.NEGOTIATING


def test_send_final_transitions_back_to_sent(admin_client, diagnostic):
    diagnostic_service.transition_status(diagnostic, WebAppDiagnostic.Status.SENT)
    diagnostic_service.transition_status(diagnostic, WebAppDiagnostic.Status.NEGOTIATING)
    response = admin_client.post(
        f'/api/diagnostics/{diagnostic.id}/send-final/', {}, format='json',
    )
    assert response.status_code == 200
    assert 'email_ok' in response.json()
    diagnostic.refresh_from_db()
    assert diagnostic.status == WebAppDiagnostic.Status.SENT


def test_mark_in_analysis_rejects_invalid_transition(admin_client, diagnostic):
    # DRAFT → NEGOTIATING is not a valid transition.
    response = admin_client.post(
        f'/api/diagnostics/{diagnostic.id}/mark-in-analysis/', {}, format='json',
    )
    assert response.status_code == 400


# ── Analytics CSV export ───────────────────────────────────────────────────

def test_export_analytics_csv_returns_text_csv(admin_client, diagnostic):
    response = admin_client.get(f'/api/diagnostics/{diagnostic.id}/analytics/csv/')
    assert response.status_code == 200
    assert response['Content-Type'] == 'text/csv'


def test_export_analytics_csv_contains_diagnostic_title(admin_client, diagnostic):
    response = admin_client.get(f'/api/diagnostics/{diagnostic.id}/analytics/csv/')
    content = response.content.decode()
    assert diagnostic.title in content


def test_export_analytics_csv_has_section_engagement_header(admin_client, diagnostic):
    response = admin_client.get(f'/api/diagnostics/{diagnostic.id}/analytics/csv/')
    content = response.content.decode()
    assert 'SECTION ENGAGEMENT' in content


# ── Attachment CRUD ────────────────────────────────────────────────────────

def _minimal_pdf():
    return SimpleUploadedFile('test.pdf', b'%PDF-1.4 fake content', content_type='application/pdf')


def test_upload_attachment_returns_201(admin_client, diagnostic):
    response = admin_client.post(
        f'/api/diagnostics/{diagnostic.id}/attachments/upload/',
        {'file': _minimal_pdf()},
        format='multipart',
    )
    assert response.status_code == 201
    assert 'id' in response.json()


def test_upload_attachment_rejects_invalid_extension(admin_client, diagnostic):
    bad_file = SimpleUploadedFile('malware.exe', b'MZ fake', content_type='application/octet-stream')
    response = admin_client.post(
        f'/api/diagnostics/{diagnostic.id}/attachments/upload/',
        {'file': bad_file},
        format='multipart',
    )
    assert response.status_code == 400
    assert 'no permitido' in response.json()['error']


def test_upload_attachment_rejects_missing_file(admin_client, diagnostic):
    response = admin_client.post(
        f'/api/diagnostics/{diagnostic.id}/attachments/upload/',
        {},
        format='multipart',
    )
    assert response.status_code == 400


def test_delete_attachment_returns_204(admin_client, diagnostic):
    upload = admin_client.post(
        f'/api/diagnostics/{diagnostic.id}/attachments/upload/',
        {'file': _minimal_pdf()},
        format='multipart',
    )
    attachment_id = upload.json()['id']
    response = admin_client.delete(
        f'/api/diagnostics/{diagnostic.id}/attachments/{attachment_id}/delete/',
    )
    assert response.status_code == 204


def test_delete_generated_attachment_returns_400(admin_client, diagnostic):
    from django.core.files.base import ContentFile

    from content.models import DiagnosticAttachment
    attachment = DiagnosticAttachment.objects.create(
        diagnostic=diagnostic,
        document_type=DiagnosticAttachment.DOC_TYPE_CONFIDENTIALITY,
        title='Generated NDA',
        file=ContentFile(b'%PDF-1.4 fake', name='nda.pdf'),
        is_generated=True,
    )
    response = admin_client.delete(
        f'/api/diagnostics/{diagnostic.id}/attachments/{attachment.id}/delete/',
    )
    assert response.status_code == 400


# ── Diagnostic defaults ────────────────────────────────────────────────────

def test_diagnostic_defaults_get_returns_fallback_config(admin_client):
    response = admin_client.get('/api/diagnostics/defaults/?lang=es')
    assert response.status_code == 200
    body = response.json()
    assert body['language'] == 'es'
    assert 'payment_initial_pct' in body


def test_diagnostic_defaults_put_creates_db_config(admin_client):
    response = admin_client.put(
        '/api/diagnostics/defaults/',
        {
            'language': 'es',
            'payment_initial_pct': 60,
            'payment_final_pct': 40,
            'default_currency': 'COP',
            'expiration_days': 21,
            'reminder_days': 7,
            'urgency_reminder_days': 14,
        },
        format='json',
    )
    assert response.status_code == 200
    assert response.json()['payment_initial_pct'] == 60


def test_diagnostic_defaults_get_returns_invalid_lang_400(admin_client):
    response = admin_client.get('/api/diagnostics/defaults/?lang=fr')
    assert response.status_code == 400


def test_reset_diagnostic_defaults_deletes_config(admin_client):
    # First create a config, then reset it.
    admin_client.put(
        '/api/diagnostics/defaults/',
        {
            'language': 'es',
            'payment_initial_pct': 60,
            'payment_final_pct': 40,
            'default_currency': 'COP',
            'expiration_days': 21,
            'reminder_days': 7,
            'urgency_reminder_days': 14,
        },
        format='json',
    )
    response = admin_client.post(
        '/api/diagnostics/defaults/reset/',
        {'language': 'es'},
        format='json',
    )
    assert response.status_code == 200
    assert response.json()['deleted'] is True


# ── Confidentiality PDF ────────────────────────────────────────────────────

def test_generate_confidentiality_pdf_view_returns_attachment(admin_client, diagnostic):
    from content.models import ConfidentialityTemplate
    ConfidentialityTemplate.objects.create(
        name='Default NDA',
        content_markdown='Acuerdo entre {client_full_name} y {contractor_full_name}.',
        is_default=True,
    )
    response = admin_client.post(
        f'/api/diagnostics/{diagnostic.id}/confidentiality/generate/',
        {},
        format='json',
    )
    assert response.status_code == 200
    assert 'attachment' in response.json()
