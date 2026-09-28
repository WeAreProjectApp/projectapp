from content.services.video_resource_service import public_resource
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response

from content.models import (
    AdditionalModule,
    AdditionalModuleCategory,
    AdditionalModuleShareLink,
)
from content.serializers.additional_modules import (
    AdditionalModuleAdminSerializer,
    AdditionalModuleCategorySerializer,
    AdditionalModulePdfSelectionSerializer,
    AdditionalModuleShareAdminSerializer,
    AdditionalModuleShareCreateSerializer,
    AdditionalModuleShareVideoSerializer,
    AdditionalModuleTrackSerializer,
)
from content.services.additional_module_catalog_service import (
    ActiveCategoryModulesConflict,
    CatalogOrderError,
    CatalogRevisionConflict,
    catalog_revision,
    next_category_order,
    next_module_order,
    record_share_view,
    reorder_catalog,
    serialize_public_catalog,
    set_category_active,
)
from content.services.additional_module_pdf_service import (
    AdditionalModulePdfService,
)
from content.services.explainer_video_service import explainer_video_visible
from content.services.frontend_build import schedule_rebuild_after_publish
from content.throttles import TrackingAnonThrottle
from content.utils import get_client_ip, is_staff_session


def _schedule_catalog_rebuild():
    schedule_rebuild_after_publish()


def _gone(detail):
    return Response(
        {'detail': detail, 'code': 'catalog_link_unavailable'},
        status=status.HTTP_410_GONE,
    )


def _pdf_response(pdf_bytes, language):
    filename = (
        'additional-modules-catalog.pdf'
        if language == 'en'
        else 'catalogo-modulos-adicionales.pdf'
    )
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['Cache-Control'] = 'private, no-store'
    return response


def _language_from_query(request, *, default='es'):
    language = request.query_params.get('lang', default)
    return language if language in ('es', 'en') else None


def _invalid_language_response():
    return Response(
        {'lang': ['Usa es o en.']},
        status=status.HTTP_400_BAD_REQUEST,
    )


def _active_share_or_response(share_uuid):
    share_link = get_object_or_404(
        AdditionalModuleShareLink.objects.prefetch_related('selected_modules'),
        uuid=share_uuid,
    )
    if not share_link.is_active:
        return None, _gone('Este enlace fue retirado y ya no está disponible.')
    active_ids = list(
        share_link.selected_modules.filter(
            is_active=True,
            category__is_active=True,
        ).values_list('id', flat=True)
    )
    if not active_ids:
        return None, _gone('Los módulos de este enlace ya no están disponibles.')
    return (share_link, active_ids), None


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_catalog(request):
    categories = AdditionalModuleCategory.objects.annotate(
        module_count_annotated=Count('modules'),
        active_module_count_annotated=Count(
            'modules',
            filter=Q(modules__is_active=True),
        ),
    ).order_by('order', 'id')
    modules = AdditionalModule.objects.select_related('category').order_by(
        'category__order', 'order', 'id',
    )
    return Response({
        'revision': catalog_revision(),
        'categories': AdditionalModuleCategorySerializer(categories, many=True).data,
        'modules': AdditionalModuleAdminSerializer(modules, many=True).data,
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_category(request):
    serializer = AdditionalModuleCategorySerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    with transaction.atomic():
        list(AdditionalModuleCategory.objects.select_for_update().values_list('id'))
        category = serializer.save(order=next_category_order(), is_active=True)
    _schedule_catalog_rebuild()
    return Response(
        AdditionalModuleCategorySerializer(category).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def update_category(request, category_id):
    category = get_object_or_404(AdditionalModuleCategory, pk=category_id)
    data = dict(request.data)
    data.pop('is_active', None)
    serializer = AdditionalModuleCategorySerializer(
        category,
        data=data,
        partial=True,
    )
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    category = serializer.save()
    _schedule_catalog_rebuild()
    return Response(AdditionalModuleCategorySerializer(category).data)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def set_category_status(request, category_id, action):
    category = get_object_or_404(AdditionalModuleCategory, pk=category_id)
    if action not in ('retire', 'restore'):
        return Response(status=status.HTTP_404_NOT_FOUND)
    try:
        set_category_active(category, action == 'restore')
    except ActiveCategoryModulesConflict as exc:
        return Response(
            {
                'detail': (
                    'Retira o mueve los módulos activos antes de retirar la categoría.'
                ),
                'active_module_count': exc.count,
            },
            status=status.HTTP_409_CONFLICT,
        )
    _schedule_catalog_rebuild()
    return Response(AdditionalModuleCategorySerializer(category).data)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_module(request):
    serializer = AdditionalModuleAdminSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    category = serializer.validated_data['category']
    with transaction.atomic():
        list(category.modules.select_for_update().values_list('id'))
        module = serializer.save(
            order=next_module_order(category),
            is_active=True,
        )
    _schedule_catalog_rebuild()
    return Response(
        AdditionalModuleAdminSerializer(module).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def update_module(request, module_id):
    module = get_object_or_404(
        AdditionalModule.objects.select_related('category'),
        pk=module_id,
    )
    data = dict(request.data)
    data.pop('is_active', None)
    serializer = AdditionalModuleAdminSerializer(
        module,
        data=data,
        partial=True,
    )
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    new_category = serializer.validated_data.get('category', module.category)
    with transaction.atomic():
        AdditionalModule.objects.select_for_update().filter(pk=module.pk).get()
        order = (
            next_module_order(new_category)
            if new_category.pk != module.category_id
            else module.order
        )
        module = serializer.save(order=order)
    _schedule_catalog_rebuild()
    return Response(AdditionalModuleAdminSerializer(module).data)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def set_module_status(request, module_id, action):
    module = get_object_or_404(AdditionalModule, pk=module_id)
    if action not in ('retire', 'restore'):
        return Response(status=status.HTTP_404_NOT_FOUND)
    if action == 'restore' and not module.category.is_active:
        return Response(
            {'detail': 'Restaura primero la categoría del módulo.'},
            status=status.HTTP_409_CONFLICT,
        )
    module.is_active = action == 'restore'
    module.save(update_fields=['is_active', 'updated_at'])
    _schedule_catalog_rebuild()
    return Response(AdditionalModuleAdminSerializer(module).data)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def reorder_admin_catalog(request):
    try:
        revision = reorder_catalog(
            expected_revision=request.data.get('revision', ''),
            category_ids=request.data.get('category_ids'),
            module_groups=request.data.get('module_groups'),
        )
    except CatalogRevisionConflict as exc:
        return Response(
            {'detail': str(exc), 'code': 'stale_catalog_revision'},
            status=status.HTTP_409_CONFLICT,
        )
    except CatalogOrderError as exc:
        return Response(
            {'detail': str(exc), 'code': 'invalid_catalog_order'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    _schedule_catalog_rebuild()
    return Response({'revision': revision})


@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def admin_share_links(request):
    if request.method == 'GET':
        links = AdditionalModuleShareLink.objects.select_related(
            'client', 'client__user',
        ).prefetch_related('selected_modules', 'selected_modules__category')
        return Response(AdditionalModuleShareAdminSerializer(links, many=True).data)

    serializer = AdditionalModuleShareCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    share_link = serializer.save(created_by=request.user)
    share_link = AdditionalModuleShareLink.objects.select_related(
        'client', 'client__user',
    ).prefetch_related('selected_modules', 'selected_modules__category').get(
        pk=share_link.pk,
    )
    return Response(
        AdditionalModuleShareAdminSerializer(share_link).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(['POST'])
@permission_classes([IsAdminUser])
def set_share_link_status(request, share_uuid, action):
    share_link = get_object_or_404(AdditionalModuleShareLink, uuid=share_uuid)
    if action not in ('revoke', 'restore'):
        return Response(status=status.HTTP_404_NOT_FOUND)
    restoring = action == 'restore'
    share_link.is_active = restoring
    share_link.revoked_at = None if restoring else timezone.now()
    share_link.save(update_fields=['is_active', 'revoked_at'])
    share_link = AdditionalModuleShareLink.objects.select_related(
        'client', 'client__user',
    ).prefetch_related('selected_modules', 'selected_modules__category').get(
        pk=share_link.pk,
    )
    return Response(AdditionalModuleShareAdminSerializer(share_link).data)


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def update_share_link(request, share_uuid):
    """Show or hide the explainer video on one link; selection stays immutable."""
    share_link = get_object_or_404(AdditionalModuleShareLink, uuid=share_uuid)
    serializer = AdditionalModuleShareVideoSerializer(share_link, data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    serializer.save()
    share_link = AdditionalModuleShareLink.objects.select_related(
        'client', 'client__user',
    ).prefetch_related('selected_modules', 'selected_modules__category').get(
        pk=share_link.pk,
    )
    return Response(AdditionalModuleShareAdminSerializer(share_link).data)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_catalog_pdf(request):
    serializer = AdditionalModulePdfSelectionSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    language = serializer.validated_data['language']
    module_ids = [module.id for module in serializer.validated_data['modules']]
    pdf_bytes = AdditionalModulePdfService.build(
        language=language,
        module_ids=module_ids,
        recipient_label=serializer.validated_data['recipient_label'],
    )
    return _pdf_response(pdf_bytes, language)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def public_catalog(request):
    language = _language_from_query(request)
    if language is None:
        return _invalid_language_response()
    payload = serialize_public_catalog(language=language)
    payload.update({
        'is_shared': False,
        'explainer_video': public_resource('additional-modules', language),
        'show_explainer_video': explainer_video_visible('additional-modules'),
        'canonical_path': (
            '/en-us/additional-modules'
            if language == 'en'
            else '/es-co/additional-modules'
        ),
    })
    return Response(payload)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def public_catalog_pdf(request):
    language = _language_from_query(request)
    if language is None:
        return _invalid_language_response()
    try:
        pdf_bytes = AdditionalModulePdfService.build(language=language)
    except ValueError as exc:
        return _gone(str(exc))
    return _pdf_response(pdf_bytes, language)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def public_share_catalog(request, share_uuid):
    resolved, unavailable = _active_share_or_response(share_uuid)
    if unavailable:
        return unavailable
    share_link, module_ids = resolved
    language = _language_from_query(request, default=share_link.language)
    if language is None:
        return _invalid_language_response()
    payload = serialize_public_catalog(
        language=language,
        module_ids=module_ids,
    )
    payload.update({
        'is_shared': True,
        'explainer_video': public_resource('additional-modules', language),
        'share_uuid': str(share_link.uuid),
        'show_explainer_video': explainer_video_visible(
            'additional-modules', share_link=share_link,
        ),
        'canonical_path': (
            '/en-us/additional-modules'
            if language == 'en'
            else '/es-co/additional-modules'
        ),
    })
    return Response(payload)


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([TrackingAnonThrottle])
def track_public_share_catalog(request, share_uuid):
    resolved, unavailable = _active_share_or_response(share_uuid)
    if unavailable:
        return unavailable
    share_link, _module_ids = resolved

    if is_staff_session(request):
        return Response({'status': 'skipped'})

    serializer = AdditionalModuleTrackSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    _event, created = record_share_view(
        share_link=share_link,
        session_id=serializer.validated_data['session_id'],
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
    )
    return Response({'status': 'recorded' if created else 'existing'})


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def public_share_catalog_pdf(request, share_uuid):
    resolved, unavailable = _active_share_or_response(share_uuid)
    if unavailable:
        return unavailable
    share_link, module_ids = resolved
    language = _language_from_query(request, default=share_link.language)
    if language is None:
        return _invalid_language_response()
    pdf_bytes = AdditionalModulePdfService.build(
        language=language,
        module_ids=module_ids,
        recipient_label=share_link.recipient_label,
    )
    return _pdf_response(pdf_bytes, language)
