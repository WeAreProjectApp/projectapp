"""Document, folder, thread and secure-link factories for the data-integrity rule tests.

They write straight through the ORM on purpose: the rules exist to catch rows
the services would refuse to create.
"""
import uuid
from datetime import timedelta

from django.utils import timezone

from content.models import (
    CommunicationFolder, CommunicationMessage, CommunicationThread, Document, DocumentFolder,
    DocumentThread, DocumentThreadItem, DocumentType,
)


def make_folder(name='Contratos', **kwargs):
    return DocumentFolder.objects.create(name=name, **kwargs)


def project_root(project):
    """The managed root folder a project provisions when it is created."""
    return DocumentFolder.objects.get(managed_project=project)


def make_document(title='Acta de inicio', **kwargs):
    return Document.objects.create(title=title, **kwargs)


def make_collection_account(title='Cuenta de cobro', **kwargs):
    kind, _ = DocumentType.objects.get_or_create(code='collection_account', defaults={'name': 'Cuenta de cobro'})
    return Document.objects.create(title=title, document_type=kind, **kwargs)


def make_document_thread(documents, title='Hilo documental'):
    thread = DocumentThread.objects.create(title=title)
    for position, document in enumerate(documents):
        DocumentThreadItem.objects.create(thread=thread, document=document, position=position,
                                          occurred_on=timezone.localdate())
    return thread


def make_thread(client, title='Conversación', **kwargs):
    return CommunicationThread.objects.create(client=client, title=title, **kwargs)


def root_thread(project):
    """The managed root thread a project provisions when it is created."""
    return CommunicationThread.objects.get(managed_project=project)


def backdate(thread, days):
    CommunicationThread.objects.filter(pk=thread.pk).update(created_at=timezone.now() - timedelta(days=days))


def make_message(thread):
    return CommunicationMessage.objects.create(
        thread=thread, channel=CommunicationMessage.Channel.WHATSAPP,
        direction=CommunicationMessage.Direction.INCOMING, status=CommunicationMessage.Status.RECEIVED,
        content='Hola', occurred_at=timezone.now(),
    )


def make_communication_folder(client, name='Contratos', **kwargs):
    return CommunicationFolder.objects.create(client=client, name=name, **kwargs)


def make_secure_link(client, project, title='Acceso al hosting'):
    from secure_links.models import SecureLink
    return SecureLink.objects.create(
        token_hash=SecureLink.hash_token(uuid.uuid4().hex), token_encrypted='cifrado', secret_type='credentials',
        title=title, payload_encrypted='cifrado', origin=SecureLink.Origin.PANEL, client=client, project=project,
        expires_at=timezone.now() + timedelta(days=7),
    )
