"""Session-admin adapters for existing project and commercial phase services."""
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from accounts.models import Project, ProjectPhase
from accounts.serializers import ProjectPhaseSerializer, UpdateProjectPhaseSerializer
from accounts.serializers_delivery import StrictSerializer
from accounts.services.project_phases import PhaseError, add_phase, list_phases, remove_phase, reorder_phases
from content.models import BusinessProposal


class AddCommercialPhaseSerializer(StrictSerializer):
    proposal_id = serializers.IntegerField(min_value=1)
    order = serializers.IntegerField(min_value=1, required=False)


class ReorderCommercialPhasesSerializer(StrictSerializer):
    class Item(StrictSerializer):
        id = serializers.IntegerField(min_value=1)
        order = serializers.IntegerField(min_value=1)

    items = Item(many=True)

    def validate_items(self, value):
        ids = [row['id'] for row in value]
        orders = [row['order'] for row in value]
        if len(set(ids)) != len(ids) or sorted(orders) != list(range(1, len(value) + 1)):
            raise serializers.ValidationError('Selecciona cada fase una vez con posiciones consecutivas.')
        return value


def _phase_error(exc):
    return Response({'detail': exc.code, **exc.extra}, status=exc.http_status)


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def project_detail(request, project_id):
    from content.views.panel_projects import _annotated_queryset
    from content.serializers.panel_projects import PanelProjectSerializer
    project = get_object_or_404(_annotated_queryset(), pk=project_id)
    result = PanelProjectSerializer(project).data
    result.update({key: getattr(project, key) for key in (
        'progress', 'start_date', 'estimated_end_date', 'payment_milestones', 'hosting_tiers', 'hosting_start_date',
    )})
    return Response(result)


@api_view(['GET', 'POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def project_commercial_phases(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    if request.method == 'GET':
        return Response(ProjectPhaseSerializer(list_phases(project), many=True).data)
    serializer = AddCommercialPhaseSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        project = Project.objects.select_for_update().get(pk=project_id)
        proposal = get_object_or_404(BusinessProposal.objects.select_for_update().select_related('client', 'deliverable'), pk=serializer.validated_data['proposal_id'])
        try:
            phase = add_phase(project, proposal, order=serializer.validated_data.get('order'))
        except PhaseError as exc:
            return _phase_error(exc)
    return Response(ProjectPhaseSerializer(phase).data, status=201)


@api_view(['PATCH', 'DELETE'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def project_commercial_phase_detail(request, project_id, phase_id):
    with transaction.atomic():
        project = get_object_or_404(Project.objects.select_for_update(), pk=project_id)
        phase = get_object_or_404(ProjectPhase.objects.select_for_update(), pk=phase_id, project=project)
        if request.method == 'DELETE':
            try:
                remove_phase(project, phase_id)
            except PhaseError as exc:
                return _phase_error(exc)
            return Response(status=204)
        unknown = set(request.data) - {'hosting_start_date'}
        if unknown:
            raise ValidationError({key: 'Campo no editable.' for key in unknown})
        serializer = UpdateProjectPhaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phase.hosting_start_date = serializer.validated_data['hosting_start_date']
        phase.save(update_fields=['hosting_start_date'])
        if phase.order == 1:
            project.hosting_start_date = phase.hosting_start_date
            project.save(update_fields=['hosting_start_date'])
    return Response(ProjectPhaseSerializer(phase).data)


@api_view(['PATCH'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def project_commercial_phases_reorder(request, project_id):
    serializer = ReorderCommercialPhasesSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        project = get_object_or_404(Project.objects.select_for_update(), pk=project_id)
        try:
            reorder_phases(project, serializer.validated_data['items'])
        except PhaseError as exc:
            return _phase_error(exc)
    return Response(ProjectPhaseSerializer(list_phases(project), many=True).data)
