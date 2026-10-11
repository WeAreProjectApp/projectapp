"""Client rules (CL*).

Duplicate groups (CL1-CL3) share one finding shape that the client-merge fixer
consumes: subjects are the group's profiles ordered by pk, ``evidence`` is
``{'key': <normalized key>, 'profiles': [pks]}`` and the operator picks
``survivor`` and ``duplicate`` (two different profiles of the group). A merge
handles one pair; a group of three leaves a new group of two, a new finding.
CL4 (orphan clients) and CL5 (projects owned by a non-client) only report.
"""
from collections import defaultdict

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


@rule(id='CL4', domain='clients', severity='low', fix_kinds=(REPORT_ONLY,), version=2,
      title='Cliente sin ningún registro',
      description='Un cliente activo sin propuestas, proyectos, diagnósticos, ingresos, hostings, conversaciones ni '
                  'ningún otro registro que impida borrarlo. Si ya no se necesita, se borra a mano desde la pestaña '
                  '«Huérfanos» de Clientes.')
def detect_orphan_client(scope):
    from accounts.models import UserProfile
    from accounts.services.client_deletion import blocked_condition
    # The orphan tab's cut and the delete guard's: nothing that would stop
    # deleting the client's user. The six business relations are part of it;
    # base managers keep archived or retained rows from looking like no data.
    rows = (UserProfile._base_manager.filter(role=UserProfile.ROLE_CLIENT, archived_at__isnull=True)
            .exclude(blocked_condition('user_id')))
    rows = scope.limit(rows.select_related('user'), PROFILE)
    for profile in rows.order_by('pk'):
        label = client_label(profile)
        yield Finding(
            rule_id='CL4',
            subjects=(RecordRef(PROFILE, profile.pk, label),),
            evidence={'profile': profile.pk},
            message=f'«{label}» no tiene propuestas, proyectos, diagnósticos, ingresos, hostings, '
                    'conversaciones ni otros registros que impidan borrarlo. Si ya no lo necesitas, bórralo a '
                    'mano desde la pestaña «Huérfanos» de Clientes.',
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


# ── CL6 · client with no business left but rows that condition its delete ───

def _trace_relations():
    """SET_NULL relations to the client that are not authorship: what a delete leaves without client.

    Read from the merge policy's canonical inventory (``discover_relations``,
    hidden fields included), so a new relation shows up here on its own.
    """
    from django.db.models import SET_NULL
    from content.services.client_merge_policy import AUTHORSHIP_RELATIONS, discover_relations
    return tuple(relation for key, relation in sorted(discover_relations().items())
                 if relation.field.remote_field.on_delete is SET_NULL and key not in AUTHORSHIP_RELATIONS)


def _has_traces(relations):
    """True when any trace relation has a row for the outer client profile, in the same query."""
    from functools import reduce
    from operator import or_

    from django.contrib.auth import get_user_model
    from django.db.models import Exists, OuterRef
    user_model = get_user_model()
    return reduce(or_, (
        Exists(relation.model._base_manager.filter(
            **{relation.field.attname: OuterRef('user_id' if relation.target is user_model else 'pk')}))
        for relation in relations
    ))


def _trace_counts(profile, relations):
    counts = {}
    for relation in relations:
        rows = relation.rows_for(profile).count()
        if rows:
            counts[relation.key] = rows
    return counts


def _counted_text(counts):
    return ', '.join(f'{name} ({rows})' for name, rows in sorted(counts.items()))


@rule(id='CL6', domain='clients', severity='low', fix_kinds=(REPORT_ONLY,),
      title='Cliente sin actividad comercial con registros que condicionan su borrado',
      description='Un cliente sin propuestas, proyectos, diagnósticos, ingresos, hostings ni conversaciones conserva '
                  'otros registros: unos impiden borrarlo (carpetas de comunicaciones, alianzas, proyectos conservados, '
                  'registros de entrega…) y otros quedarían sin cliente si se borra (documentos, carpetas del gestor, '
                  'correos, enlaces). Es informativa: dice qué hay antes de decidir.')
def detect_client_with_residual_records(scope):
    from django.db.models import Exists, OuterRef, Q
    from accounts.models import Project, UserProfile
    from accounts.services.client_deletion import blocker_counts, deletion_blocked_annotation
    from content.models import BusinessProposal, CommunicationThread, HostingRecord, IncomeRecord, WebAppDiagnostic
    business = (
        (BusinessProposal, 'client_id', 'pk'), (Project, 'client_id', 'user_id'),
        (WebAppDiagnostic, 'client_id', 'pk'), (IncomeRecord, 'client_id', 'pk'),
        (HostingRecord, 'client_id', 'pk'), (CommunicationThread, 'client_id', 'pk'),
    )
    rows = UserProfile._base_manager.filter(role=UserProfile.ROLE_CLIENT, archived_at__isnull=True)
    for model, field, owner in business:
        rows = rows.filter(~Exists(model._base_manager.filter(**{field: OuterRef(owner)})))
    traces = _trace_relations()
    # One query picks the clients holding anything; only those get per-relation counts.
    rows = (rows.annotate(deletion_blocked=deletion_blocked_annotation())
            .filter(Q(deletion_blocked=True) | _has_traces(traces)))
    for profile in scope.limit(rows.select_related('user'), PROFILE).order_by('pk'):
        blocking = blocker_counts(profile.user_id) if profile.deletion_blocked else {}
        leftovers = _trace_counts(profile, traces)
        if not blocking and not leftovers:
            continue  # nothing at all: CL4 reports it
        label = client_label(profile)
        parts = []
        if blocking:
            parts.append(f'Impiden borrarlo: {_counted_text(blocking)}.')
        if leftovers:
            parts.append(f'Quedarían sin cliente si se borra: {_counted_text(leftovers)}.')
        yield Finding(
            rule_id='CL6',
            subjects=(RecordRef(PROFILE, profile.pk, label),),
            evidence={'profile': profile.pk, 'blocking': sorted(blocking), 'traces': sorted(leftovers)},
            message=f'«{label}» no tiene propuestas, proyectos, diagnósticos, ingresos, hostings ni conversaciones, '
                    f'pero conserva otros registros. {" ".join(parts)}',
        )
