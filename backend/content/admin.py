import logging

from django import forms
from django.contrib import admin, messages
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin, GroupAdmin
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from accounts.services.impersonation import (
    ImpersonationError,
    build_impersonation_redirect_url,
    create_exchange_code,
    impersonate,
)
from content.forms.admin_login import CaptchaAdminAuthenticationForm
from .models import (
    Contact, PortfolioWork,
    BusinessProposal, ProposalSection,
    BlogPost, ProposalViewEvent, ProposalSectionView, ProposalChangeLog,
    ProposalDefaultConfig, EmailTemplateConfig,
    Document,
    DocumentType,
    DocumentFolder,
    DocumentItem,
    DocumentCollectionAccount,
    DocumentTag,
    DocumentNumberSequence,
    DocumentPaymentMethod,
    IssuerProfile,
    CompanySettings,
    ProposalDocument,
    ContractTemplate,
    ConfidentialityTemplate,
    ProposalAlert,
    ProposalProjectStage,
    ProposalShareLink,
    WebAppDiagnostic,
    DiagnosticSection,
    EmailLog,
    EmailCopyRecipient,
    CommunicationAttachment,
    CommunicationMessage,
    CommunicationMessageDateCorrection,
    CommunicationThread,
    LinkedInToken,
    LinkedInPost,
    Task,
    FinancingAgreement,
    FinancingAgreementEvent,
    FinancingAgreementNumberSequence,
    FinancingAgreementTemplate,
    FinancingPolicyRevision,
)

logger = logging.getLogger(__name__)


class PortfolioWorkAdmin(admin.ModelAdmin):
    """
    Custom admin configuration for the PortfolioWork model.
    """
    list_display = ('title_en', 'title_es', 'slug', 'is_published', 'order', 'published_at', 'created_at')
    list_filter = ('is_published',)
    search_fields = ('title_es', 'title_en', 'excerpt_es', 'excerpt_en')
    prepopulated_fields = {'slug': ('title_es',)}
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Español', {
            'fields': ('title_es', 'excerpt_es', 'content_json_es'),
        }),
        ('English', {
            'fields': ('title_en', 'excerpt_en', 'content_json_en'),
        }),
        (None, {
            'fields': ('slug', 'cover_image', 'cover_image_url', 'project_url', 'category_title_es', 'category_title_en', 'order'),
        }),
        ('SEO', {
            'fields': ('meta_title_es', 'meta_title_en', 'meta_description_es', 'meta_description_en', 'meta_keywords_es', 'meta_keywords_en'),
            'classes': ('collapse',),
        }),
        ('Publishing', {
            'fields': ('is_published', 'published_at'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )

class ContactAdmin(admin.ModelAdmin):
    """
    Custom admin configuration for the Contact model.
    Display specific fields of the Contact model.
    """
    list_display = ('email', 'subject', 'message')

class BlogPostAdmin(admin.ModelAdmin):
    """
    Custom admin configuration for the BlogPost model.
    """
    list_display = ('title_es', 'title_en', 'slug', 'category', 'is_featured', 'is_published', 'published_at', 'created_at')
    list_filter = ('is_published', 'is_featured', 'category')
    search_fields = ('title_es', 'title_en', 'excerpt_es', 'excerpt_en', 'content_es', 'content_en')
    prepopulated_fields = {'slug': ('title_es',)}
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Español', {
            'fields': ('title_es', 'excerpt_es', 'content_es', 'content_json_es'),
        }),
        ('English', {
            'fields': ('title_en', 'excerpt_en', 'content_en', 'content_json_en'),
        }),
        (None, {
            'fields': ('slug', 'cover_image', 'cover_image_url', 'cover_image_credit', 'cover_image_credit_url', 'category', 'read_time_minutes', 'is_featured', 'author'),
        }),
        ('SEO', {
            'fields': ('meta_title_es', 'meta_title_en', 'meta_description_es', 'meta_description_en', 'meta_keywords_es', 'meta_keywords_en'),
            'classes': ('collapse',),
        }),
        ('Sources', {
            'fields': ('sources',),
        }),
        ('Publishing', {
            'fields': ('is_published', 'published_at'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )


class ProposalSectionInline(admin.TabularInline):
    """
    Inline admin for proposal sections within BusinessProposalAdmin.
    Content JSON is edited in the Nuxt admin frontend, not here.
    """
    model = ProposalSection
    extra = 0
    fields = ('section_type', 'title', 'order', 'is_enabled', 'is_wide_panel')
    ordering = ('order',)


class BusinessProposalAdmin(admin.ModelAdmin):
    """
    Custom admin configuration for the BusinessProposal model.
    """
    list_display = (
        'title', 'client_name', 'status', 'is_active', 'total_investment',
        'currency', 'expires_at', 'view_count', 'created_at',
    )
    list_filter = ('status', 'currency', 'is_active')
    search_fields = ('title', 'client_name', 'client_email')
    readonly_fields = (
        'uuid', 'view_count', 'first_viewed_at', 'sent_at',
        'responded_at', 'revisit_alert_sent_at',
        'reminder_sent_at', 'created_at', 'updated_at',
    )
    inlines = [ProposalSectionInline]
    fieldsets = (
        ('Identity', {
            'fields': ('uuid', 'title', 'client_name', 'client_email', 'slug', 'deliverable'),
        }),
        ('Financial', {
            'fields': ('total_investment', 'currency'),
        }),
        ('Status & Lifecycle', {
            'fields': (
                'status', 'is_active', 'expires_at',
                'reminder_days', 'urgency_reminder_days',
                'discount_percent', 'reminder_sent_at', 'urgency_email_sent_at',
            ),
        }),
        ('Tracking', {
            'fields': (
                'view_count', 'first_viewed_at', 'sent_at',
                'responded_at', 'revisit_alert_sent_at',
            ),
        }),
        ('Email Template Metadata', {
            'description': (
                'Datos opcionales que se renderizan en los correos al cliente. '
                'Si quedan vacíos, los bloques opcionales se omiten y la firma usa el default.'
            ),
            'fields': ('email_intro', 'email_features', 'email_method_phases', 'email_signed_by'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )


class CompanySettingsForm(forms.ModelForm):
    """Require one of the contractor's two identification documents.

    The rule lives on the form and not on the model: ``CompanySettings.load()``
    creates the singleton through ``get_or_create``, which would start failing
    if an empty instance stopped being valid.
    """

    class Meta:
        model = CompanySettings
        fields = '__all__'

    def clean(self):
        cleaned = super().clean()
        if not (cleaned.get('contractor_nit') or '').strip() and not (
            cleaned.get('contractor_cedula') or ''
        ).strip():
            raise forms.ValidationError(
                {'contractor_nit': 'Indica el NIT o la cédula del contratista (al menos uno).'}
            )
        return cleaned


class CompanySettingsAdmin(admin.ModelAdmin):
    form = CompanySettingsForm


class ProposalDefaultConfigAdmin(admin.ModelAdmin):
    """
    Admin configuration for the ProposalDefaultConfig model.
    """
    list_display = ('language', 'updated_at', 'created_at')
    list_filter = ('language',)
    readonly_fields = ('created_at', 'updated_at')


class EmailTemplateConfigAdmin(admin.ModelAdmin):
    """
    Admin configuration for the EmailTemplateConfig model.
    """
    list_display = ('template_key', 'is_active', 'updated_at', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('template_key',)
    readonly_fields = ('created_at', 'updated_at')


class DocumentAdmin(admin.ModelAdmin):
    """
    Custom admin configuration for the Document model.
    """
    list_display = (
        'title', 'slug', 'status', 'language', 'cover_type',
        'include_portada', 'include_subportada', 'include_contraportada',
        'client_name', 'created_at',
    )
    list_filter = ('status', 'language', 'cover_type', 'include_portada', 'include_subportada', 'include_contraportada')
    search_fields = ('title', 'client_name')
    readonly_fields = (
        'uuid', 'created_at', 'updated_at',
        'is_archived', 'archived_at', 'archived_via_folder',
    )
    fieldsets = (
        ('Identity', {
            'fields': ('uuid', 'title', 'slug', 'client_name'),
        }),
        ('Content', {
            'fields': ('content_markdown', 'content_json'),
        }),
        ('Settings', {
            'fields': ('status', 'language', 'cover_type'),
        }),
        ('Portadas', {
            'fields': ('include_portada', 'include_subportada', 'include_contraportada'),
        }),
        ('Archivado', {
            # Visible pero intocable: el estado de archivado solo se mueve por
            # document_archive_service; editarlo suelto recrea el estado que
            # perdió un documento en producción (ERR-016).
            'fields': ('is_archived', 'archived_at', 'archived_via_folder'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if obj is not None and obj.is_contract_mirror:
            # The contract window stores no text of its own; see ContractTemplate.
            return (*fields, 'title', 'content_markdown', 'content_json')
        return fields

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.is_contract_mirror:
            return False
        return super().has_delete_permission(request, obj)


class ContractTemplateAdmin(admin.ModelAdmin):
    """The one contract. Its text changes only through versioned migrations.

    An edit here used to be the way the default template drifted away from the
    migration chain, after which every later contract migration skipped it.
    """

    list_display = ('name', 'is_default', 'mirror_document', 'updated_at')
    raw_id_fields = ('mirror_document',)
    readonly_fields = ('content_markdown', 'created_at', 'updated_at')
    fields = ('name', 'is_default', 'mirror_document', 'content_markdown', 'created_at', 'updated_at')

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.is_default:
            return False
        return super().has_delete_permission(request, obj)


class DocumentFolderAdmin(admin.ModelAdmin):
    """
    Folder admin with the archive state sealed read-only.

    El registro pelado dejaba `is_archived` editable campo a campo, saltándose
    la cascada del servicio — el vector que recrea filas activas bajo carpetas
    archivadas. `parent` sigue editable a propósito (mover carpetas desde el
    admin es legítimo); el comando audit_archive_integrity detecta el drift.
    """
    list_display = (
        'name', 'folder_kind', 'managed_project', 'parent', 'order',
        'is_archived', 'archived_at',
    )
    list_filter = ('is_archived', 'managed_project')
    search_fields = ('name',)
    readonly_fields = (
        'managed_project', 'is_archived', 'archived_at',
        'archived_via_folder',
    )

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.managed_project_id:
            fields.extend(('name', 'parent', 'project', 'client_user', 'order'))
        return tuple(dict.fromkeys(fields))

    def has_delete_permission(self, request, obj=None):
        if obj and obj.managed_project_id:
            return False
        return super().has_delete_permission(request, obj)


class ProjectAppAdminSite(admin.AdminSite):
    """
    Custom AdminSite configuration to organize models by sections.
    """
    site_header = 'ProjectApp Administration'
    site_title = 'ProjectApp Admin'
    index_title = 'Welcome to the ProjectApp Control Panel'
    login_form = CaptchaAdminAuthenticationForm
    login_template = 'admin/captcha_login.html'

    def get_app_list(self, request):
        app_dict = self._build_app_dict(request)
        content_models = app_dict.get('content', {}).get('models', [])
        auth_models = app_dict.get('auth', {}).get('models', [])

        custom_app_list = [
            {
                'name': _('Contact Management'),
                'app_label': 'contact_management',
                'models': [m for m in content_models if m['object_name'] == 'Contact'],
            },
            {
                'name': _('Portfolio Works Management'),
                'app_label': 'portfolio_works_management',
                'models': [m for m in content_models if m['object_name'] == 'PortfolioWork'],
            },
            {
                'name': _('Business Proposals'),
                'app_label': 'business_proposals',
                'models': [m for m in content_models if m['object_name'] in [
                    'BusinessProposal', 'ProposalSection',
                    'ProposalViewEvent', 'ProposalSectionView',
                    'ProposalChangeLog', 'ProposalDefaultConfig',
                    'EmailTemplateConfig',
                ]],
            },
            {
                'name': _('Proposals (Extended)'),
                'app_label': 'proposals_extended',
                'models': [m for m in content_models if m['object_name'] in [
                    'ProposalAlert', 'ProposalProjectStage', 'ProposalShareLink',
                ]],
            },
            {
                'name': _('Blog'),
                'app_label': 'blog',
                'models': [m for m in content_models if m['object_name'] == 'BlogPost'],
            },
            {
                'name': _('Documents'),
                'app_label': 'documents',
                'models': [m for m in content_models if m['object_name'] == 'Document'],
            },
            {
                'name': _('Document Management'),
                'app_label': 'document_management',
                'models': [m for m in content_models if m['object_name'] in [
                    'DocumentFolder', 'DocumentItem', 'DocumentCollectionAccount',
                    'DocumentTag', 'DocumentNumberSequence', 'DocumentPaymentMethod',
                    'DocumentType', 'IssuerProfile',
                ]],
            },
            {
                'name': _('Tasks'),
                'app_label': 'tasks',
                'models': [m for m in content_models if m['object_name'] == 'Task'],
            },
            {
                'name': _('Diagnostics'),
                'app_label': 'diagnostics',
                'models': [m for m in content_models if m['object_name'] in [
                    'WebAppDiagnostic', 'DiagnosticSection',
                ]],
            },
            {
                'name': _('Contract Settings'),
                'app_label': 'contract_settings',
                'models': [m for m in content_models if m['object_name'] in [
                    'CompanySettings', 'ContractTemplate', 'ConfidentialityTemplate', 'ProposalDocument',
                ]],
            },
            {
                'name': _('System'),
                'app_label': 'system',
                'models': [m for m in content_models if m['object_name'] in [
                    'EmailLog', 'LinkedInToken',
                ]],
            },
            {
                'name': _('Users & Auth'),
                'app_label': 'users_auth',
                'models': auth_models,
            },
        ]

        # Catch-all: any registered model not yet shown (e.g. accounts models)
        shown = {m['object_name'] for sec in custom_app_list for m in sec['models']}
        remaining = []
        for app_data in app_dict.values():
            for model in app_data.get('models', []):
                if model['object_name'] not in shown:
                    remaining.append(model)
        if remaining:
            custom_app_list.append({
                'name': _('Platform'),
                'app_label': 'platform',
                'models': remaining,
            })

        return [s for s in custom_app_list if s['models']]

admin_site = ProjectAppAdminSite(name='myadmin')

admin_site.register(Contact, ContactAdmin)
admin_site.register(PortfolioWork, PortfolioWorkAdmin)
admin_site.register(BusinessProposal, BusinessProposalAdmin)
admin_site.register(ProposalSection)
admin_site.register(BlogPost, BlogPostAdmin)
admin_site.register(ProposalViewEvent)
admin_site.register(ProposalSectionView)
admin_site.register(ProposalChangeLog)
admin_site.register(ProposalDefaultConfig, ProposalDefaultConfigAdmin)
admin_site.register(EmailTemplateConfig, EmailTemplateConfigAdmin)
admin_site.register(Document, DocumentAdmin)
admin_site.register(DocumentType)
admin_site.register(IssuerProfile)
admin_site.register(CompanySettings, CompanySettingsAdmin)
admin_site.register(ProposalDocument)
admin_site.register(ContractTemplate, ContractTemplateAdmin)
admin_site.register(ConfidentialityTemplate)
@admin.register(FinancingAgreement, site=admin_site)
class FinancingAgreementAdmin(admin.ModelAdmin):
    list_display = (
        'number', 'client_full_name', 'project_name', 'modality',
        'cycle_number', 'status', 'is_archived', 'updated_at',
    )
    list_filter = ('status', 'modality', 'cycle_number', 'is_archived')
    search_fields = ('number', 'client_full_name', 'client_company', 'project_name')

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FinancingAgreementEvent, site=admin_site)
class FinancingAgreementEventAdmin(admin.ModelAdmin):
    list_display = ('agreement', 'event_type', 'actor', 'created_at')
    list_filter = ('event_type',)
    search_fields = ('agreement__number', 'agreement__client_full_name')

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FinancingAgreementNumberSequence, site=admin_site)
class FinancingAgreementNumberSequenceAdmin(admin.ModelAdmin):
    list_display = ('year', 'last_number', 'updated_at')

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FinancingAgreementTemplate, site=admin_site)
class FinancingAgreementTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'version', 'is_default', 'is_active', 'updated_at')
    list_filter = ('is_default', 'is_active')
    search_fields = ('name',)


@admin.register(FinancingPolicyRevision, site=admin_site)
class FinancingPolicyRevisionAdmin(admin.ModelAdmin):
    list_display = (
        'version', 'minimum_project_value_cop', 'maximum_project_value_cop',
        'financing_months', 'maximum_financed_percent',
        'late_hosting_increase_percent', 'created_by', 'created_at',
    )
    readonly_fields = (
        'version', 'minimum_project_value_cop', 'maximum_project_value_cop',
        'financing_months', 'maximum_financed_percent',
        'late_hosting_increase_percent', 'installment_due_day_start',
        'installment_due_day_end', 'created_by', 'created_at',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

admin_site.register(DocumentFolder, DocumentFolderAdmin)
admin_site.register(DocumentItem)
admin_site.register(DocumentCollectionAccount)
admin_site.register(DocumentTag)
admin_site.register(DocumentNumberSequence)
admin_site.register(DocumentPaymentMethod)
admin_site.register(Task)
admin_site.register(ProposalAlert)
admin_site.register(ProposalProjectStage)
admin_site.register(ProposalShareLink)
admin_site.register(WebAppDiagnostic)
admin_site.register(DiagnosticSection)
admin_site.register(EmailLog)
admin_site.register(EmailCopyRecipient)
admin_site.register(CommunicationThread)
admin_site.register(CommunicationMessage)
admin_site.register(CommunicationAttachment)
admin_site.register(CommunicationMessageDateCorrection)
admin_site.register(LinkedInToken)


class LinkedInPostAdmin(admin.ModelAdmin):
    list_display = ('id', 'status', 'scheduled_at', 'published_at', 'created_at')
    list_filter = ('status',)
    search_fields = ('commentary',)


admin_site.register(LinkedInPost, LinkedInPostAdmin)

class ProjectAppUserAdmin(UserAdmin):
    """Stock ``auth.User`` admin plus a "Log in as this user" button."""

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if obj is None:
            return fieldsets
        fieldsets = [(name, dict(opts)) for name, opts in fieldsets]
        section_name, section_opts = fieldsets[0]
        fields = list(section_opts.get('fields', ()))
        if 'impersonate_link' not in fields:
            fields.append('impersonate_link')
        section_opts['fields'] = tuple(fields)
        fieldsets[0] = (section_name, section_opts)
        return fieldsets

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if 'impersonate_link' not in readonly:
            readonly.append('impersonate_link')
        return readonly

    def impersonate_link(self, obj):
        if not obj or not obj.pk:
            return '—'
        url = reverse('myadmin:auth_user_login_as', args=[obj.pk])
        return format_html(
            '<a class="button" href="{}" style="text-decoration:none" '
            'target="_blank" rel="noopener">Log in as this user</a>',
            url,
        )
    impersonate_link.short_description = 'Impersonate'

    def get_urls(self):
        custom = [
            path(
                '<int:user_id>/login_as/',
                self.admin_site.admin_view(self.login_as_user_view),
                name='auth_user_login_as',
            ),
        ]
        return custom + super().get_urls()

    def login_as_user_view(self, request, user_id):
        target = get_object_or_404(User, pk=user_id)
        change_url = reverse('myadmin:auth_user_change', args=[user_id])
        try:
            tokens = impersonate(request.user, target)
        except ImpersonationError as exc:
            messages.error(request, exc.message)
            return HttpResponseRedirect(change_url)
        logger.info(
            'admin %s logged in as user %s', request.user, target,
        )
        code = create_exchange_code(tokens)
        return HttpResponseRedirect(build_impersonation_redirect_url(code))


# Auth models
admin_site.register(User, ProjectAppUserAdmin)
admin_site.register(Group, GroupAdmin)
