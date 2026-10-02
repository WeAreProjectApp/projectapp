"""Who a cuenta de cobro is issued to, and under which project.

Regression suite for the defect where `company_name` — the field operators
use for the brand — decided the legal name on the document, the numbering
code and the panel column all at once. Production issued PA-MIMITTOS-001 to
"MIMITTOS · C.C. 1049654583": a brand beside a personal cédula, with the
actual debtor's name unused in `contact_name`.
"""
import pytest
from accounts.models import Project, UserProfile
from django.contrib.auth import get_user_model

from content.services.collection_account_create_service import (
    client_legal_identity,
    customer_snapshot_defaults,
    legal_name_for,
)
from content.services.collection_account_numbering import derive_billing_code
from content.services.collection_account_service import _fill_customer_from_user
from content.models.document_collection_account import DocumentCollectionAccount

User = get_user_model()
pytestmark = pytest.mark.django_db


def make_profile(*, first='', last='', company='', nit='', cedula='',
                 address='', email='cliente@example.com'):
    user = User.objects.create_user(
        username=email, email=email, password='pass12345',
        first_name=first, last_name=last,
    )
    return UserProfile.objects.create(
        user=user, company_name=company, nit=nit, cedula=cedula,
        address=address,
    )


class TestLegalIdentityFollowsTheIdentification:
    def test_natural_person_is_named_over_the_brand_in_company_name(self):
        """The production case: cédula client whose company_name is a brand."""
        profile = make_profile(
            first='Daniel', last='Felipe Corredor Castiblanco',
            company='MIMITTOS', cedula='1049654583',
        )

        name, identification, id_type, contact = client_legal_identity(profile)

        assert name == 'Daniel Felipe Corredor Castiblanco'
        assert (id_type, identification) == ('CC', '1049654583')
        assert contact == 'Daniel Felipe Corredor Castiblanco'

    def test_company_with_nit_is_still_named_by_its_company_name(self):
        """The rule follows the identification — it does not just prefer people."""
        profile = make_profile(
            first='Jesús', last='Murillo',
            company='Multiproyectos S.A.S.', nit='900123456-7',
        )

        name, identification, id_type, _ = client_legal_identity(profile)

        assert name == 'Multiproyectos S.A.S.'
        assert (id_type, identification) == ('NIT', '900123456-7')

    def test_person_without_any_identification_is_named_by_their_name(self):
        profile = make_profile(first='Frida', last='Galindo', company='Marca X')

        name, identification, id_type, _ = client_legal_identity(profile)

        assert name == 'Frida Galindo'
        assert (id_type, identification) == ('', '')

    def test_company_name_still_names_a_client_with_no_person_name(self):
        profile = make_profile(company='Taptag', nit='901222333-1')

        assert legal_name_for(profile) == 'Taptag'

    def test_falls_back_to_the_email_when_nothing_else_is_known(self):
        profile = make_profile(email='sinnombre@example.com')

        assert legal_name_for(profile) == ''
        assert client_legal_identity(profile)[0] == 'sinnombre@example.com'


class TestSnapshotPrefill:
    def test_snapshot_name_is_the_legal_holder_not_the_brand(self):
        profile = make_profile(
            first='Daniel', last='Corredor', company='MIMITTOS',
            cedula='1049654583',
        )

        snapshot = customer_snapshot_defaults(profile)

        assert snapshot['name'] == 'Daniel Corredor'
        assert snapshot['identification_type'] == 'CC'
        # The person stays reachable as the contact either way; what changed
        # is which field the DOCUMENT prints as the party being charged.
        assert snapshot['contact_name'] == 'Daniel Corredor'

    def test_snapshot_uses_the_complete_client_billing_identity(self):
        """Fails if a new cuenta de cobro drops identity or address from its client."""
        profile = make_profile(
            first='Laura', last='Ramírez', cedula='1049654583',
            email='laura@example.com', address='Carrera 7 # 72-41, Bogotá',
        )

        snapshot = customer_snapshot_defaults(profile)

        assert snapshot['identification_type'] == 'CC'
        assert snapshot['identification'] == '1049654583'
        assert snapshot['email'] == 'laura@example.com'
        assert snapshot['address'] == 'Carrera 7 # 72-41, Bogotá'

    def test_snapshot_keeps_nit_over_cedula_when_the_profile_has_both(self):
        """Fails if a business account changes from NIT to C.C. in the billing prefill."""
        profile = make_profile(
            company='Servicios Ejemplo S.A.S.', nit='901234567-1',
            cedula='1049654583', address='Calle 80 # 10-20, Bogotá',
        )

        snapshot = customer_snapshot_defaults(profile)

        assert snapshot['identification_type'] == 'NIT'
        assert snapshot['identification'] == '901234567-1'
        assert snapshot['address'] == 'Calle 80 # 10-20, Bogotá'


class TestPlatformIssueSnapshot:
    def test_platform_issue_uses_the_canonical_customer_snapshot(self):
        """Fails if platform-issued documents omit a client's address or legal identity."""
        profile = make_profile(
            first='Laura', last='Ramírez', cedula='1049654583',
            email='laura@example.com', address='Carrera 7 # 72-41, Bogotá',
        )
        extension = DocumentCollectionAccount()

        _fill_customer_from_user(extension, profile.user)

        assert extension.customer_name == 'Laura Ramírez'
        assert extension.customer_email == 'laura@example.com'
        assert extension.customer_identification == '1049654583'
        assert extension.customer_identification_type == 'CC'
        assert extension.customer_contact_name == 'Laura Ramírez'
        assert extension.customer_address == 'Carrera 7 # 72-41, Bogotá'


class TestBillingCodeDerivation:
    def test_code_derives_from_the_person_not_the_brand(self):
        profile = make_profile(
            first='Daniel', last='Corredor', company='MIMITTOS',
            cedula='1049654583',
        )

        assert derive_billing_code(profile) == 'DANIELCO'

    def test_code_still_derives_from_the_company_when_it_has_a_nit(self):
        profile = make_profile(
            first='Jesús', last='Murillo', company='Multiproyectos',
            nit='900123456-7',
        )

        assert derive_billing_code(profile) == 'MULTIPRO'

    def test_an_already_stored_code_is_never_re_derived(self):
        """PA-MIMITTOS-001 is already issued; its series must not move."""
        from content.services.collection_account_numbering import (
            ensure_billing_code,
        )

        profile = make_profile(
            first='Daniel', last='Corredor', company='MIMITTOS',
            cedula='1049654583',
        )
        profile.billing_code = 'MIMITTOS'
        profile.save(update_fields=['billing_code'])

        assert ensure_billing_code(profile) == 'MIMITTOS'
        profile.refresh_from_db()
        assert profile.billing_code == 'MIMITTOS'

    def test_a_numeric_base_is_prefixed_so_it_cannot_look_like_a_year(self):
        """PA-123-001 would be indistinguishable from the legacy
        PA-{year}-{NNNN} series, so a digits-only code gets a C prefix."""
        profile = make_profile(email='123@example.com')

        assert derive_billing_code(profile) == 'C123'

    def test_code_falls_back_to_c_pk_when_there_is_nothing_to_derive_from(self):
        profile = make_profile(email='.-_@example.com')

        assert derive_billing_code(profile) == f'C{profile.pk}'


class TestProjectOwnership:
    def test_a_project_knows_the_same_client_the_profile_does(self):
        """The join the coherence check relies on: Project.client is a User,
        the accounting records' client is a UserProfile."""
        profile = make_profile(first='Daniel', last='Corredor', cedula='1049')
        project = Project.objects.create(name='MIMITTOS', client=profile.user)

        assert project.client_id == profile.user_id
