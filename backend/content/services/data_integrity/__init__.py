"""Data integrity engine: find orphan, duplicate and inconsistent business data.

A fixed, versioned catalog of rules (``catalog`` + ``rules/``) detects findings
inside a scope. Fixes run through a hash-bound preview and apply, are recorded
in ``DataIntegrityOperation`` with before/after values, and can be undone
exactly while nothing changed afterwards (``engine``). Fixers reuse the domain
writers (``fixes/``). See docs/DATA_INTEGRITY.md.
"""
