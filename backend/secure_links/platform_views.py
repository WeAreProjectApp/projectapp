"""JWT-only client endpoints. Error responses also forbid HTTP caching."""

from functools import wraps

from django.core.paginator import Paginator
from django.db.models import Count
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from accounts.authentication import SessionJWTAuthentication

from . import platform_services
from .catalog import CatalogError, catalog_payload
from .platform_access import IsActiveSecureLinkClient, owned_link, owned_links, owned_project
from .platform_serializers import CreateInput, EmptyInput, EventMetadata, LinkMetadata, ListInput, ReactivateInput, TitleInput
from .platform_throttles import PlatformSecureLinkCreateThrottle, PlatformSecureLinkURLThrottle
from .services import RequestMeta, SecureLinkError

PAGE_SIZE = 25


def client_api(methods, *, throttles=()):
    def decorate(view):
        @wraps(view)
        def errors(request, *args, **kwargs):
            try:
                return view(request, *args, **kwargs)
            except SecureLinkError as exc:
                return Response({'detail': exc.message, 'code': exc.code}, status=exc.status)
            except CatalogError:
                # CatalogError can echo unknown input keys; never return it raw.
                return Response({'detail': 'Revisa los campos del tipo seleccionado.', 'code': 'invalid_content'}, status=400)

        endpoint = api_view(methods)(authentication_classes([SessionJWTAuthentication])(
            permission_classes([IsAuthenticated, IsActiveSecureLinkClient])(throttle_classes(list(throttles))(errors))))

        @wraps(endpoint)
        def private(request, *args, **kwargs):
            response = endpoint(request, *args, **kwargs)
            response['Cache-Control'] = 'no-store, max-age=0'
            response['Pragma'] = 'no-cache'
            return response
        return private
    return decorate


def _input(cls, data):
    serializer = cls(data=data)
    if not serializer.is_valid():
        # Choice/unknown values in DRF messages can themselves be secrets.
        raise SecureLinkError('Revisa los datos del formulario.', code='invalid')
    return serializer.validated_data


def _scope(request, project_id):
    return owned_project(request.user.profile.pk, project_id)


def _write_context(request, project_id, link_id):
    return {
        'owner_id': request.user.profile.pk, 'project_id': project_id, 'link_id': link_id,
        'actor': request.user, 'meta': RequestMeta.from_request(request),
    }


@client_api(['GET'])
def types(request, project_id):
    _scope(request, project_id)
    return Response({'types': catalog_payload()})


@client_api(['GET', 'POST'], throttles=[PlatformSecureLinkCreateThrottle])
def collection(request, project_id):
    owner, project = _scope(request, project_id)
    if request.method == 'POST':
        data = _input(CreateInput, request.data)
        link, url, replayed = platform_services.create_owned_link(
            owner_id=owner.pk, project_id=project.pk, actor=request.user,
            meta=RequestMeta.from_request(request), **data,
        )
        result = {'link': LinkMetadata(link).data, 'replayed': replayed}
        if url is not None:
            result['url'] = url
        return Response(result, status=200 if replayed else 201)
    data = _input(ListInput, request.query_params)
    query = owned_links(owner, project)
    if data.get('search'):
        query = query.filter(title__icontains=data['search'])
    totals = query.aggregate(all=Count('pk'), **{
        state: Count('pk', filter=condition) for state, condition in query.status_conditions().items()
    })
    if data.get('status'):
        query = query.with_status(data['status'])
    page = Paginator(query, PAGE_SIZE).get_page(data['page'])
    return Response({
        'results': LinkMetadata(page.object_list, many=True).data,
        'counts': totals, 'count': page.paginator.count, 'page': page.number, 'page_size': PAGE_SIZE,
    })


@client_api(['GET', 'PATCH'])
def detail(request, project_id, link_id):
    owner, project = _scope(request, project_id)
    link = owned_link(owner, project, link_id)
    if request.method == 'PATCH':
        link = platform_services.update_owned_title(
            **_write_context(request, project_id, link_id), **_input(TitleInput, request.data),
        )
    return Response(LinkMetadata(link).data)


@client_api(['GET'])
def events(request, project_id, link_id):
    owner, project = _scope(request, project_id)
    link = owned_link(owner, project, link_id)
    data = _input(ListInput, request.query_params)
    page = Paginator(link.events.all(), PAGE_SIZE).get_page(data['page'])
    return Response({
        'results': EventMetadata(page.object_list, many=True, context={'owner_user_id': owner.user_id}).data,
        'count': page.paginator.count, 'page': page.number, 'page_size': PAGE_SIZE,
    })


@client_api(['POST'], throttles=[PlatformSecureLinkURLThrottle])
def copy_url(request, project_id, link_id):
    _input(EmptyInput, request.data)
    url = platform_services.owned_link_url(**_write_context(request, project_id, link_id))
    return Response({'url': url})


@client_api(['POST'])
def revoke(request, project_id, link_id):
    _input(EmptyInput, request.data)
    link = platform_services.revoke_owned_link(**_write_context(request, project_id, link_id))
    return Response(LinkMetadata(link).data)


@client_api(['POST'], throttles=[PlatformSecureLinkURLThrottle])
def reactivate(request, project_id, link_id):
    data = _input(ReactivateInput, request.data)
    link, url = platform_services.reactivate_owned_link(**_write_context(request, project_id, link_id), **data)
    return Response({'link': LinkMetadata(link).data, 'url': url})
