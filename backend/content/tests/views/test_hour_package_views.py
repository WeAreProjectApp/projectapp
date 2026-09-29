"""Tests for the hour-package catalog admin CRUD endpoints."""
import pytest
from django.urls import reverse

from content.models import HourPackage, HourPackageSettings

pytestmark = pytest.mark.django_db


@pytest.fixture
def ext_package(db):
    return HourPackage.objects.create(
        nationality='EXT',
        name_es='Paquete Ágil MX',
        name_en='Agile Pack MX',
        hours=20,
        hourly_rate=45,
        discount_percent=0,
        order=1,
    )


class TestAdminHourPackageList:
    def test_returns_403_for_unauthenticated(self, api_client):
        response = api_client.get(reverse('list-admin-hour-packages'))
        assert response.status_code in (401, 403)

    def test_lists_migration_seeded_col_packages(self, admin_client):
        response = admin_client.get(reverse('list-admin-hour-packages'))
        assert response.status_code == 200
        col = [p for p in response.data if p['nationality'] == 'COL']
        assert len(col) == 4
        assert all(p['currency'] == 'COP' for p in col)
        # July 2026 ladder starts with a 1-hour package at 30.000 COP/h.
        assert col[0]['hours'] == 1
        assert float(col[0]['hourly_rate']) == 30000.0

    def test_filters_by_nationality(self, admin_client, ext_package):
        response = admin_client.get(
            reverse('list-admin-hour-packages'), {'nationality': 'EXT'}
        )
        assert response.status_code == 200
        ids = [p['id'] for p in response.data]
        assert ext_package.id in ids
        assert all(p['nationality'] == 'EXT' for p in response.data)
        assert all(p['currency'] == 'USD' for p in response.data)

    def test_rejects_invalid_nationality_filter(self, admin_client):
        response = admin_client.get(
            reverse('list-admin-hour-packages'), {'nationality': 'BRA'}
        )
        assert response.status_code == 400


class TestAdminHourPackageCreate:
    def test_returns_403_for_unauthenticated(self, api_client):
        response = api_client.post(reverse('create-hour-package'), {}, format='json')
        assert response.status_code in (401, 403)

    def test_creates_package_with_derived_currency(self, admin_client):
        payload = {
            'nationality': 'EXT',
            'name_es': 'Paquete Pro MX',
            'name_en': 'Pro Pack MX',
            'hours': 60,
            'hourly_rate': '40.00',
            'discount_percent': 10,
        }
        response = admin_client.post(
            reverse('create-hour-package'), payload, format='json'
        )
        assert response.status_code == 201
        assert response.data['currency'] == 'USD'
        assert HourPackage.objects.filter(
            nationality='EXT', name_es='Paquete Pro MX').count() == 1

    def test_rejects_zero_hours(self, admin_client):
        payload = {
            'nationality': 'COL', 'name_es': 'X', 'name_en': 'X',
            'hours': 0, 'hourly_rate': '90000',
        }
        response = admin_client.post(
            reverse('create-hour-package'), payload, format='json'
        )
        assert response.status_code == 400
        assert 'hours' in response.data

    def test_rejects_discount_above_100(self, admin_client):
        payload = {
            'nationality': 'COL', 'name_es': 'X', 'name_en': 'X',
            'hours': 10, 'hourly_rate': '90000', 'discount_percent': 150,
        }
        response = admin_client.post(
            reverse('create-hour-package'), payload, format='json'
        )
        assert response.status_code == 400
        assert 'discount_percent' in response.data

    def test_rejects_invalid_nationality(self, admin_client):
        payload = {
            'nationality': 'BRA', 'name_es': 'X', 'name_en': 'X',
            'hours': 10, 'hourly_rate': '90000',
        }
        response = admin_client.post(
            reverse('create-hour-package'), payload, format='json'
        )
        assert response.status_code == 400
        assert 'nationality' in response.data


class TestAdminHourPackageRetrieveUpdate:
    def test_returns_403_for_unauthenticated(self, api_client, ext_package):
        url = reverse('update-hour-package', args=[ext_package.id])
        response = api_client.patch(url, {}, format='json')
        assert response.status_code in (401, 403)

    def test_retrieves_detail(self, admin_client, ext_package):
        url = reverse('retrieve-admin-hour-package', args=[ext_package.id])
        response = admin_client.get(url)
        assert response.status_code == 200
        assert response.data['name_es'] == 'Paquete Ágil MX'
        assert response.data['currency'] == 'USD'

    def test_partial_update(self, admin_client, ext_package):
        url = reverse('update-hour-package', args=[ext_package.id])
        response = admin_client.patch(
            url, {'hourly_rate': '50.00', 'discount_percent': 5}, format='json'
        )
        assert response.status_code == 200
        ext_package.refresh_from_db()
        assert float(ext_package.hourly_rate) == 50.0
        assert ext_package.discount_percent == 5

    def test_update_returns_404_for_missing(self, admin_client):
        url = reverse('update-hour-package', args=[999999])
        response = admin_client.patch(url, {'hours': 5}, format='json')
        assert response.status_code == 404


class TestAdminHourPackageDelete:
    def test_returns_403_for_unauthenticated(self, api_client, ext_package):
        url = reverse('delete-hour-package', args=[ext_package.id])
        response = api_client.delete(url)
        assert response.status_code in (401, 403)

    def test_deletes_package(self, admin_client, ext_package):
        url = reverse('delete-hour-package', args=[ext_package.id])
        response = admin_client.delete(url)
        assert response.status_code == 204
        assert not HourPackage.objects.filter(pk=ext_package.id).exists()


class TestHourPackageSettings:
    def test_returns_403_for_unauthenticated(self, api_client):
        response = api_client.get(reverse('hour-package-settings'))
        assert response.status_code in (401, 403)

    def test_get_returns_table_default(self, admin_client):
        response = admin_client.get(reverse('hour-package-settings'))
        assert response.status_code == 200
        assert response.data['default_view_mode'] == 'table'

    def test_patch_updates_view_mode(self, admin_client):
        response = admin_client.patch(
            reverse('update-hour-package-settings'),
            {'default_view_mode': 'cards'}, format='json',
        )
        assert response.status_code == 200
        assert HourPackageSettings.load().default_view_mode == 'cards'

    def test_patch_rejects_unknown_mode(self, admin_client):
        response = admin_client.patch(
            reverse('update-hour-package-settings'),
            {'default_view_mode': 'carousel'}, format='json',
        )
        assert response.status_code == 400
        assert 'default_view_mode' in response.data

    def test_get_exposes_base_rates(self, admin_client):
        response = admin_client.get(reverse('hour-package-settings'))
        assert response.status_code == 200
        assert float(response.data['base_rate_col']) == 30000.0
        assert float(response.data['base_rate_ext']) == 18.0
        assert float(response.data['base_rate_usa']) == 30.0

    def test_patch_base_rate_propagates_to_catalog(self, admin_client):
        response = admin_client.patch(
            reverse('update-hour-package-settings'),
            {'base_rate_col': '35000'}, format='json',
        )
        assert response.status_code == 200
        assert response.data['updated_packages'] == {'COL': 4}
        rates = set(
            HourPackage.objects.filter(nationality='COL')
            .values_list('hourly_rate', flat=True)
        )
        assert {float(r) for r in rates} == {35000.0}

    def test_patch_unchanged_base_rate_skips_propagation(self, admin_client):
        pkg = HourPackage.objects.filter(nationality='COL').first()
        pkg.hourly_rate = 99999  # per-package exception must survive
        pkg.save()
        response = admin_client.patch(
            reverse('update-hour-package-settings'),
            {'base_rate_col': '30000'}, format='json',
        )
        assert response.status_code == 200
        assert response.data['updated_packages'] == {}
        pkg.refresh_from_db()
        assert float(pkg.hourly_rate) == 99999.0

    def test_patch_view_mode_only_does_not_touch_packages(self, admin_client):
        before = list(
            HourPackage.objects.order_by('id')
            .values_list('hourly_rate', 'updated_at')
        )
        response = admin_client.patch(
            reverse('update-hour-package-settings'),
            {'default_view_mode': 'compare'}, format='json',
        )
        assert response.status_code == 200
        assert response.data['updated_packages'] == {}
        after = list(
            HourPackage.objects.order_by('id')
            .values_list('hourly_rate', 'updated_at')
        )
        assert after == before

    def test_patch_rejects_zero_base_rate(self, admin_client):
        response = admin_client.patch(
            reverse('update-hour-package-settings'),
            {'base_rate_ext': '0'}, format='json',
        )
        assert response.status_code == 400
        assert 'base_rate_ext' in response.data

    def test_patch_rejects_negative_base_rate(self, admin_client):
        response = admin_client.patch(
            reverse('update-hour-package-settings'),
            {'base_rate_usa': '-5'}, format='json',
        )
        assert response.status_code == 400
        assert 'base_rate_usa' in response.data


class TestRestoreDefaultHourPackages:
    def test_returns_403_for_unauthenticated(self, api_client):
        response = api_client.post(
            reverse('restore-default-hour-packages'), {}, format='json'
        )
        assert response.status_code in (401, 403)

    def test_rejects_invalid_nationality(self, admin_client):
        response = admin_client.post(
            reverse('restore-default-hour-packages'),
            {'nationality': 'BRA'}, format='json',
        )
        assert response.status_code == 400

    def test_replaces_catalog_with_defaults(self, admin_client):
        HourPackage.objects.filter(nationality='COL').delete()
        custom = HourPackage.objects.create(
            nationality='COL', name_es='Custom', name_en='Custom',
            hours=7, hourly_rate=99999, discount_percent=1, order=1,
        )
        response = admin_client.post(
            reverse('restore-default-hour-packages'),
            {'nationality': 'COL'}, format='json',
        )
        assert response.status_code == 200
        assert not HourPackage.objects.filter(pk=custom.id).exists()
        col = HourPackage.objects.filter(nationality='COL').order_by('order')
        assert col.count() == 4
        assert col.first().hours == 1
        assert float(col.first().hourly_rate) == 30000.0
        # The response returns the fresh list for the store to swap in.
        assert len(response.data) == 4


class TestHourPackageProgramRebuild:
    """The public Partnership Program is prerendered with its monthly package."""

    @pytest.fixture
    def rebuild_calls(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            'content.views.hour_packages.schedule_rebuild_after_publish',
            lambda **kwargs: calls.append(kwargs),
        )
        return calls

    @pytest.fixture
    def program_package(self, db):
        return HourPackage.objects.get(nationality='COL', hours=60)

    def test_renaming_program_package_requests_rebuild(
        self, admin_client, program_package, rebuild_calls,
    ):
        """Fails if the prerendered program keeps the old monthly package name."""
        url = reverse('update-hour-package', args=[program_package.id])
        response = admin_client.patch(url, {'name_es': 'Paquete Pro Plus'}, format='json')

        assert response.status_code == 200
        assert response.data['name_es'] == 'Paquete Pro Plus'
        assert rebuild_calls == [{'reason': 'partnership-program'}]

    def test_moving_program_package_off_sixty_hours_requests_rebuild(
        self, admin_client, program_package, rebuild_calls,
    ):
        """Fails if a package leaving the program only triggers on its new values."""
        url = reverse('update-hour-package', args=[program_package.id])
        response = admin_client.patch(url, {'hours': 50}, format='json')

        assert response.status_code == 200
        assert response.data['hours'] == 50
        assert rebuild_calls == [{'reason': 'partnership-program'}]

    def test_editing_unlisted_package_skips_rebuild(
        self, admin_client, ext_package, rebuild_calls,
    ):
        """Fails if a package the program never shows forces a regeneration."""
        url = reverse('update-hour-package', args=[ext_package.id])
        response = admin_client.patch(url, {'hourly_rate': '50.00'}, format='json')

        assert response.status_code == 200
        assert float(response.data['hourly_rate']) == 50.0
        assert rebuild_calls == []

    def test_deleting_program_package_requests_rebuild(
        self, admin_client, program_package, rebuild_calls,
    ):
        url = reverse('delete-hour-package', args=[program_package.id])
        response = admin_client.delete(url)

        assert response.status_code == 204
        assert not HourPackage.objects.filter(pk=program_package.id).exists()
        assert rebuild_calls == [{'reason': 'partnership-program'}]

    def test_creating_program_package_requests_rebuild(self, admin_client, rebuild_calls):
        payload = {
            'nationality': 'COL', 'name_es': 'Paquete Socio', 'name_en': 'Partner Pack',
            'hours': 60, 'hourly_rate': '30000', 'order': 0,
        }
        response = admin_client.post(reverse('create-hour-package'), payload, format='json')

        assert response.status_code == 201
        assert response.data['name_es'] == 'Paquete Socio'
        assert rebuild_calls == [{'reason': 'partnership-program'}]

    def test_restoring_colombian_defaults_requests_rebuild(self, admin_client, rebuild_calls):
        response = admin_client.post(
            reverse('restore-default-hour-packages'), {'nationality': 'COL'}, format='json',
        )

        assert response.status_code == 200
        assert [row['hours'] for row in response.data] == [1, 20, 60, 180]
        assert rebuild_calls == [{'reason': 'partnership-program'}]

    def test_restoring_foreign_defaults_skips_rebuild(self, admin_client, rebuild_calls):
        response = admin_client.post(
            reverse('restore-default-hour-packages'), {'nationality': 'EXT'}, format='json',
        )

        assert response.status_code == 200
        assert len(response.data) == 4
        assert rebuild_calls == []
