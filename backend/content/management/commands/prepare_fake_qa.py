"""Prepare or verify one QA profile in a reserved, isolated DevQA copy."""

import fcntl
import json
import os
import re
import secrets
import stat
import subprocess
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from content.fake_data import DEFAULT_COUNT, add_seed_arguments, ensure_fake_data_allowed, seed_context
from content.fake_data_files import fake_data_transaction
from content.fake_qa_profiles import PROFILE_ACTORS, profile_actors, profile_baseline, seed_profile
from content.management.commands.create_fake_data import Command as BaseSeedCommand
from content.models import ExpenseRecord, HostingRecord, IncomeRecord


SETTINGS_MODULE = 'projectapp.settings_fake_data'
RECIPE_VERSION = 1
MANIFEST_NAME = 'qa-manifest.json'
FILE_MAIL_BACKEND = 'django.core.mail.backends.filebased.EmailBackend'


def _configured_copy(expected_sha):
    ensure_fake_data_allowed('prepare_fake_qa')
    if settings.SETTINGS_MODULE != SETTINGS_MODULE:
        raise CommandError(f'Usa --settings={SETTINGS_MODULE} en la copia reservada.')
    if not re.fullmatch(r'[0-9a-f]{40}', expected_sha):
        raise CommandError('--expected-sha debe ser un SHA completo.')

    root = Path(settings.FAKE_DATA_ROOT)
    source = Path(settings.BASE_DIR).resolve().parent
    if os.path.lexists(source / 'backend' / '.env'):
        raise CommandError('La copia QA debe tener una configuración aislada sin backend/.env.')
    for directory in (root, root / 'private'):
        if not directory.is_dir() or directory.is_symlink():
            raise CommandError('Falta el directorio privado de la copia QA.')
        info = directory.stat()
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise CommandError('La raíz QA y su directorio private deben pertenecer a DevQA y tener modo 0700.')

    database = settings.DATABASES.get('default', {})
    db_path = root / 'db.sqlite3'
    if (set(settings.DATABASES) != {'default'} or database.get('ENGINE') != 'django.db.backends.sqlite3'
            or Path(database.get('NAME', '')) != db_path or not db_path.is_file() or db_path.is_symlink()):
        raise CommandError('La copia requiere su propia base SQLite con esquema preparado.')
    mailer = settings.MAILERS['default']
    mail_path = root / 'mail'
    if mailer['BACKEND'] != FILE_MAIL_BACKEND or Path(mailer['OPTIONS']['file_path']).resolve() != mail_path:
        raise CommandError('La copia debe capturar correo dentro de su propia raíz.')
    storage_locations = [settings.STATIC_ROOT, *(
        settings.STORAGES[alias]['OPTIONS']['location'] for alias in ('default', 'private', 'dbbackup')
    )]
    if any(root not in Path(location).resolve().parents for location in storage_locations):
        raise CommandError('El almacenamiento de QA debe pertenecer a su propia raíz.')
    if settings.RECAPTCHA_ENABLED:
        raise CommandError('El login local requiere RECAPTCHA_ENABLED=false en la copia QA.')

    def git(*args):
        return subprocess.check_output(
            ['git', '-C', str(source), *args], text=True, stderr=subprocess.DEVNULL,
        ).strip()

    try:
        if Path(git('rev-parse', '--show-toplevel')).resolve() != source:
            raise CommandError('DevQA requiere una copia Git propia del proyecto.')
        if git('rev-parse', 'HEAD') != expected_sha or git('status', '--porcelain', '--untracked-files=no'):
            raise CommandError('El código de la copia difiere de --expected-sha.')
    except (OSError, subprocess.CalledProcessError):
        raise CommandError('No se pudo acreditar el SHA de la copia Git de DevQA.') from None

    db_info = db_path.stat()
    return root, {
        'source': str(source), 'root': str(root), 'database': str(db_path),
        'database_device': db_info.st_dev, 'database_inode': db_info.st_ino,
    }


@contextmanager
def _copy_lock(root):
    fd = os.open(root / '.prepare-fake-qa.lock', os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise CommandError('Otra preparación está usando la copia QA.') from None
        yield
    finally:
        os.close(fd)


def _read_private_json(path):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, encoding='utf-8') as source:
            info = os.fstat(source.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) != 0o600):
                raise ValueError
            data = json.load(source)
            if not isinstance(data, dict):
                raise ValueError
            return data
    except (OSError, ValueError):
        raise CommandError(f'Falta un archivo privado válido para {path.name}.') from None


def _install_credentials(path, actors):
    passwords = {email: secrets.token_urlsafe(32) for email in actors}
    # Exclusive file creation keeps any existing access material intact.
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        raise CommandError('Ya existe un archivo de acceso QA. Conserva la copia para revisión.') from None
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as output:
            json.dump(passwords, output)
        for email, actor in actors.items():
            actor.set_password(passwords[email])
            actor.save(update_fields=['password'])
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _validate_credentials(path, actors):
    passwords = _read_private_json(path)
    for email, actor in actors.items():
        password = passwords.get(email)
        if not isinstance(password, str) or not check_password(password, actor.password):
            raise CommandError(f'El actor {email} no tiene acceso local utilizable.')


def _write_manifest(path, payload):
    with NamedTemporaryFile(mode='w', dir=path.parent, encoding='utf-8', delete=False) as output:
        temporary = Path(output.name)
        try:
            json.dump(payload, output, ensure_ascii=False, indent=2)
            output.write('\n')
            output.flush()
            os.fsync(output.fileno())
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def _verify_empty_copy():
    populated_model = BaseSeedCommand._first_populated_business_model()
    if populated_model:
        raise CommandError(f'La base contiene {populated_model} sin un manifiesto compatible.')
    for model in (get_user_model(), IncomeRecord, ExpenseRecord, HostingRecord):
        if model.objects.exists():
            raise CommandError(f'La base contiene {model._meta.label} sin un manifiesto compatible.')


def _generate(profile, context, count, credentials, mail_path):
    _verify_empty_copy()
    installed = False
    try:
        with fake_data_transaction():
            call_command('create_fake_data', count=count, seed=context.seed, anchor_date=context.anchor_date)
            seed_profile(profile, context)
            actors = profile_actors(profile)
            _install_credentials(credentials, actors)
            installed = True
            _validate_credentials(credentials, actors)
            return profile_baseline(profile, actors, context, mail_path)
    except BaseException:
        if installed:
            credentials.unlink(missing_ok=True)
        raise


class Command(BaseCommand):
    help = 'Prepare or verify a role-based corpus for one disposable ProjectApp DevQA copy.'

    def add_arguments(self, parser):
        add_seed_arguments(parser, count_default=DEFAULT_COUNT)
        parser.add_argument('--profile', choices=PROFILE_ACTORS, required=True)
        parser.add_argument('--expected-sha', required=True)

    def handle(self, *args, **options):
        root, copy = _configured_copy(options['expected_sha'])
        profile = options['profile']
        context = seed_context(options, f'qa-profile:{profile}')
        count = options['count']
        if options['anchor_date'] is None or count < 1:
            raise CommandError('Indica una --anchor-date explícita y un --count positivo.')

        manifest_path = root / MANIFEST_NAME
        credentials = root / 'private' / f'{profile}-access.json'
        recipe = {
            'profile': profile, 'sha': options['expected_sha'], 'settings': SETTINGS_MODULE,
            'count': count, 'seed': context.seed, 'anchor_date': context.anchor_date.isoformat(),
        }

        with _copy_lock(root):
            if os.path.lexists(manifest_path):
                previous = _read_private_json(manifest_path)
                for key, expected in (('schema_version', RECIPE_VERSION), ('recipe', recipe), ('copy', copy)):
                    if previous.get(key) != expected:
                        raise CommandError(f'El manifiesto no coincide en {key}. Conserva el corpus existente.')
                actors = profile_actors(profile)
                _validate_credentials(credentials, actors)
                baseline = profile_baseline(profile, actors, context, root / 'mail')
                original = previous.get('baseline')
                if not isinstance(original, dict):
                    raise CommandError('El manifiesto carece de línea base.')
                changed = sorted(key for key in baseline.keys() | original.keys() if baseline.get(key) != original.get(key))
                if changed:
                    raise CommandError(f'La línea base cambió en {", ".join(changed)}. Usa otra copia aislada autorizada.')
                mode = 'reutilizado'
            else:
                if os.path.lexists(credentials):
                    raise CommandError('Existe acceso QA sin manifiesto. Conserva la copia para revisión.')
                baseline = _generate(profile, context, count, credentials, root / 'mail')
                mode = 'generado'

            _write_manifest(manifest_path, {
                'schema_version': RECIPE_VERSION, 'mode': mode,
                'recipe': recipe, 'copy': copy, 'baseline': baseline,
            })

        self.stdout.write(f'Corpus {profile} {mode}. Manifiesto: {manifest_path}')
