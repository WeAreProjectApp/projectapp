"""Viewing a client's account cannot become that client's legal decision."""
from types import SimpleNamespace

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from accounts.models import ContractSignatureEvidence, RequirementReview
from accounts.services.impersonation import impersonate
from accounts.tests.delivery_helpers import build_delivery_context, decisions, publish

pytestmark = pytest.mark.django_db


@pytest.fixture
def context():
    value = build_delivery_context()
    value.admin.is_staff = True
    value.admin.is_superuser = True
    value.admin.save(update_fields=['is_staff', 'is_superuser'])
    return value


@pytest.fixture(params=['original', 'refreshed'])
def impersonated(context, request):
    tokens = impersonate(context.admin, context.client)
    response = APIClient().post('/api/accounts/token/refresh/', {'refresh': tokens['refresh']}, format='json')
    assert response.status_code == 200
    access = {'original': tokens['access'], 'refreshed': response.data['access']}[request.param]
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
    return SimpleNamespace(api=api, access=access, refresh=response.data['refresh'])


def test_impersonation_marker_survives_token_refresh(context, impersonated):
    """Fails if refreshed tokens lose the original administrator's identity."""
    assert AccessToken(impersonated.access)['impersonated_by'] == context.admin.pk
    assert RefreshToken(impersonated.refresh)['impersonated_by'] == context.admin.pk
    assert int(AccessToken(impersonated.access)['user_id']) == context.client.pk


def test_impersonated_client_cannot_submit_a_review(context, impersonated):
    """Fails if logging in as a client can create an apparent client approval."""
    publish(context)
    url = f'/api/accounts/projects/{context.project.pk}/delivery/stages/{context.stage.pk}/review/'

    response = impersonated.api.post(url, decisions(context, (context.first, 'approved')), format='json')

    context.first.refresh_from_db()
    assert response.status_code == 403
    assert RequirementReview.objects.count() == 0
    assert context.first.review_status == 'in_review'


def test_impersonated_client_cannot_sign_a_contract(context, impersonated):
    """Fails if a support session can record the client's contractual signature."""
    context.document.signed_at = None
    context.document.signed_by = None
    context.document.save(update_fields=['signed_at', 'signed_by'])

    response = impersonated.api.post(f'/api/accounts/documents/{context.document.uuid}/sign/',
                                     {'accept': True, 'signature_name': 'Cliente'}, format='json')

    context.document.refresh_from_db()
    assert response.status_code == 403
    assert context.document.signed_at is None
    assert context.document.signed_by_id is None
    assert ContractSignatureEvidence.objects.count() == 0


def test_impersonated_client_can_read_published_delivery(context, impersonated):
    """Fails if restricting decisions also prevents the authorized support read."""
    publish(context)

    response = impersonated.api.get(f'/api/accounts/projects/{context.project.pk}/delivery/')

    assert response.status_code == 200
    assert response.data['is_admin'] is False
    assert response.data['scopes'][0]['phases'][0]['stages'][0]['title'] == 'Etapa'
