"""Presentation-only examples: project overrides never rewrite calculator agreements."""
import json
from pathlib import Path

from django.db import transaction
from django.contrib.auth import get_user_model
from accounts.models_requirement_packages import PackageExampleRevision, PackageOperation
from accounts.services.delivery_access import DeliveryConflict, project_for_actor, require_admin

OUTCOMES = ('XS', 'S', 'M', 'L', 'XL', 'PROJECT')
ENGLISH = {
    'XS': ['Change a label or a basic validation on an existing screen.'],
    'S': ['Add a simple modal using the existing form and API.'],
    'M': ['Add server-side filters to an existing list, or show an existing audit history.'],
    'L': ['Build a complete calendar or a reusable audit trail with its own API and interface.'],
    'XL': ['Build a complex integration with a clearly defined outcome and acceptance criteria.'],
    'PROJECT': ['Build a new product combining independent capabilities, such as payments, inventory and delivery.'],
}
ENGLISH_DEFINITIONS = {
    'XS': 'A focused adjustment to an existing capability.',
    'S': 'A small extension to an existing screen or capability.',
    'M': 'A bounded capability involving business logic or several existing components.',
    'L': 'A complete, self-contained new capability with its own server and interface work.',
    'XL': 'A complex, bounded capability with one outcome and verifiable acceptance criteria.',
    'PROJECT': 'Several independent capabilities requiring their own agreed scope.',
}


def latest(project_id, language):
    return PackageExampleRevision.objects.filter(project_id=project_id, language=language).first()


def example_catalog(project_id=None, *, language='es'):
    config_path = Path(__file__).resolve().parents[2] / 'content/data/requirement_calculator.json'
    # The stored general definition is authoritative; only its public fields are projected.
    from content.models import RequirementCalculator
    calculator = RequirementCalculator.objects.select_related('current_revision').first()
    config = calculator.current_revision.definition if calculator else json.loads(config_path.read_text())
    definitions = ({row['id']: row['definition'] for row in config['sizes']}
                   if language == 'es' else ENGLISH_DEFINITIONS.copy())
    definitions.setdefault('PROJECT', 'Varias capacidades independientes que requieren un alcance propio acordado.')
    generic = ({row['id']: row['examples'] for row in config['sizes']} if language == 'es' else ENGLISH.copy())
    generic.setdefault('PROJECT', ['Crear un producto que combina capacidades independientes y requiere su propio alcance.'])
    general = latest(None, language)
    if general:
        generic.update(general.examples)
    project = latest(project_id, language) if project_id is not None else None
    custom = project.examples if project else {}
    return {'language': language, 'generic_revision': general.pk if general else 0,
            'project_revision': project.pk if project else 0,
            'custom_examples': custom, 'generic_examples': generic,
            'sizes': [{'size': size, 'definition': definitions[size], 'examples': custom.get(size, generic[size]),
                       'source': 'project' if size in custom else 'generic'} for size in OUTCOMES]}


def publish_examples(actor, data, *, project_id=None, language='es'):
    require_admin(actor)
    with transaction.atomic():
        if project_id is not None:
            project_for_actor(project_id, actor, lock=True)
        else:
            # One stable catalog lock also covers the first publication.
            from content.models import HourPackageSettings
            settings = HourPackageSettings.load()
            HourPackageSettings.objects.select_for_update().get(pk=settings.pk)
        get_user_model().objects.select_for_update().get(pk=actor.pk)
        from content.services.requirement_calculator import digest
        fingerprint = digest({'action': 'examples', 'project_id': project_id, 'language': language,
                              'data': {key: str(value) if key == 'request_id' else value for key, value in data.items()}})
        operation = PackageOperation.objects.filter(actor=actor, request_id=data['request_id']).first()
        if operation:
            if operation.fingerprint != fingerprint:
                raise DeliveryConflict('El identificador corresponde a otra operación.')
            return operation.receipt
        previous = latest(project_id, language)
        if data['expected_revision'] != (previous.pk if previous else 0):
            raise DeliveryConflict('Los ejemplos cambiaron; consulta la revisión vigente.')
        PackageExampleRevision.objects.create(project_id=project_id, language=language,
            examples=data['examples'], author=actor, note=data['note'])
        result = example_catalog(project_id, language=language)
        PackageOperation.objects.create(project_id=project_id, actor=actor, request_id=data['request_id'],
                                        fingerprint=fingerprint, receipt=result)
        return result
