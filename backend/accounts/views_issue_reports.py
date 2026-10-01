"""Thin ticket adapters; existing Platform URLs continue to use JWT/session defaults."""
from django.http import FileResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import ProjectContract
from accounts.serializers_issue_reports import IssueContextOptionsFields
from accounts.services import issue_reports as issues
from accounts.services.delivery_access import fail, is_admin, project_for_actor
from accounts.services.delivery_workflow import overview
from accounts.services.issue_context import capture_context
from accounts.services.issue_evidence import allowed_documents, attachment_for_actor


def ticket_response(ticket, kind, request, *, status=200, detail=True):
    from accounts.serializers import (
        BugReportDetailSerializer, BugReportListSerializer,
        ChangeRequestDetailSerializer, ChangeRequestListSerializer,
    )
    serializer = {
        ('bug', True): BugReportDetailSerializer, ('bug', False): BugReportListSerializer,
        ('change', True): ChangeRequestDetailSerializer, ('change', False): ChangeRequestListSerializer,
    }[(kind, detail)]
    return Response(serializer(ticket, context={'request': request}).data, status=status)


def create_handler(request, project_id, kind):
    ticket = issues.create_ticket(project_id, request.user, kind, request.data)
    return ticket_response(ticket, kind, request, status=201, detail=False)


def evaluate_handler(request, project_id, kind, ticket_id):
    ticket = issues.evaluate_ticket(project_id, request.user, kind, ticket_id, request.data)
    return ticket_response(ticket, kind, request)


def comment_handler(request, project_id, kind, ticket_id, *, reopen=False):
    from accounts.serializers import BugCommentSerializer, ChangeRequestCommentSerializer
    data = {**request.data, 'reopen': True} if reopen else request.data
    comment = issues.comment_ticket(project_id, request.user, kind, ticket_id, data)
    serializer = BugCommentSerializer if kind == 'bug' else ChangeRequestCommentSerializer
    return Response(serializer(comment).data, status=201)


def archive_handler(request, project_id, kind, ticket_id):
    issues.archive_ticket(project_id, request.user, kind, ticket_id, request.data)
    return Response({'detail': 'Reporte de bug archivado.' if kind == 'bug' else 'Solicitud de cambio archivada.'})


def bulk_handler(request, project_id, kind):
    return Response(issues.bulk_evaluate(project_id, request.user, kind, request.data))


def convert_handler(request, project_id, ticket_id):
    ticket = issues.convert_request(project_id, request.user, ticket_id, request.data)
    return ticket_response(ticket, 'change', request, status=201)


def context_options(project_id, actor, *, kind=None, ticket_id=None, contract_id=None,
                    source_requirement_id=None, source_publication_id=None):
    options = IssueContextOptionsFields(data={key: value for key, value in {
        'kind': kind, 'ticket_id': ticket_id, 'contract_id': contract_id,
        'source_requirement_id': source_requirement_id, 'source_publication_id': source_publication_id,
    }.items() if value is not None})
    options.is_valid(raise_exception=True)
    project = project_for_actor(project_id, actor)
    ticket = issues.get_ticket(project_id, actor, kind, ticket_id) if ticket_id else None
    # An admin reporting on a delivery sees the same published guides as the client.
    delivery = overview(project_id, project.client)
    from accounts.models import DeliveryPublication
    rounds = dict(DeliveryPublication.objects.filter(
        stage__phase__scope__contract__project=project,
    ).values_list('pk', 'round'))
    requirements = []
    for scope in delivery['scopes']:
        for phase in scope['phases']:
            for stage in phase['stages']:
                for requirement in stage['requirements']:
                    requirements.append({
                        **requirement, 'source_publication_id': stage['publication_id'],
                        'source_requirement_version': requirement['version'],
                        'publication_round': rounds.get(stage['publication_id']),
                        'contract_id': scope['contract_id'], 'amendment_id': scope.get('amendment_id'),
                        'scope_id': scope['id'], 'scope_title': scope['title'],
                        'phase_id': phase['id'], 'phase_title': phase['title'],
                        'stage_id': stage['id'], 'stage_title': stage['title'],
                    })
    if source_publication_id:
        publication, captured = capture_context(project, actor, {
            'source_requirement_id': source_requirement_id, 'source_publication_id': source_publication_id,
        })
        original = {**captured['requirement'], **{key: captured[key] for key in (
            'contract_id', 'contract_title', 'amendment_id', 'scope_id', 'scope_title',
            'phase_id', 'phase_title', 'stage_id', 'stage_title', 'publication_round',
        )}, 'source_publication_id': publication.pk, 'source_requirement_version': captured['requirement_version']}
        requirements = [original, *[row for row in requirements if row['id'] != source_requirement_id]]
    contracts = ProjectContract.objects.filter(project=project)
    if not is_admin(actor):
        contracts = contracts.filter(client_visible=True)
    contract = contracts.filter(pk=contract_id).first() if contract_id else None
    if contract_id and not contract:
        fail('Contrato no disponible en este proyecto.', 'issue_contract_context')
    return {
        'requirements': requirements,
        'contracts': list(contracts.values('id', 'title')),
        'documents': [{'id': doc.pk, 'title': doc.title} for doc in allowed_documents(
            project, actor, ticket, public=True, contract=contract,
        )],
        'scope_review_available': False,
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def issue_context_options(request, project_id):
    serializer = IssueContextOptionsFields(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    return Response(context_options(project_id, request.user, **serializer.validated_data))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bug_reopen_view(request, project_id, bug_id):
    return comment_handler(request, project_id, 'bug', bug_id, reopen=True)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def issue_attachment_view(request, attachment_id):
    attachment = attachment_for_actor(attachment_id, request.user)
    response = FileResponse(attachment.file.open('rb'), content_type='application/pdf',
                            as_attachment=True, filename=f'issue-document-{attachment.pk}.pdf')
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
