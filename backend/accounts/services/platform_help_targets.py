"""Closed target vocabulary shared by tours and Appi's navigation guides.

Routes are relative platform paths, never arbitrary URLs supplied by editors.
The frontend only resolves these keys to data-tour attributes on visible controls.
"""
TARGETS = {
    'welcome': {'context': 'general'},
    'projects': {'context': 'general', 'route': '/platform/projects'},
    'documents': {'context': 'general', 'route': '/platform/documents'},
    'collection-accounts': {'context': 'general', 'route': '/platform/collection-accounts'},
    'hosting': {'context': 'general', 'route': '/platform/payments'},
    'notifications': {'context': 'general', 'route': '/platform/notifications'},
    'profile': {'context': 'general', 'route': '/platform/profile'},
    'help': {'context': 'general'},
    'platform-appi-launcher': {'context': 'general', 'capability': 'chatbot'},
    **{key: {'context': 'project', 'route': '/platform/projects/{project_id}' + suffix}
       for key, suffix in [('project-summary', ''), ('project-delivery', '/delivery'),
                           ('project-ideas', '/ideas'), ('project-changes', '/changes'),
                           ('project-bugs', '/bugs'), ('project-resources', '/deliverables'),
                           ('project-access', '/access'), ('project-secure-links', '/secure-links')]},
    'voice-report': {'context': 'voice', 'capability': 'voice_reporting'},
}


def target_available(key, context, capabilities):
    target = TARGETS.get(key)
    return bool(target and target['context'] == context and (
        not target.get('capability') or capabilities.get(target['capability'], {}).get('available') is True))
