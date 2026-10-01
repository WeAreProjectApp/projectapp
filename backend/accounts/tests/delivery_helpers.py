"""Real-domain builders for focused delivery tests."""
from datetime import datetime, timezone
from types import SimpleNamespace
from django.contrib.auth.models import User
from accounts.models import DeliveryPhase, DeliveryScope, DeliveryStage, DeliveryWorkspace, Project, ProjectContract, Requirement, UserProfile
from accounts.services import delivery_workflow as delivery
from content.models import Document

GUIDE = {'role': 'Cliente', 'environment': 'Staging', 'preparation': 'Entrar con tu cuenta',
         'data': 'Un registro de prueba', 'steps': ['Abrir la pantalla', 'Guardar el registro'],
         'expected_result': 'El registro aparece en la lista', 'failure_signals': 'No aparece el registro'}
RECORDED_AT = datetime(2026, 9, 30, 12, tzinfo=timezone.utc)


def build_delivery_context():
    admin = User.objects.create_user('delivery-admin', 'admin@example.test', 'test-password')
    UserProfile.objects.create(user=admin, role='admin', is_onboarded=True, email_verified=True)
    client = User.objects.create_user('delivery-client', 'client@example.test', 'test-password', first_name='Cliente')
    UserProfile.objects.create(user=client, role='client', is_onboarded=True, email_verified=True)
    project = Project.objects.create(name='Proyecto de validación', client=client)
    doc = Document.objects.create(title='Contrato firmado', project=project, client_user=client, requires_signature=True,
                                  signed_by=client, signed_at=RECORDED_AT, signature_name='Cliente', is_client_visible=True,
                                  content_markdown='# Contrato\nAlcance acordado.',
                                  include_portada=False, include_subportada=False, include_contraportada=False)
    contract = ProjectContract.objects.create(project=project, key='contrato', title='Contrato original', document=doc, client_visible=True)
    scope = DeliveryScope.objects.create(contract=contract, key='alcance', title='Alcance')
    phase = DeliveryPhase.objects.create(scope=scope, key='fase', title='Fase')
    stage = DeliveryStage.objects.create(phase=phase, key='etapa', title='Etapa')
    first = Requirement.objects.create(stage=stage, key='uno', title='Guardar registro', guide=GUIDE)
    second = Requirement.objects.create(stage=stage, key='dos', title='Editar registro', guide=GUIDE, order=1)
    return SimpleNamespace(admin=admin, client=client, project=project, document=doc,
                           contract=contract, scope=scope, phase=phase, stage=stage, first=first, second=second)


def version(context):
    return DeliveryWorkspace.objects.filter(project=context.project).values_list('version', flat=True).first() or 0


def prepare_prompt(context, **overrides):
    from accounts.services.delivery_authoring import create_prompt_context
    values = {'expected_version': version(context), 'request_id': 'prepare-guides',
              'mode': 'guides', 'contract_id': context.contract.pk}
    values.update(overrides)
    return create_prompt_context(context.project.pk, context.admin, values)


def publish(context, request_id='publish-1'):
    return delivery.publish_stage(context.project.pk, context.admin, context.stage.pk,
                                  {'expected_version': version(context), 'request_id': request_id})


def decisions(context, *pairs, request_id='review-1'):
    return {'expected_version': version(context), 'request_id': request_id,
            'decisions': [{'requirement_id': req.pk, 'version': req.version, 'decision': decision,
                           'message': 'El registro no se guarda' if decision != 'approved' else '',
                           'environment': 'Staging'} for req, decision in pairs]}


def stage_data(response):
    return response['scopes'][0]['phases'][0]['stages'][0]
