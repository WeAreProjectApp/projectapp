"""Current billing rows, locked Project -> financial origin -> Document.

Discovery reads only identify rows to lock. Every relationship is checked again
with a current locking read; callers must keep their writer transaction open.
No locking query joins a nullable relation.
"""
from dataclasses import dataclass

from django.db.models import Q

from accounts.models import Project
from accounts.services.billing_access import BillingConflict
from content.models import Document, ExpenseRecord, HostingRecord, IncomeRecord


@dataclass
class LockedBillingRows:
    projects: dict
    incomes: dict
    hostings: dict
    documents: dict


def _discover(model, ids, fields):
    requested = set(ids)
    rows = {row['id']: row for row in model.objects.filter(pk__in=requested).values('id', *fields)}
    if rows.keys() != requested:
        raise BillingConflict()
    return rows


def _lock_current(model, discovered, fields, projects):
    rows = {}
    for row in model.objects.select_for_update().filter(pk__in=discovered).order_by('pk'):
        if any(getattr(row, field) != discovered[row.pk][field] for field in fields):
            raise BillingConflict()
        row.project = projects.get(row.project_id)
        rows[row.pk] = row
    if rows.keys() != discovered.keys():
        raise BillingConflict()
    return rows


def lock_billing_rows(*, document_ids=(), income_ids=(), hosting_ids=(),
                      project_ids=(), include_origin_documents=False,
                      include_income_children=False):
    doc_fields = ('project_id', 'income_record_id', 'hosting_record_id')
    docs = _discover(Document, document_ids, doc_fields)
    incomes = set(income_ids) | {row['income_record_id'] for row in docs.values() if row['income_record_id']}
    hostings = set(hosting_ids) | {row['hosting_record_id'] for row in docs.values() if row['hosting_record_id']}
    if include_income_children:
        incomes.update(IncomeRecord.objects.filter(expected_income_id__in=incomes).values_list('pk', flat=True))
    if include_origin_documents and (incomes or hostings):
        origin_docs = Document.objects.filter(Q(income_record_id__in=incomes) | Q(hosting_record_id__in=hostings))
        docs.update({row['id']: row for row in origin_docs.values('id', *doc_fields)})
        incomes.update(row['income_record_id'] for row in docs.values() if row['income_record_id'])
        hostings.update(row['hosting_record_id'] for row in docs.values() if row['hosting_record_id'])
    income_rows = _discover(IncomeRecord, incomes, ('project_id',))
    hosting_rows = _discover(HostingRecord, hostings, ('project_id',))
    projects_needed = set(project_ids)
    for discovered in (docs, income_rows, hosting_rows):
        projects_needed.update(row['project_id'] for row in discovered.values() if row['project_id'])
    projects_needed.discard(None)
    projects = {row.pk: row for row in Project.objects.select_for_update().filter(pk__in=projects_needed).order_by('pk')}
    if projects.keys() != projects_needed:
        raise BillingConflict()
    # These are bare row queries: joining client/project here would lock more
    # tables or fail on nullable outer joins in databases that prohibit it.
    locked_incomes = _lock_current(IncomeRecord, income_rows, ('project_id',), projects)
    locked_hostings = _lock_current(HostingRecord, hosting_rows, ('project_id',), projects)
    locked_docs = _lock_current(Document, docs, doc_fields, projects)
    for doc in locked_docs.values():
        doc.income_record = locked_incomes.get(doc.income_record_id)
        doc.hosting_record = locked_hostings.get(doc.hosting_record_id)
    return LockedBillingRows(projects, locked_incomes, locked_hostings, locked_docs)


def lock_billing_document(document_id, *, project_ids=()):
    return lock_billing_rows(document_ids=[document_id], project_ids=project_ids).documents.get(document_id)


def current_income_paid_total(income):
    """Same settlement sum, from current child rows after Project/Income locks."""
    liquids = IncomeRecord.objects.select_for_update().filter(
        expected_income=income, kind=IncomeRecord.Kind.LIQUID,
    ).order_by('pk')
    deductions = ExpenseRecord.objects.select_for_update().filter(
        source_income=income,
    ).exclude(deduction_type='').order_by('pk')
    return (sum((row.total_amount for row in liquids), 0)
            + sum((row.total_amount for row in deductions), 0))
