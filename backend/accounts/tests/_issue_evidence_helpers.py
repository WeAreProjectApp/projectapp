"""Shared real-domain fixtures for ticket option and evidence regressions."""
import io

import pytest
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import override_settings
from pypdf import PdfWriter

from accounts.models import ContractAmendment, UserProfile
from accounts.tests.delivery_helpers import RECORDED_AT, build_delivery_context
from accounts.tests.issue_browser_server import assert_memory_mailers, memory_mailers
from content.models import Document


@pytest.fixture(autouse=True)
def memory_only_mail(settings):
    # Object-permission cases use force_authenticate; keep fixture creation cheap.
    with override_settings(MAILERS=memory_mailers(settings),
                           PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]):
        assert_memory_mailers()
        yield
        assert_memory_mailers()


@pytest.fixture
def context(memory_only_mail):
    value = build_delivery_context()
    value.outsider = User.objects.create_user('issue-evidence-outsider', 'outsider@example.test')
    UserProfile.objects.create(user=value.outsider, role='client')
    return value


def pdf_bytes():
    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(output)
    return output.getvalue()


def evidence_document(context, *, title='Evidencia del ticket', **fields):
    document = Document.objects.create(
        title=title, project=context.project, client_user=context.client,
        created_by=context.admin, is_client_visible=True, **fields,
    )
    document.generated_file.save('evidence.pdf', ContentFile(pdf_bytes()))
    return document


def amendment(context, *, key='amendment'):
    document = evidence_document(context, title=f'Otrosí {key}')
    document.requires_signature = True
    document.signed_by = context.client
    document.signed_at = RECORDED_AT
    document.signature_name = 'Cliente'
    document.save()
    return ContractAmendment.objects.create(
        contract=context.contract, key=key, title=f'Otrosí {key}', document=document,
        client_visible=True,
    )
