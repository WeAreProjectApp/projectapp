import os

import coverage as coverage_module
import pytest

# Import before time freezes: DRF otherwise captures freezegun's fake_time as
# a bound throttle timer that keeps breaking requests after the freeze ends.
import rest_framework.throttling  # noqa: F401
from rest_framework.test import APIClient

# Bar widths: per-file bars use MINI, the TOTAL row uses WIDE
_MINI_W = 13
_WIDE_W = 15
_APP_NAMES = ("content", "accounts", "projectapp")


def _color_for(pct):
    """Return a pytest terminal color name based on coverage percentage."""
    if pct > 80:
        return "green"
    if pct >= 50:
        return "yellow"
    return "red"


def _bar(pct, width):
    """Build a Unicode progress bar: filled for covered, dots for uncovered."""
    filled = round(pct / 100 * width)
    return "\u2588" * filled + "\u00b7" * (width - filled)


def _refuse_unsafe_session() -> None:
    """Abort before collection if this session could reach production.

    Runs ahead of django_db_setup and of every test. The refusals live in
    projectapp/tests/isolation.py; projectapp/settings_test.py satisfies them.
    """
    from django.conf import settings

    from projectapp.tests.isolation import (
        collect_storage_locations,
        deployed_clone_refusal,
        settings_refusals,
        storage_refusals,
    )

    reasons = settings_refusals(settings, os.environ)
    deployed_clone = deployed_clone_refusal(settings.BASE_DIR)
    if deployed_clone:
        reasons.append(deployed_clone)
    reasons += storage_refusals(
        getattr(settings, "TEST_FILE_ROOT", None),
        settings.BASE_DIR,
        collect_storage_locations(),
    )
    if reasons:
        pytest.exit(
            "Refusing to run the test suite:\n  - " + "\n  - ".join(reasons),
            returncode=pytest.ExitCode.USAGE_ERROR,
        )


def pytest_sessionstart(session) -> None:
    """Refuse a production-reachable session, then trim the pytest-cov summary."""
    _refuse_unsafe_session()
    cov_plugin = session.config.pluginmanager.get_plugin("_cov")
    if cov_plugin is None:
        return
    hook = session.config.pluginmanager.hook.pytest_terminal_summary
    for impl in hook.get_hookimpls():
        if impl.plugin is cov_plugin:
            impl.function = lambda *args, **kw: None
            break


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    """Remove term report formats from pytest-cov options."""
    try:
        if hasattr(config.option, "cov_report"):
            config.option.cov_report = [
                r for r in config.option.cov_report
                if not r.startswith("term")
            ]
    except Exception:
        pass


@pytest.hookimpl(trylast=True)
def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Custom coverage report with per-file table and Top-N focus footer."""
    root_dir = os.path.dirname(__file__)
    cov_file = os.path.join(root_dir, ".coverage")
    if not os.path.exists(cov_file):
        return

    try:
        cov = coverage_module.Coverage(data_file=cov_file)
        cov.load()
    except Exception:
        return

    results = []
    try:
        measured = cov.get_data().measured_files()
    except Exception:
        return

    for filepath in measured:
        try:
            short = os.path.relpath(filepath, root_dir).replace("\\", "/")
        except ValueError:
            continue
        if not short.startswith(tuple(f"{app}/" for app in _APP_NAMES)):
            continue
        if "/tests/" in short or "/migrations/" in short:
            continue
        try:
            analysis = cov._analyze(filepath)
            stmts = len(analysis.statements)
            if stmts == 0:
                continue
            missing = len(analysis.missing)
            pct = (stmts - missing) / stmts * 100
            results.append({"path": short, "stmts": stmts, "missing": missing, "pct": pct})
        except Exception:
            continue

    if not results:
        return

    results.sort(key=lambda r: r["path"])
    total_stmts = sum(r["stmts"] for r in results)
    total_missing = sum(r["missing"] for r in results)
    total_pct = (total_stmts - total_missing) / total_stmts * 100 if total_stmts > 0 else 0
    top_n = sorted([r for r in results if r["missing"] > 0], key=lambda x: (x["pct"], -x["missing"]))[:3]

    try:
        term_w = terminalreporter._tw._width
    except AttributeError:
        import shutil
        term_w = shutil.get_terminal_size().columns

    _FIXED = 2 + 2 + 5 + 2 + 4 + 2 + 7 + 2 + 1 + _MINI_W + 1
    path_w = min(max(term_w - _FIXED - 2, 20), max((len(r["path"]) for r in results), default=40))
    path_w = max(path_w, 20)

    for r in results:
        if len(r["path"]) > path_w:
            r["path"] = r["path"][:path_w - 1] + "\u2026"

    tw = terminalreporter
    tw.write_sep("=", "COVERAGE REPORT", bold=True)
    tw.write("\n")
    for r in results:
        color = _color_for(r["pct"])
        mini = _bar(r["pct"], _MINI_W)
        tw.write(f"  {r['path']:<{path_w}}  {r['stmts']:>5}  {r['missing']:>4}  ")
        tw.write(f"{r['pct']:>6.1f}%  ", **{color: True})
        tw.write("[")
        tw.write(mini, **{color: True})
        tw.write("]\n")

    tw.write("\n")
    c = _color_for(total_pct)
    wide = _bar(total_pct, _WIDE_W)
    tw.write(f"  {'TOTAL':<{path_w}}  {total_stmts:>5}  {total_missing:>4}  ", bold=True)
    tw.write(f"{total_pct:>6.1f}%  ", bold=True, **{c: True})
    tw.write("[", bold=True)
    tw.write(wide, bold=True, **{c: True})
    tw.write("]\n\n", bold=True)

    dash = "\u2500" * 10
    n = len(top_n)
    label = f"Top-{n} files to focus on" if top_n else "All files fully covered"
    tw.write(f"  {dash}  {label}  ", bold=True)
    tw.write(f"(total project: {total_pct:.1f}%)  ", bold=True)
    tw.write(f"{dash}\n", bold=True)
    if not top_n:
        tw.write("\n", green=True)
    else:
        for i, r in enumerate(top_n, 1):
            color = _color_for(r["pct"])
            mini = _bar(r["pct"], _MINI_W)
            tw.write(f"  {i}.  ")
            tw.write(f"{r['pct']:>5.1f}%", **{color: True})
            tw.write("  [")
            tw.write(mini, **{color: True})
            tw.write(f"]  {r['path']}")
            tw.write(f"   ({r['missing']} lines uncovered)\n")
        tw.write("\n")


@pytest.fixture(autouse=True)
def disable_recaptcha_for_tests(settings):
    """Ordinary auth tests opt out; CAPTCHA tests explicitly enable protection."""
    settings.RECAPTCHA_ENABLED = False
    settings.RECAPTCHA_SECRET_KEY = ''


@pytest.fixture(autouse=True)
def allow_fake_data_for_tests(settings):
    """Tests are an explicit safe environment for destructive seed commands."""
    settings.FAKE_DATA_ALLOWED = True


@pytest.fixture(autouse=True)
def project_access_cipher_for_tests(monkeypatch):
    """Provide an isolated Fernet key to tests and fake-data commands."""
    from accounts.services import credential_cipher

    monkeypatch.setenv(
        'PROJECT_ACCESS_CIPHER_KEY',
        'uFJ2bxSRv2V4OLA4y-BxJcTYL8QxIrRiG4rZa_3BaiI=',
    )
    credential_cipher._get_cipher.cache_clear()
    yield
    credential_cipher._get_cipher.cache_clear()


@pytest.fixture(scope='session', autouse=True)
def isolate_seeded_email_copy_recipient(django_db_setup, django_db_blocker):
    """Keep recipient-dependent tests explicit while testing the seed separately.

    Tolerates an unmigrated database on purpose. This fixture is autouse and
    session-scoped, so it also runs for a selection made entirely of tests that
    never touch the database — and there the schema does not exist yet, so the
    query raises instead of finding nothing to delete. That selection was
    unreachable while the suite ran as one job; with the CI split into shards it
    is one `pytest content/tests/utils` away.
    """
    from django.db import OperationalError, ProgrammingError

    from content.models import EmailCopyRecipient

    with django_db_blocker.unblock():
        try:
            EmailCopyRecipient.objects.filter(
                email='carlos18bp@gmail.com',
            ).delete()
        except (OperationalError, ProgrammingError):
            # No schema means no seeded row to isolate. Nothing to do.
            pass


@pytest.fixture
def api_client():
    """Unauthenticated DRF API client."""
    return APIClient()
