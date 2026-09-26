from content.api_errors import error_response
from django.contrib.auth import get_user
from django.db.models import Q
from django.shortcuts import get_object_or_404
from projectapp.recaptcha import CaptchaError, verify_captcha
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response

from . import services
from .catalog import CatalogError, catalog_payload
from .models import SecureLink
from .serializers import (
    FilterSerializer,
    PanelCreateSerializer,
    PanelUpdateSerializer,
    PublicCreateSerializer,
    ReactivateSerializer,
    SecureLinkEventSerializer,
    SecureLinkSerializer,
    TokenSerializer,
)
from .tasks import notify_team_secure_link_received
from .throttles import SecureLinkAccessThrottle, SecureLinkCreateThrottle

PAGE_SIZE = 25


def admin_api(methods):
    def decorate(view):
        return api_view(methods)(authentication_classes([SessionAuthentication])(permission_classes([IsAdminUser])(view)))
    return decorate


def public_api(methods, throttle):
    # No DRF authentication: anonymous and CSRF-free. The underlying Django
    # session is read only to recognise staff (see _session_staff).
    def decorate(view):
        return api_view(methods)(authentication_classes([])(permission_classes([AllowAny])(throttle_classes([throttle])(view))))
    return decorate


def private(response):
    response['Cache-Control'] = 'no-store, max-age=0'
    response['Pragma'] = 'no-cache'
    return response


def _session_staff(request):
    user = get_user(getattr(request, '_request', request))
    return user if user.is_authenticated and user.is_staff else None


def _service_error(exc):
    return private(error_response(exc.message, code=exc.code, status=exc.status))


def _invalid(errors):
    return error_response('Revisa los datos del formulario.', code='invalid', errors=errors)


def _validated(serializer_class, data):
    serializer = serializer_class(data=data)
    return serializer, serializer.is_valid()


def _link(pk):
    return get_object_or_404(SecureLink.objects.select_related('client__user', 'project', 'created_by'), pk=pk)


@admin_api(['GET'])
def link_list(request):
    serializer, valid = _validated(FilterSerializer, request.query_params)
    if not valid:
        return _invalid(serializer.errors)
    data = serializer.validated_data
    query = SecureLink.objects.select_related('client__user', 'project', 'created_by')
    if data.get('origin'):
        query = query.filter(origin=data['origin'])
    if data.get('received'):
        query = query.filter(origin=SecureLink.Origin.PUBLIC)
    for field in ('client', 'project'):
        if field in data:
            query = query.filter(**{f'{field}_id': data[field]})
    if data.get('search'):
        term = data['search']
        query = query.filter(
            Q(title__icontains=term) | Q(creator_name__icontains=term) | Q(creator_email__icontains=term)
            | Q(client__user__first_name__icontains=term) | Q(client__user__last_name__icontains=term)
            | Q(client__company_name__icontains=term) | Q(project__name__icontains=term)
        )
    counts = {status: query.with_status(status).count() for status in SecureLink.STATUSES}
    counts['all'] = query.count()
    if data.get('status'):
        query = query.with_status(data['status'])
    total = query.count()
    page = data['page']
    rows = query[(page - 1) * PAGE_SIZE:page * PAGE_SIZE]
    return Response({
        'results': SecureLinkSerializer(rows, many=True).data,
        'count': total,
        'page': page,
        'page_size': PAGE_SIZE,
        'counts': counts,
        'unopened_received': services.unopened_received_count(),
        'public_create_url': services.public_create_url(),
    })


@admin_api(['POST'])
def link_create(request):
    serializer, valid = _validated(PanelCreateSerializer, request.data)
    if not valid:
        return _invalid(serializer.errors)
    data = serializer.validated_data
    try:
        link, url = services.create_link(
            origin=SecureLink.Origin.PANEL, actor=request.user,
            meta=services.RequestMeta.from_request(request), **data,
        )
    except CatalogError as exc:
        return _invalid(exc.errors)
    except services.SecureLinkError as exc:
        return _service_error(exc)
    return private(Response({**SecureLinkSerializer(link).data, 'url': url}, status=201))


@admin_api(['GET', 'PATCH', 'DELETE'])
def link_detail(request, pk):
    link = _link(pk)
    if request.method == 'DELETE':
        link.delete()
        return Response(status=204)
    if request.method == 'PATCH':
        serializer = PanelUpdateSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return _invalid(serializer.errors)
        try:
            link = services.update_link(
                link, actor=request.user, meta=services.RequestMeta.from_request(request),
                **serializer.validated_data,
            )
        except CatalogError as exc:
            return _invalid(exc.errors)
        except services.SecureLinkError as exc:
            return _service_error(exc)
        link = _link(pk)
    return Response({
        **SecureLinkSerializer(link).data,
        'events': SecureLinkEventSerializer(link.events.select_related('actor')[:100], many=True).data,
    })


@admin_api(['POST'])
def link_content(request, pk):
    link = _link(pk)
    try:
        content = services.panel_content(link, actor=request.user, meta=services.RequestMeta.from_request(request))
    except services.SecureLinkError as exc:
        return _service_error(exc)
    return private(Response(content))


@admin_api(['POST'])
def link_url(request, pk):
    try:
        url = services.link_url(_link(pk))
    except services.SecureLinkError as exc:
        return _service_error(exc)
    return private(Response({'url': url}))


@admin_api(['POST'])
def link_reactivate(request, pk):
    serializer, valid = _validated(ReactivateSerializer, request.data)
    if not valid:
        return _invalid(serializer.errors)
    try:
        link, url = services.reactivate(
            _link(pk), actor=request.user, meta=services.RequestMeta.from_request(request),
            **serializer.validated_data,
        )
    except services.SecureLinkError as exc:
        return _service_error(exc)
    return private(Response({**SecureLinkSerializer(link).data, 'url': url}))


@admin_api(['POST'])
def link_revoke(request, pk):
    link = services.revoke(_link(pk), actor=request.user, meta=services.RequestMeta.from_request(request))
    return Response(SecureLinkSerializer(link).data)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def public_types(request):
    return Response({'types': catalog_payload()})


@public_api(['POST'], SecureLinkCreateThrottle)
def public_create(request):
    serializer, valid = _validated(PublicCreateSerializer, request.data)
    if not valid:
        return _invalid(serializer.errors)
    data = serializer.validated_data
    if data.get('website'):
        # Pretend success without storing anything: bots get no signal.
        return private(Response({'accepted': True}, status=201))
    try:
        verify_captcha(data.get('recaptcha_token', ''))
    except CaptchaError as exc:
        return error_response(exc.message, code=exc.code, status=exc.status)
    title = (data.get('title') or '').strip() or f'Enviado por {data["creator_name"].strip()}'
    try:
        link, url = services.create_link(
            secret_type=data['secret_type'], title=title, fields=data['fields'],
            origin=SecureLink.Origin.PUBLIC, language=data['language'],
            validity_days=data.get('validity_days'), creator_name=data['creator_name'],
            creator_email=data.get('creator_email', ''), meta=services.RequestMeta.from_request(request),
        )
    except CatalogError as exc:
        return _invalid(exc.errors)
    except services.SecureLinkError as exc:
        return _service_error(exc)
    notify_team_secure_link_received(link.pk)
    return private(Response({'accepted': True, 'url': url, 'expires_at': link.expires_at}, status=201))


@public_api(['POST'], SecureLinkAccessThrottle)
def public_status(request):
    serializer, valid = _validated(TokenSerializer, request.data)
    if not valid:
        return _invalid(serializer.errors)
    try:
        payload = services.public_status(serializer.validated_data['token'], staff=_session_staff(request) is not None)
    except services.SecureLinkError as exc:
        return _service_error(exc)
    return private(Response(payload))


@public_api(['POST'], SecureLinkAccessThrottle)
def public_reveal(request):
    serializer, valid = _validated(TokenSerializer, request.data)
    if not valid:
        return _invalid(serializer.errors)
    staff = _session_staff(request)
    try:
        _link_row, content = services.reveal(
            serializer.validated_data['token'], staff=staff is not None, actor=staff,
            meta=services.RequestMeta.from_request(request),
        )
    except services.SecureLinkError as exc:
        return _service_error(exc)
    return private(Response(content))
