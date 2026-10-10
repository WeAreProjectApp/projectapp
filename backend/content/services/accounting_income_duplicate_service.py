"""Prefill for duplicating an income — opening the next period of a charge.

Persists nothing. The panel opens its income form with this payload so the
date or the amount can be adjusted before confirming, and the record is then
created through the ordinary create endpoint: that is what keeps the audit
row, the pocket sync and the notification identical to any other income.

Three rules carry the intent of the action:

* the draft is always ``expected``, whatever the original was — duplicating a
  collected hosting to open its next cycle is the whole use case;
* nothing belonging to the original occurrence travels. Its settlement links,
  its cuenta de cobro, its deductions, its silenced calendar and its history
  all stay behind. Most of that is free (they are reverse relations, or fields
  the write serializer cannot set), so the draft simply omits them;
* **the fields that govern the shape of the form are always inherited**, unless
  the intent of the action overrides them — and then the override is declared
  where it happens. They are the ones that go unnoticed when the copied fields
  are listed out, and the ones that break the loudest when they are missing:
  the form opens configured for a different kind of income than the one being
  copied, and every date it then proposes is answering the wrong question.

  Here that is ``origin`` (single date or covered window), ``ledger``
  (partner split or a single value) and ``period_cadence`` (the length of the
  window). ``kind`` and ``destination`` govern the form too and are the two
  declared overrides: a duplicate is born pending, and pocket is a
  liquid-only destination that resets along with it.

  Copying is faithful, not helpful: an original with no ``origin`` — most of
  the book, which predates the field — duplicates into a form with no origin,
  and it is the form that says so rather than this service guessing a line of
  business out of the concept text.

The date is the one field that cannot simply be copied, and it is the reason
duplicating opens the form instead of writing the row. When the hosting cycle
can be resolved the draft proposes it; otherwise the date comes back empty and
``cycle_options`` gives the form the candidate dates to fill it with in one
click. Neither path ever guesses silently — a wrong date already filled in is
worse than an empty one the operator is forced to complete.

Empty is not the same as ungrounded, though. ``period_anchor`` always states
what this duplicate counts from — the original's recorded window, its hosting
cycle, or failing both its own date — so a form that cannot prefill can still
chain the instant a cadence is picked, and can say on screen why the dates
landed where they did. Today is never the answer: it chains with nothing.
"""
from datetime import date, timedelta

from content.models import HostingRecord, IncomeRecord, RecurringPayment
from content.serializers.accounting import money_str
from content.utils import add_months, today_bogota

HOSTING_CYCLE = 'hosting_cycle'
INCOME_PERIOD = 'income_period'
ORIGINAL_DATE = 'original_date'

# Cadences the form offers so the next period is one click away when the
# hosting lookup below cannot resolve one on its own — which is the normal
# case, not the exception: the book is written as free-text concepts, so most
# incomes carry no ``origin`` and no client for it to work from.
CYCLE_OPTION_MONTHS = (1, 3, 6, 12)


def resolve_hosting_cycle_months(income):
    """Months of the hosting cycle behind this income, or None.

    An income does not record which hosting it belongs to — ``origin`` is a
    label, not a link — so the hosting is resolved by client, narrowed by
    project when the income has one. Only an unambiguous match counts: with no
    hosting, or with several disagreeing on the modality, proposing a date
    would be guessing, and a wrong date already filled in is worse than an
    empty one the operator is forced to complete.
    """
    if income.origin != IncomeRecord.Origin.HOSTING or not income.client_id:
        return None
    hostings = HostingRecord.objects.filter(
        is_active=True, client_id=income.client_id,
    )
    if income.project_id:
        hostings = hostings.filter(project_id=income.project_id)
    modalities = set(hostings.values_list('payment_modality', flat=True))
    if len(modalities) != 1:
        return None
    return HostingRecord.MODALITY_MONTHS.get(modalities.pop())


def next_period_date(income):
    """The date one cycle after this income's, or None when unknown.

    ``add_months`` clamps the day, so a charge on the 31st lands on the last
    day of a shorter month instead of overflowing into the next one.
    """
    months = resolve_hosting_cycle_months(income)
    if not months:
        return None
    return add_months(income.period_date, months)


def next_billing_date(income, next_start):
    """Expected-payment date of the window opening on ``next_start``, keeping
    the original's offset from its own start (an Oct window paid in Nov makes
    the Apr window paid in May). Whole-month moves shift by months
    (``add_months`` clamps the day); other windows move by the same days.
    """
    if not income.period_start or income.period_date == income.period_start:
        return next_start
    months = (
        (next_start.year - income.period_start.year) * 12
        + next_start.month - income.period_start.month
    )
    if add_months(income.period_start, months) == next_start:
        return add_months(income.period_date, months)
    return income.period_date + (next_start - income.period_start)


def build_cycle_options(income):
    """One candidate next date per offered cadence, counted from the original.

    These are the dates for an income with no covered window — the single
    ``period_date``. A hosting income advances its window in the panel instead
    (``frontend/utils/periodDates.js`` mirrors ``add_months``, day clamp
    included), because the requirement is that the dates move the instant a
    cadence is picked and a round trip per click cannot deliver that.

    Offering the dates is deliberately not the same as proposing one. The
    operator is who knows the cadence, so nothing is filled in behind their
    back: this only spares them from computing the date by hand.
    """
    return [
        {
            'months': months,
            'date': add_months(income.period_date, months).isoformat(),
        }
        for months in CYCLE_OPTION_MONTHS
    ]


def next_period_range(income):
    """(start, end) of the following covered window, or None.

    Only a hosting income with a recorded window can propose one. The next
    window starts the day after the recorded end (``period_end`` is
    inclusive) and lasts one cadence — ``custom`` or a missing cadence falls
    back to the original window's own length, which is the only cadence the
    record actually attests.
    """
    if income.origin != IncomeRecord.Origin.HOSTING:
        return None
    if not (income.period_start and income.period_end):
        return None
    start = income.period_end + timedelta(days=1)
    months = RecurringPayment.FREQUENCY_MONTHS.get(income.period_cadence)
    if months:
        end = add_months(start, months) - timedelta(days=1)
    else:
        end = start + (income.period_end - income.period_start)
    return start, end


def build_period_anchor(income):
    """Where the duplicate's window opens, and what that was read off.

    Duplicating exists to open the period that follows, so the count starts at
    the original — never at today, which chains with nothing. Three grounds, in
    descending order of how much the original actually attests:

    * ``income_period`` — the recorded window. The next one opens the day after
      it closed, and that start is FIXED: changing the cadence in the form
      lengthens the window without moving where it begins.
    * ``hosting_cycle`` — no window, but the client's hosting resolves without
      ambiguity, so the catalog states the length. Also a fixed start.
    * ``original_date`` — neither of the above, which is the normal case until
      the book is completed. The original's own date is read as the START of
      the period that charge covered, so this one opens where that would have
      closed. ``start`` deliberately stays ``None``: only the cadence the
      operator picks can state that length, and the form computes it from
      ``origin_date`` the instant it is picked.

    ``source`` is ``None`` only when the original carries no date at all — not
    reachable through the model today (``period_date`` is NOT NULL), but the
    form still says so rather than opening a window on today in silence.

    No origin guard here: ``next_period_range`` and
    ``resolve_hosting_cycle_months`` already require hosting, so an original of
    another origin lands on ``original_date`` with its date — which is exactly
    what the form needs when the operator switches the origin to Hosting after
    the draft opened.
    """
    origin_date = income.period_date
    anchor = {
        'source': None,
        'start': None,
        'origin_start': None,
        'origin_end': None,
        'origin_date': origin_date.isoformat() if origin_date else None,
    }
    period_range = next_period_range(income)
    if period_range:
        anchor['source'] = INCOME_PERIOD
        anchor['start'] = period_range[0].isoformat()
        anchor['origin_start'] = income.period_start.isoformat()
        anchor['origin_end'] = income.period_end.isoformat()
        return anchor
    if not origin_date:
        return anchor
    months = resolve_hosting_cycle_months(income)
    if months:
        anchor['source'] = HOSTING_CYCLE
        anchor['start'] = add_months(origin_date, months).isoformat()
        return anchor
    anchor['source'] = ORIGINAL_DATE
    return anchor


def suggest_next_period_start(client_id, project_id=None):
    """``(previous end, proposed start)`` for a client's next hosting window.

    Creating a hosting income has no original to count from, so the antecedent
    is the last window already on the book: the new one opens the day after
    that one closed (``period_end`` is inclusive). With nothing recorded — the
    first charge of a client — the proposal is simply today.

    An income does not record which hosting it belongs to (``origin`` is a
    label, not a link), so the antecedent is looked up by client and narrowed
    by project when the form already has one. The ambiguity guard of
    ``resolve_hosting_cycle_months`` applies here too: with several active
    hostings on the client and no project telling them apart, the last window
    may well belong to a different one, and a wrong date already filled in is
    worse than an empty one the operator is forced to complete.
    """
    today = today_bogota()
    if not client_id:
        return None, today
    if project_id is None and HostingRecord.objects.filter(
        is_active=True, client_id=client_id,
    ).count() > 1:
        return None, today
    windows = IncomeRecord.objects.filter(
        origin=IncomeRecord.Origin.HOSTING,
        client_id=client_id,
        period_end__isnull=False,
    )
    if project_id is not None:
        windows = windows.filter(project_id=project_id)
    previous_end = (
        windows.order_by('-period_end').values_list('period_end', flat=True).first()
    )
    if not previous_end:
        return None, today
    return previous_end, previous_end + timedelta(days=1)


def build_income_duplicate_draft(income):
    """Return the prefill for a new income copied from ``income``."""
    from accounts.services.proposal_client_service import (
        build_client_display_name,
    )

    # One resolution for both: what the form prefills and what it says the
    # prefill was read off are the same decision, and `resolve_hosting_cycle_months`
    # hits the database, so it is not made twice.
    anchor = build_period_anchor(income)
    period_start = period_end = period_date = None
    period_date_source = None
    if anchor['source'] == INCOME_PERIOD:
        # The recorded window beats the hosting lookup: it is first-hand data
        # on this very charge, while the lookup infers from the catalog.
        period_start, period_end = next_period_range(income)
        period_date = next_billing_date(income, period_start)
        period_date_source = INCOME_PERIOD
    elif anchor['source'] == HOSTING_CYCLE:
        period_date = date.fromisoformat(anchor['start'])
        period_date_source = HOSTING_CYCLE
    # `original_date` proposes nothing to prefill on purpose: its length is the
    # cadence the operator has not picked yet. The anchor travels all the same,
    # so the form can chain the moment they do.
    return {
        'concept': income.concept,
        # Always pending, whatever the original was. Pocket is a liquid-only
        # destination server-side, so it resets along with the kind.
        'kind': IncomeRecord.Kind.EXPECTED,
        'destination': IncomeRecord.Destination.PARTNERS,
        'period_date': period_date.isoformat() if period_date else None,
        'period_date_source': period_date_source,
        'period_start': period_start.isoformat() if period_start else None,
        'period_end': period_end.isoformat() if period_end else None,
        'period_cadence': income.period_cadence,
        # Always offered, including when the hosting cycle already proposed a
        # date: the operator may well disagree with it, and these count from
        # the original's date, never from the proposal.
        'cycle_options': build_cycle_options(income),
        # Where the window this duplicate opens is counted from, and off what.
        # The form anchors its own arithmetic here instead of on today, and
        # says so on screen: dates that appear on their own are dates nobody
        # can tell apart from a guess.
        'period_anchor': anchor,
        'ledger': income.ledger,
        'client': income.client_id,
        # Same shape as the list rows: the form shows this as the label of the
        # client picker, and None keeps "sin cliente" distinct from a blank.
        'client_name': (
            build_client_display_name(income.client) if income.client_id else None
        ),
        'project': income.project_id,
        'project_name': income.project.name if income.project_id else None,
        'origin': income.origin,
        'total_amount': money_str(income.total_amount),
        'vat_rate': income.vat_rate,
        'gustavo_amount': money_str(income.gustavo_amount),
        'carlos_amount': money_str(income.carlos_amount),
        'notes': income.notes,
    }
