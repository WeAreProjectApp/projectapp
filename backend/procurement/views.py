import json

from django.http import HttpResponse
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from procurement.models import Alert, Delivery, SavedSearch, Settings
from procurement.serializers import AlertSerializer, DeliverySerializer, DeliverySummarySerializer, SavedSearchSerializer, SettingsSerializer, SyncRunSerializer
from procurement.services import records


def admin_api(methods):
    def decorate(view):
        return api_view(methods)(authentication_classes([SessionAuthentication])(permission_classes([IsAdminUser])(view)))
    return decorate


def query(request):
    result = request.query_params.dict()
    try:
        result['filters'] = json.loads(result.get('filters', '{}'))
    except (ValueError, TypeError) as exc:
        raise ValidationError({'filters': 'Filtros JSON inválidos.'}) from exc
    return result


@admin_api(['GET'])
def opportunities(request):
    return Response(records.list_opportunities(query(request), request.user))


@admin_api(['GET'])
def opportunity_detail(request, pk):
    return Response(records.detail(pk))


@admin_api(['POST'])
def classify(request, pk):
    return Response(records.classify(pk, request.data, request.user, request.user))


@admin_api(['POST'])
def restore(request, pk):
    return Response(records.classify(pk, {}, request.user, request.user, restore=True))


@admin_api(['GET', 'POST'])
def searches(request):
    if request.method == 'POST':
        return Response(records.save_search(request.data, request.user), status=201)
    return Response(SavedSearchSerializer(SavedSearch.objects.filter(owner=request.user), many=True).data)


@admin_api(['PATCH', 'DELETE'])
def search_detail(request, pk):
    if request.method == 'PATCH':
        return Response(records.save_search(request.data, request.user, pk))
    records.found(SavedSearch, pk, owner=request.user).delete()
    return Response(status=204)


@admin_api(['GET', 'POST'])
def alerts(request):
    if request.method == 'POST':
        return Response(records.save_alert(request.data, request.user), status=201)
    return Response(AlertSerializer(Alert.objects.all()[:500], many=True).data)


@admin_api(['PATCH'])
def alert_detail(request, pk):
    return Response(records.save_alert(request.data, request.user, pk))


@admin_api(['GET', 'PATCH'])
def settings(request):
    return Response(records.save_settings(request.data) if request.method == 'PATCH' else SettingsSerializer(Settings.current()).data)


@admin_api(['GET'])
def catalog(request):
    return Response(records.filter_catalog())


@admin_api(['GET', 'POST'])
def sync(request):
    if request.method == 'POST':
        from procurement.services.sync import request_sync
        return Response(SyncRunSerializer(request_sync(request.user)).data, status=202)
    return Response(records.sync_status())


@admin_api(['GET'])
def deliveries(request):
    from procurement.filters import StrictSerializer
    from rest_framework import serializers
    class Options(StrictSerializer):
        page = serializers.IntegerField(min_value=1, default=1)
    options = records.validated(Options, request.query_params)
    return Response(records.page(Delivery.objects.defer('snapshot'), DeliverySummarySerializer, options['page']))


@admin_api(['GET'])
def delivery_detail(request, pk):
    return Response(DeliverySerializer(records.found(Delivery, pk)).data)


@admin_api(['POST'])
def retry(request, pk):
    from procurement.services.notifications import retry_delivery
    return Response(retry_delivery(pk), status=202)


@admin_api(['GET'])
def export(request):
    data = records.export_opportunities(query(request), request.user)
    response = HttpResponse(data, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="oportunidades-secop.xlsx"'
    return response
