"""Client rules (CL*).

Duplicate groups (CL1-CL3) share one finding shape that the client-merge fixer
consumes: subjects are the group's profiles ordered by pk, ``evidence`` is
``{'key': <normalized key>, 'profiles': [pks]}`` and the operator picks
``survivor`` and ``duplicate`` (two different profiles of the group). A merge
handles one pair; a group of three leaves a new group of two, a new finding.
CL4 (orphan clients) and CL5 (projects owned by a non-client) only report.
"""
from collections import defaultdict

from django.db.models import Exists, OuterRef

from content.services.data_integrity.catalog import rule
from content.services.data_integrity.hashing import digits, normalized
from content.services.data_integrity.scope import PROFILE, PROJECT, USER, client_label
from content.services.data_integrity.types import MERGE_CLIENTS, REPORT_ONLY, Finding, RecordRef

MIN_CEDULA_DIGITS = 5


def _clients():
    from accounts.models import UserProfile
    # A merge archives the losing profile without deleting its identity history.
    # Archived profiles must not recreate the duplicate group after that merge.
    return list(UserProfile._base_manager.filter(role=UserProfile.ROLE_CLIENT, archived_at__isnull=True)
                .select_related('user').order_by('pk'))


def is_placeholder(profile):
    from accounts.models import UserProfile
    return (profile.user.email or '').strip().lower().endswith(UserProfile.PLACEHOLDER_EMAIL_DOMAIN)


def merge_inputs(profiles, suggested=None):
    options = [{'value': profile.pk, 'label': f'{client_label(profile)} · {profile.user.email}'}
               for profile in profiles]
    inputs = {
        'survivor': {'label': 'el cliente que se conserva', 'options': options, 'required': True},
        'duplicate': {'label': 'el cliente duplicado que se fusiona y se archiva', 'options': options,
                      'required': True},
    }
    suggestion = {}
    if suggested is not None:
        others = [profile.pk for profile in profiles if profile.pk != suggested.pk]
        suggestion = {'survivor': suggested.pk, 'duplicate': others[0]}
    return inputs, suggestion


def _group_finding(rule_id, key, profiles, message, suggested=None):
    inputs, suggestion = merge_inputs(profiles, suggested)
    return Finding(
        rule_id=rule_id,
        subjects=tuple(RecordRef(PROFILE, profile.pk, client_label(profile)) for profile in profiles),
        evidence={'key': key, 'profiles': [profile.pk for profile in profiles]},
        message=message, inputs=inputs, suggestion=suggestion,
    )


def _suggest(profiles):
    """The non-placeholder, oldest profile: the one most likely to carry history."""
    real = [profile for profile in profiles if not is_placeholder(profile)]
    return (real or profiles)[0]


@rule(id='CL1', domain='clients', severity='high', fix_kinds=(MERGE_CLIENTS,), group=True,
      title='Clientes con el mismo correo',
      description='Dos o más clientes activos usan el mismo correo: podrían ser la misma persona registrada varias veces. '
                  'Se fusionan en uno, que conserva todo lo de los demás.')
def detect_duplicate_email(scope):
    groups = defaultdict(list)
    for profile in _clients():
        email = (profile.user.email or '').strip().lower()
        if email and not is_placeholder(profile):
            groups[email].append(profile)
    for email, profiles in sorted(groups.items()):
        if len(profiles) > 1 and scope.touches(PROFILE, [profile.pk for profile in profiles]):
            yield _group_finding('CL1', email, profiles,
                                 f'{len(profiles)} clientes comparten el correo {email}.', _suggest(profiles))


@rule(id='CL2', domain='clients', severity='medium', fix_kinds=(MERGE_CLIENTS,), group=True,
      title='Cliente provisional repetido',
      description='Un cliente activo creado sin correo (provisional) tiene el mismo nombre o empresa que otro '
                  'cliente. Suele pasar al crear o editar una propuesta sin correo; se fusiona en el real.')
def detect_placeholder_clone(scope):
    groups = defaultdict(dict)
    for profile in _clients():
        name = normalized(profile.user.get_full_name())
        company = normalized(profile.company_name)
        for field, key in (('name', name), ('company', company)):
            if key:
                groups[(field, key)][profile.pk] = profile
    seen = set()
    for (field, key), members in sorted(groups.items()):
        profiles = [members[pk] for pk in sorted(members)]
        group = tuple(profile.pk for profile in profiles)
        if len(profiles) < 2 or group in seen or not any(is_placeholder(profile) for profile in profiles):
            continue
        seen.add(group)
        if scope.touches(PROFILE, group):
            shared = 'el nombre' if field == 'name' else 'la empresa'
            yield _group_finding('CL2', key, profiles,
                                 f'{len(profiles)} clientes comparten {shared} «{key}» y al menos '
                                 'uno es provisional (sin correo real).', _suggest(profiles))


@rule(id='CL3', domain='clients', severity='high', fix_kinds=(MERGE_CLIENTS,), group=True,
      title='Clientes con la misma cédula',
      description='Dos o más clientes activos tienen el mismo documento de identidad: podrían ser la misma persona. '
                  'Se fusionan en uno.')
def detect_duplicate_cedula(scope):
    groups = defaultdict(list)
    for profile in _clients():
        number = digits(profile.cedula)
        if len(number) >= MIN_CEDULA_DIGITS:
            groups[number].append(profile)
    for number, profiles in sorted(groups.items()):
        if len(profiles) > 1 and scope.touches(PROFILE, [profile.pk for profile in profiles]):
            yield _group_finding('CL3', number, profiles,
                                 f'{len(profiles)} clientes comparten la cédula {number}.', _suggest(profiles))


@rule(id='CL4', domain='clients', severity='low', fix_kinds=(REPORT_ONLY,),
      title='Cliente sin ningún registro',
      description='Un cliente activo sin propuestas, proyectos, diagnósticos, ingresos, hostings ni conversaciones. '
                  'Si ya no se necesita, se borra a mano desde la pestaña «Huérfanos» de Clientes.')
def detect_orphan_client(scope):
    from accounts.models import Project, UserProfile
    from content.models import BusinessProposal, CommunicationThread, HostingRecord, IncomeRecord, WebAppDiagnostic
    # Match the orphan tab's six relations, including retained history. Base
    # managers keep an archived or retained relation from looking like no data.
    related = (
        (BusinessProposal, 'client_id', 'pk'), (Project, 'client_id', 'user_id'),
        (WebAppDiagnostic, 'client_id', 'pk'), (IncomeRecord, 'client_id', 'pk'),
        (HostingRecord, 'client_id', 'pk'), (CommunicationThread, 'client_id', 'pk'),
    )
    rows = UserProfile._base_manager.filter(role=UserProfile.ROLE_CLIENT, archived_at__isnull=True)
    for model, field, owner in related:
        rows = rows.filter(~Exists(model._base_manager.filter(**{field: OuterRef(owner)})))
    rows = scope.limit(rows.select_related('user'), PROFILE)
    for profile in rows.order_by('pk'):
        label = client_label(profile)
        yield Finding(
            rule_id='CL4',
            subjects=(RecordRef(PROFILE, profile.pk, label),),
            evidence={'profile': profile.pk},
            message=f'«{label}» no tiene propuestas, proyectos, diagnósticos, ingresos, hostings ni '
                    'conversaciones. Si ya no lo necesitas, bórralo a mano desde la pestaña «Huérfanos» '
                    'de Clientes.',
        )


@rule(id='CL5', domain='clients', severity='high', fix_kinds=(REPORT_ONLY,),
      title='Proyecto cuyo dueño no es cliente',
      description='El dueño de un proyecto no tiene perfil de cliente, así que el proyecto no aparece en Clientes '
                  'ni puede tener su conversación principal. Se corrige a mano.')
def detect_project_owner_without_client_profile(scope):
    from accounts.models import Project, UserProfile
    rows = (scope.limit(Project._base_manager.exclude(client__profile__role=UserProfile.ROLE_CLIENT), PROJECT)
            .order_by('pk').values_list('pk', 'name', 'client_id', 'client__email', 'client__profile__role'))
    for pk, name, user_id, email, role in rows:
        owner = 'es un administrador, no un cliente' if role == UserProfile.ROLE_ADMIN else 'no tiene perfil de cliente'
        yield Finding(
            rule_id='CL5',
            subjects=(RecordRef(PROJECT, pk, name), RecordRef(USER, user_id, email)),
            evidence={'project': pk, 'user': user_id, 'role': role},
            message=f'El proyecto «{name}» pertenece a {email}, que {owner}. Así no aparece en Clientes ni recibe '
                    'su conversación principal: crea el perfil de cliente o pasa el proyecto al cliente correcto.',
        )
