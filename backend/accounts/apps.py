from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    verbose_name = 'Platform Accounts'

    def ready(self):
        import accounts.signals  # noqa: F401
        import accounts.project_client_access_hooks  # noqa: F401
