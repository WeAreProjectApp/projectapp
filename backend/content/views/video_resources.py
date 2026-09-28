"""Staff administration and access-checked range delivery for commercial videos."""
from urllib.parse import quote

from django.conf import settings
from django.http import Http404, HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from content.models import BusinessProposal, VideoResource
from content.serializers.video_resource import VideoResourceWriteSerializer
from content.services.video_resource_service import resource_payload, update_resource


def _admin_resource(request, module, language, proposal=None):
    if request.method == 'POST':
        serializer = VideoResourceWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        payload = update_resource(
            module, language, proposal=proposal, actor=request.user,
            revision=data['revision'], action=data['action'], uploaded_file=data.get('file'),
        )
    else:
        payload = resource_payload(module, language, proposal)
    return Response(payload, headers={'Cache-Control': 'no-store'})


@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def admin_module_video(request, module, language):
    return _admin_resource(request, module, language)


@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def admin_proposal_video(request, proposal_id):
    proposal = get_object_or_404(BusinessProposal, pk=proposal_id)
    return _admin_resource(request, 'proposal', proposal.language, proposal)


def _range_stream(file, start, length):
    try:
        file.seek(start)
        while length:
            chunk = file.read(min(length, 64 * 1024))
            if not chunk:
                break
            length -= len(chunk)
            yield chunk
    finally:
        file.close()


def public_video_file(request, resource_id, revision, kind):
    if request.method not in ('GET', 'HEAD'):
        return HttpResponse(status=405)
    resource = get_object_or_404(
        VideoResource.objects.select_related('proposal'),
        pk=resource_id, revision=revision, mode='uploaded',
    )
    staff = request.user.is_authenticated and request.user.is_staff
    if resource.proposal_id and not staff:
        proposal = resource.proposal
        if not proposal.is_active or proposal.is_expired:
            raise Http404
    field = resource.poster if kind == 'poster' else resource.file if kind == 'video' else None
    if not field:
        raise Http404
    content_type = 'image/webp' if kind == 'poster' else 'video/mp4'
    if getattr(settings, 'VIDEO_USE_X_ACCEL_REDIRECT', False):
        response = HttpResponse(content_type=content_type)
        response['X-Accel-Redirect'] = '/_commercial_videos/' + quote(field.name, safe='/')
    else:
        size = field.size
        start, end = 0, size - 1
        partial = request.headers.get('Range', '')
        if partial:
            try:
                unit, positions = partial.split('=', 1)
                first, last = positions.split('-', 1)
                if unit != 'bytes' or ',' in positions:
                    raise ValueError
                if first:
                    start = int(first)
                    end = min(int(last), size - 1) if last else size - 1
                else:
                    length = int(last)
                    if length <= 0:
                        raise ValueError
                    start = max(0, size - length)
                if start < 0 or start >= size or end < start:
                    raise ValueError
            except ValueError:
                return HttpResponse(status=416, headers={'Content-Range': f'bytes */{size}'})
        response = StreamingHttpResponse(
            () if request.method == 'HEAD' else _range_stream(field.open('rb'), start, end - start + 1),
            status=206 if partial else 200, content_type=content_type,
        )
        response['Content-Length'] = str(end - start + 1)
        if partial:
            response['Content-Range'] = f'bytes {start}-{end}/{size}'
    response['Accept-Ranges'] = 'bytes'
    response['Cache-Control'] = 'private, no-store' if resource.proposal_id else 'public, max-age=0, must-revalidate'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
