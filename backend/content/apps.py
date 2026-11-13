from django.apps import AppConfig


class ContentConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'content'

    def ready(self):
        from projectapp.build_identity import capture_backend_version
        capture_backend_version()
        import projectapp.checks  # noqa: F401 — deploy-time CAPTCHA validation
        import projectapp.tasks  # noqa: F401 — Huey periodic task discovery
        import content.signals  # noqa: F401
        import content.services.video_resource_signals  # noqa: F401
        import content.services.entity_history_signals  # noqa: F401
