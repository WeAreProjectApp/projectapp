"""Shared shape for the two surfaces that page over the send log.

The accounting Historial and a client's email modal read the same rows
through different scopes — one by the module's template keys, the other by
the client the row is filed under — but the panel pages both with the same
component. Keeping the envelope and the body payload here is what stops the
two from drifting into two dialects of the same response.
"""

from rest_framework import status
from rest_framework.response import Response

from content.api_errors import error_response

HISTORY_PAGE_SIZE = 20


def paginated_history_response(
    queryset,
    params,
    serializer_class,
    *,
    row_enricher=None,
):
    """Serialize one 20-row page, optionally enriching the sliced rows."""
    total = queryset.count()
    try:
        page = max(1, int(params.get('page', 1)))
    except (ValueError, TypeError):
        page = 1
    offset = (page - 1) * HISTORY_PAGE_SIZE
    num_pages = max(1, -(-total // HISTORY_PAGE_SIZE))

    page_rows = queryset[offset:offset + HISTORY_PAGE_SIZE]
    if row_enricher is not None:
        page_rows = row_enricher(page_rows)
    serializer = serializer_class(page_rows, many=True)
    return Response({
        'results': serializer.data,
        'count': total,
        'page': page,
        'num_pages': num_pages,
    })


def email_body_response(log):
    """The message as delivered, or the 404 that says why there is none."""
    from content.services.email_privacy_policy import credential_email
    if credential_email(log.template_key):
        return error_response('El contenido de acceso no está disponible.', code='credential_content_protected', status=403)
    if log.body is None:
        return error_response(
            'Este envío es anterior a que se guardara el cuerpo de los '
            'correos, así que no hay nada que mostrar.',
            code='body_not_stored',
            status=status.HTTP_404_NOT_FOUND,
        )
    return Response({
        'id': log.id,
        'subject': log.subject,
        'recipient': log.recipient,
        'sent_at': log.sent_at,
        'html': log.body.html,
        'text': log.body.text,
    })
