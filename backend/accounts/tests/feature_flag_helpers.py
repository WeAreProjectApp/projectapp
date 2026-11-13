"""Explicit canonical setup for tests of replaced AI/help availability controls."""
from accounts.models_feature_flags import ClientPlatformFeatureSettings, PlatformFeatureSettings


def set_global_flags(values):
    item, _ = PlatformFeatureSettings.objects.get_or_create(pk=1)
    item.values = {**item.values, **values}
    item.save()


def set_client_flags(user, values):
    item, _ = ClientPlatformFeatureSettings.objects.get_or_create(user=user)
    item.values = {**item.values, **values}
    item.save()
