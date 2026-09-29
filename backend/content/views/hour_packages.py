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
from content.services.financing_program_service import (
    INCLUDED_PACKAGE_NATIONALITY,
    is_included_package,
)
from content.services.frontend_build import schedule_rebuild_after_publish
from content.services.hour_package_service import (
    apply_base_rates_to_catalog,
    restore_default_packages,
)


def _request_program_rebuild(*packages):
    """Request a regeneration when a change touches the public program's package.

    The prerendered Partnership Program names its included monthly package
    (see financing_program_service), so only a package that matched it before
    or after the change can alter that page. ``packages`` are
    ``(nationality, hours)`` pairs.
    """
    if any(is_included_package(nationality, hours) for nationality, hours in packages):
        schedule_rebuild_after_publish(reason='partnership-program')


# ---------------------------------------------------------------------------
# Admin endpoints (staff only) — hour-package catalog per nationality
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAdminUser])
def list_admin_hour_packages(request):
    """List hour packages, optionally filtered by ?nationality=COL|EXT|USA."""
    qs = HourPackage.objects.all()
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
    _request_program_rebuild((package.nationality, package.hours))
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
    before = (package.nationality, package.hours)
    serializer = HourPackageCreateUpdateSerializer(
        package, data=request.data, partial=True
    )
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    serializer.save()
    _request_program_rebuild(before, (package.nationality, package.hours))
    detail = HourPackageAdminDetailSerializer(package)
    return Response(detail.data, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([IsAdminUser])
def delete_hour_package(request, package_id):
    """Delete an hour package."""
    package = get_object_or_404(HourPackage, pk=package_id)
    removed = (package.nationality, package.hours)
    package.delete()
    _request_program_rebuild(removed)
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
    restore_default_packages(nationality)
    if nationality == INCLUDED_PACKAGE_NATIONALITY:
        schedule_rebuild_after_publish(reason='partnership-program')
    qs = HourPackage.objects.filter(nationality=nationality)
    serializer = HourPackageAdminListSerializer(qs, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)
