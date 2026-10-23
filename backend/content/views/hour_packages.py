from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.db import transaction
from django.shortcuts import get_object_or_404

from content.models import (
    BASE_RATE_FIELD_BY_NATIONALITY,
    HourPackage,
    HourPackageSettings,
    Nationality,
)
from content.serializers.hour_packages import (
    HourPackageAdminListSerializer,
    HourPackageAdminDetailSerializer,
    HourPackageCreateUpdateSerializer,
    HourPackageSettingsSerializer,
)
from content.services.frontend_build import schedule_rebuild_after_publish
from content.services.hour_package_service import (
    apply_base_rates_to_catalog,
    restore_default_packages,
)


# ---------------------------------------------------------------------------
# Admin endpoints (staff only) — hour-package catalog per nationality
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAdminUser])
def list_admin_hour_packages(request):
    """List hour packages, optionally filtered by ?nationality=COL|EXT|USA."""
    qs = HourPackage.objects.filter(pricing_model='requirements')
    nationality = request.query_params.get('nationality')
    if nationality:
        if nationality not in Nationality.values:
            return Response(
                {'nationality': ['Nacionalidad inválida. Usa COL, EXT o USA.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        qs = qs.filter(nationality=nationality)
    serializer = HourPackageAdminListSerializer(qs, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_hour_package(request):
    """Create a new hour package."""
    serializer = HourPackageCreateUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    package = serializer.save()
    detail = HourPackageAdminDetailSerializer(package)
    return Response(detail.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def retrieve_admin_hour_package(request, package_id):
    """Retrieve full hour package detail for admin editing."""
    package = get_object_or_404(HourPackage, pk=package_id)
    serializer = HourPackageAdminDetailSerializer(package)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def update_hour_package(request, package_id):
    """Update an hour package's fields."""
    package = get_object_or_404(HourPackage, pk=package_id)
    serializer = HourPackageCreateUpdateSerializer(
        package, data=request.data, partial=True
    )
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    serializer.save()
    detail = HourPackageAdminDetailSerializer(package)
    return Response(detail.data, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([IsAdminUser])
def delete_hour_package(request, package_id):
    """Delete an hour package."""
    package = get_object_or_404(HourPackage, pk=package_id, pricing_model='requirements')
    package.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_hour_package_settings(request):
    """Return the hour-packages panel settings singleton."""
    serializer = HourPackageSettingsSerializer(HourPackageSettings.load())
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def update_hour_package_settings(request):
    """Update the settings singleton, propagating changed base rates.

    A base rate present in the payload and different from the stored value
    is applied to every package of that nationality. The response includes
    ``updated_packages`` (nationality → rows updated; empty when no rate
    changed).
    """
    settings_obj = HourPackageSettings.load()
    old_rates = {
        nationality: getattr(settings_obj, field)
        for nationality, field in BASE_RATE_FIELD_BY_NATIONALITY.items()
    }
    serializer = HourPackageSettingsSerializer(
        settings_obj, data=request.data, partial=True
    )
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    changed_rates = {
        nationality: serializer.validated_data[field]
        for nationality, field in BASE_RATE_FIELD_BY_NATIONALITY.items()
        if field in serializer.validated_data
        and serializer.validated_data[field] != old_rates[nationality]
    }
    with transaction.atomic():
        serializer.save()
        updated_packages = apply_base_rates_to_catalog(changed_rates)
        if any(key.startswith('alliance_') for key in serializer.validated_data):
            schedule_rebuild_after_publish(reason='partnership-program')
    return Response(
        {**serializer.data, 'updated_packages': updated_packages},
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([IsAdminUser])
def restore_default_hour_packages(request):
    """Replace one nationality's catalog with the canonical defaults."""
    nationality = request.data.get('nationality')
    if nationality not in Nationality.values:
        return Response(
            {'nationality': ['Nacionalidad inválida. Usa COL, EXT o USA.']},
            status=status.HTTP_400_BAD_REQUEST,
        )
    from content.services.requirement_package_service import price_context

    price_context(nationality)
    with transaction.atomic():
        restore_default_packages(nationality)
        qs = HourPackage.objects.filter(nationality=nationality, pricing_model='requirements')
        data = HourPackageAdminListSerializer(qs, many=True).data
    return Response(data, status=status.HTTP_200_OK)
