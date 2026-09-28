from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from content.serializers.document_move import MoveDocumentsSerializer
from content.services.document_move_service import DocumentMoveError, move_documents
from content.services.document_write_service import document_write_options


@api_view(["POST"])
@permission_classes([IsAdminUser])
@document_write_options
def move_document_batch(request):
    serializer = MoveDocumentsSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        return Response(move_documents(**serializer.validated_data, actor=request.user))
    except DocumentMoveError as exc:
        return Response(
            {
                "ok": False,
                "code": "move_batch_rejected",
                "detail": str(exc),
                "results": exc.results,
            },
            status=409,
        )
