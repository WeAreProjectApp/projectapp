"""Engine adapter for client merges (CL1-CL3); the merge itself lives in content.services.client_merge."""
from rest_framework.exceptions import PermissionDenied
from content.services import client_merge
from content.services.client_merge_policy import COLLISION, RELINK, discover_relations
from content.services.data_integrity.catalog import register_fixer
from content.services.data_integrity.fixes.base import Fixer, required_choice
from content.services.data_integrity.fixes.merge_folders import actor_blockers, recorded_rows, restore_rows
from content.services.data_integrity.snapshots import model_for
from content.services.data_integrity.types import MERGE_CLIENTS


def merge_fields():
    """Only columns the writer or its explicit domain signals can change."""
    fields = {}
    for key, relation in discover_relations().items():
        if client_merge.RELATION_POLICIES.get(key) in (RELINK, COLLISION):
            fields.setdefault(relation.model._meta.label_lower, set()).add(relation.field.attname)
    extras = {
        'auth.user': ('first_name', 'last_name', 'email', 'username', 'is_active'),
        'accounts.userprofile': (*client_merge.PROFILE_FIELDS, 'billing_code', 'archived_at', 'archived_by_id'),
        'content.document': ('client_user_id', 'folder_id', 'updated_by_id'),
        'content.documentfolder': ('parent_id', 'order', 'name', 'project_id', 'client_user_id', 'managed_client_id',
                                   'is_archived', 'archived_at', 'archived_via_folder_id'),
        'content.communicationthread': ('client_id', 'managed_client_id', 'title', 'project_id',
                                        'is_archived', 'archived_at'),
        'content.hostingrecord': ('client_name', 'client_email', 'client_contact_name', 'client_identification'),
        'content.businessproposal': ('client_name', 'client_email', 'client_phone'),
        'content.webappdiagnostic': ('client_name', 'client_email', 'client_phone', 'client_company'),
        'content.documentcollectionaccount': ('customer_name', 'customer_email', 'customer_identification',
                                              'customer_identification_type', 'customer_contact_name',
                                              'customer_address'),
    }
    for label, names in extras.items():
        concrete = {field.attname for field in model_for(label)._meta.concrete_fields}
        fields.setdefault(label, set()).update(name for name in names if name in concrete)
    return {label: tuple(sorted(names)) for label, names in fields.items()}


class MergeClientsFixer(Fixer):
    kind = MERGE_CLIENTS
    exclusive = True
    max_closure = 1000
    fields = merge_fields()

    def plan(self, finding, params, *, actor):
        options = [{'value': pk} for pk in finding.evidence['profiles']]
        survivor, left = required_choice(params, 'survivor', options, 'el cliente que se conserva')
        duplicate, right = required_choice(params, 'duplicate', options, 'el cliente duplicado')
        if survivor is None or duplicate is None:
            return self.new_plan(params, blockers=left + right + actor_blockers(actor))
        merge = client_merge.plan_client_merge(survivor, duplicate, resolutions=params.get('resolutions'), actor=actor)
        payload = merge['preview']
        blockers = list(payload['blockers'])
        # One summarized entry per relation, plus the operator's complete summary.
        changes = [{'model': 'accounts.userprofile', 'id': duplicate, 'field': 'merged_into',
                    'before': None, 'after': survivor, 'preview': payload}]
        changes += [{'model': key.rsplit('.', 1)[0].lower(), 'id': None, 'field': key.rsplit('.', 1)[1],
                     'before': duplicate, 'after': survivor, 'count': len(ids),
                     'sample_ids': ids[:client_merge.SAMPLE_SIZE], 'relation': key}
                    for key, ids in sorted(merge['relations'].items()) if ids]
        return self.new_plan(params, closure=merge['closure'], changes=changes, blockers=blockers,
                             warnings=payload['warnings'], guards=merge['guards'], context={'merge': merge})

    def apply(self, plan, *, actor):
        client_merge.apply_client_merge(plan.context['merge'], actor=actor)

    def revert(self, step, *, actor):
        """P10-P1 without signals, followed by a second exact snapshot restore."""
        if actor_blockers(actor):
            raise PermissionDenied('Deshacer una fusión requiere un superusuario activo.', code='actor_not_superuser')
        client_merge.document_folder_merge.lock_folder_tree()
        rows = recorded_rows(step['items'])
        guards = step['guards']
        duplicate, survivor = guards['duplicate'], guards['survivor']
        profile_d = ('accounts.userprofile', duplicate)
        if profile_d in rows:
            archive = {key: value for key, value in rows[profile_d].items() if key in ('archived_at', 'archived_by_id')}
            if archive:
                restore_rows({profile_d: archive}, [profile_d])
        # Restore managed pointers and active roots in single UPDATEs before
        # children/documents move back; both CHECK constraints hold throughout.
        for name, label in (('documents', 'content.documentfolder'), ('communications', 'content.communicationthread')):
            root = guards['containers'][name]['duplicate_root']
            key = (label, root)
            if key in rows:
                restore_rows(rows, [key])
        ranks = {'content.businessproposal': 8, 'content.webappdiagnostic': 8,
                 'content.incomerecord': 7, 'content.hostingrecord': 7,
                 'content.document': 6, 'content.documentcollectionaccount': 6,
                 'accounts.project': 5, 'content.documentfolder': 4,
                 'content.communicationfolder': 3, 'content.communicationthread': 3,
                 'content.clientdocumentnumbersequence': 2, 'accounts.userprofile': 1, 'auth.user': 0}

        def rank(key):
            label, pk = key
            # Restore S's login before D can reclaim its original username.
            if label == 'auth.user':
                return (0, pk != guards['survivor_user'], pk)
            return (-ranks.get(label, 9), 0, pk)

        keys = sorted(rows, key=rank)
        nonidentity = [key for key in keys if key[0] not in ('accounts.userprofile', 'auth.user')]
        restore_rows(rows, nonidentity)
        # Release S's adopted code before restoring D's reserved code.
        if guards['billing']['action'] == 'transfer':
            client_merge._update(model_for('accounts.userprofile'), survivor, billing_code=None)
        profile_keys = [key for key in keys if key[0] == 'accounts.userprofile']
        restore_rows(rows, profile_keys)
        user_keys = [key for key in keys if key[0] == 'auth.user']
        restore_rows(rows, user_keys)
        restore_rows(rows, keys)

    def guards_changed(self, step):
        return client_merge.client_merge_undo_blockers(step)


register_fixer(('CL1', 'CL2', 'CL3'), MergeClientsFixer())
