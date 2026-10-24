"""Admin API tests for the size-based requirement package catalog."""
import pytest
from django.urls import reverse

from content.models import HourPackage, HourPackageSettings

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def requirement_catalog():
    from content.services.hour_package_service import restore_default_packages
    restore_default_packages('COL')
    restore_default_packages('EXT')
    restore_default_packages('USA')


@pytest.fixture
def ext_package():
    HourPackage.objects.filter(nationality='EXT', pricing_model='requirements').delete()
    return HourPackage.objects.create(
        nationality='EXT', pricing_model='requirements',
        name_es='Paquete Ágil MX', name_en='Agile Pack MX',
        xs_count=30, s_count=0, m_count=0, validity_months=12,
        discount_percent=10, order=1,
    )


def _payload(**changes):
    return {
        'nationality': 'EXT', 'name_es': 'Paquete Pro MX', 'name_en': 'Pro Pack MX',
        'xs_count': 30, 's_count': 20, 'm_count': 0,
        'validity_months': 12, 'discount_percent': 15, **changes,
    }


class TestRequirementPackageCatalog:
    def test_list_requires_admin(self, api_client):
        """Fails if the editable commercial catalog becomes public."""
        assert api_client.get(reverse('list-admin-hour-packages')).status_code in (401, 403)

    @pytest.mark.parametrize(
        ('method', 'url_name', 'kwargs', 'payload'),
        [
            ('post', 'create-hour-package', None, _payload()),
            ('get', 'retrieve-admin-hour-package', {'package_id': 999999}, {}),
            ('patch', 'update-hour-package', {'package_id': 999999}, {'xs_count': 30}),
            ('delete', 'delete-hour-package', {'package_id': 999999}, {}),
            ('get', 'hour-package-settings', None, {}),
            ('patch', 'update-hour-package-settings', None, {'alliance_xs_count': 8}),
            ('post', 'restore-default-hour-packages', None, {'nationality': 'COL'}),
        ],
    )
    def test_each_catalog_management_endpoint_requires_admin(self, api_client, method, url_name, kwargs, payload):
        """Fails if one independently protected catalog endpoint becomes writable without staff access."""
        response = getattr(api_client, method)(reverse(url_name, kwargs=kwargs), payload, format='json')

        assert response.status_code in (401, 403)
        assert not HourPackage.objects.filter(name_es='Paquete Pro MX').exists()

    def test_list_returns_only_three_active_requirement_tiers(self, admin_client):
        """Fails if historical hour rows reappear in the active size catalog."""
        HourPackage.objects.create(
            nationality='COL', pricing_model='hours', name_es='Histórico', name_en='Historical',
            hours=60, hourly_rate=30000, is_active=False,
        )

        response = admin_client.get(reverse('list-admin-hour-packages'), {'nationality': 'COL'})

        assert response.status_code == 200
        assert [(row['xs_count'], row['s_count'], row['m_count']) for row in response.data] == [
            (30, 0, 0), (30, 20, 0), (30, 20, 10),
        ]
        assert all(row['pricing_model'] == 'requirements' for row in response.data)

    def test_list_filters_requirement_catalog_by_market(self, admin_client, ext_package):
        """Fails if the market filter leaks a package into another commercial market."""
        response = admin_client.get(reverse('list-admin-hour-packages'), {'nationality': 'EXT'})

        assert response.status_code == 200
        assert [row['id'] for row in response.data] == [ext_package.pk]
        assert response.data[0]['currency'] == 'USD'

    def test_list_rejects_unknown_market_filter(self, admin_client):
        """Fails if a typo can bypass the market catalog boundary."""
        response = admin_client.get(reverse('list-admin-hour-packages'), {'nationality': 'BRA'})

        assert response.status_code == 400
        assert 'nationality' in response.data

    def test_create_persists_size_counts_and_derived_currency(self, admin_client):
        """Fails if a new offer loses its size composition or market currency."""
        response = admin_client.post(reverse('create-hour-package'), _payload(), format='json')

        assert response.status_code == 201
        assert (response.data['xs_count'], response.data['s_count'], response.data['m_count']) == (30, 20, 0)
        assert response.data['currency'] == 'USD'
        assert HourPackage.objects.get(pk=response.data['id']).pricing_model == 'requirements'

    @pytest.mark.parametrize(
        ('payload', 'field'),
        [
            (_payload(xs_count=0, s_count=0, m_count=0), 'non_field_errors'),
            (_payload(validity_months=0), 'validity_months'),
            (_payload(discount_percent=100), 'discount_percent'),
        ],
    )
    def test_create_rejects_invalid_requirement_commitment(self, admin_client, payload, field):
        """Fails if the admin API accepts an unusable commercial commitment."""
        response = admin_client.post(reverse('create-hour-package'), payload, format='json')

        assert response.status_code == 400
        assert field in response.data
        assert not HourPackage.objects.filter(name_es='Paquete Pro MX').exists()

    def test_legacy_package_is_read_only_and_cannot_be_deleted_through_active_catalog(self, admin_client):
        """Fails if historical hour commitments can be modified or erased as live packages."""
        legacy = HourPackage.objects.create(
            nationality='COL', pricing_model='hours', name_es='Histórico', name_en='Historical',
            hours=60, hourly_rate=30000, is_active=False,
        )

        update = admin_client.patch(reverse('update-hour-package', args=[legacy.pk]), {'xs_count': 30}, format='json')
        delete = admin_client.delete(reverse('delete-hour-package', args=[legacy.pk]))

        assert update.status_code == 400
        assert delete.status_code == 404
        assert HourPackage.objects.filter(pk=legacy.pk).exists()

    def test_update_changes_requirement_composition(self, admin_client, ext_package):
        """Fails if a saved package ignores its edited S allowance."""
        response = admin_client.patch(
            reverse('update-hour-package', args=[ext_package.pk]), {'s_count': 20}, format='json',
        )

        assert response.status_code == 200
        ext_package.refresh_from_db()
        assert ext_package.s_count == 20


class TestRequirementPackageSettings:
    def test_settings_returns_and_updates_the_selected_view_mode(self, admin_client):
        """Fails if the panel loses its persisted catalog display preference."""
        current = admin_client.get(reverse('hour-package-settings'))
        updated = admin_client.patch(
            reverse('update-hour-package-settings'), {'default_view_mode': 'cards'}, format='json',
        )

        assert current.data['default_view_mode'] == 'table'
        assert updated.status_code == 200
        assert HourPackageSettings.load().default_view_mode == 'cards'

    def test_settings_reject_unknown_view_mode(self, admin_client):
        """Fails if the persisted panel preference accepts a layout the UI cannot render."""
        response = admin_client.patch(
            reverse('update-hour-package-settings'), {'default_view_mode': 'carousel'}, format='json',
        )

        assert response.status_code == 400
        assert 'default_view_mode' in response.data
    def test_settings_reject_empty_alliance_allowance(self, admin_client):
        """Fails if the public five-year benefit can be configured with no monthly capacity."""
        response = admin_client.patch(
            reverse('update-hour-package-settings'),
            {'alliance_xs_count': 0, 'alliance_s_count': 0, 'alliance_m_count': 0}, format='json',
        )

        assert response.status_code == 400
        assert 'non_field_errors' in response.data

    def test_settings_change_schedules_public_program_rebuild(self, admin_client, monkeypatch):
        """Fails if changing the public allowance leaves the prerendered program stale."""
        calls = []
        monkeypatch.setattr(
            'content.views.hour_packages.schedule_rebuild_after_publish',
            lambda **kwargs: calls.append(kwargs),
        )

        response = admin_client.patch(
            reverse('update-hour-package-settings'), {'alliance_xs_count': 8}, format='json',
        )

        assert response.status_code == 200
        assert HourPackageSettings.load().alliance_xs_count == 8
        assert calls == [{'reason': 'partnership-program'}]


class TestRestoreRequirementPackageDefaults:
    def test_restore_with_missing_usd_rate_keeps_existing_catalog(self, admin_client):
        """Fails if a rejected foreign restore deletes its current requirement tiers first."""
        before = list(HourPackage.objects.filter(
            nationality='EXT', pricing_model='requirements',
        ).values_list('pk', flat=True))
        from content.models import AccountingSettings
        accounting = AccountingSettings.load()
        accounting.usd_exchange_rate = 0
        accounting.save(update_fields=['usd_exchange_rate'])

        response = admin_client.post(
            reverse('restore-default-hour-packages'), {'nationality': 'EXT'}, format='json',
        )

        assert response.status_code == 400
        assert list(HourPackage.objects.filter(
            nationality='EXT', pricing_model='requirements',
        ).values_list('pk', flat=True)) == before

    def test_restore_rejects_unknown_market(self, admin_client):
        """Fails if default restoration can target a non-existent commercial market."""
        response = admin_client.post(
            reverse('restore-default-hour-packages'), {'nationality': 'BRA'}, format='json',
        )

        assert response.status_code == 400
        assert 'nationality' in response.data

    def test_restore_replaces_only_requirement_catalog_with_three_default_tiers(self, admin_client):
        """Fails if restoring defaults deletes history or recreates hourly offers."""
        legacy = HourPackage.objects.create(
            nationality='COL', pricing_model='hours', name_es='Histórico', name_en='Historical',
            hours=60, hourly_rate=30000, is_active=False,
        )
        HourPackage.objects.filter(nationality='COL', pricing_model='requirements').delete()

        response = admin_client.post(
            reverse('restore-default-hour-packages'), {'nationality': 'COL'}, format='json',
        )

        assert response.status_code == 200
        assert len(response.data) == 3
        assert [row['xs_count'] for row in response.data] == [30, 30, 30]
        assert HourPackage.objects.filter(pk=legacy.pk).exists()
