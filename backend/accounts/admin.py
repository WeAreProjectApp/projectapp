from django.contrib import admin
from django.db import transaction

from content.admin import admin_site

from .models import (
    UserProfile,
    VerificationCode,
    Project,
    ChangeRequest,
    ChangeRequestComment,
    BugReport,
    BugComment,
    Deliverable,
    DataModelEntity,
    ProjectDataModelEntity,
    DeliverableVersion,
    DeliverableFile,
    DeliverableClientFolder,
    DeliverableClientUpload,
    Notification,
    HostingSubscription,
    Payment,
    PaymentHistory,
)


class ProjectAdmin(admin.ModelAdmin):
    from .forms_billing import BillingProjectAdminForm
    form = BillingProjectAdminForm

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        if change:
            from .services.billing_reassignment import validate_project_billing_reassignment
            original = Project.objects.select_for_update().get(pk=obj.pk)
            validate_project_billing_reassignment(original, obj.client)
        super().save_model(request, obj, form, change)

    list_display = (
        'name', 'client', 'status',
        'production_url', 'updated_at',
    )
    list_filter = ('status',)
    search_fields = (
        'name', 'client__email',
        'production_url', 'staging_url', 'repository_url',
    )
    fieldsets = (
        (None, {'fields': (
            'name', 'description', 'client', 'status', 'progress',
        )}),
        ('Fechas', {'fields': ('start_date', 'estimated_end_date', 'hosting_start_date')}),
        ('Datos financieros', {
            'classes': ('collapse',),
            'fields': ('payment_milestones', 'hosting_tiers'),
        }),
        ('URLs del producto', {
            'fields': (
                'production_url', 'staging_url', 'repository_url',
            ),
        }),
    )


admin_site.register(UserProfile)
admin_site.register(VerificationCode)
admin_site.register(Project, ProjectAdmin)
admin_site.register(ChangeRequest)
admin_site.register(ChangeRequestComment)
admin_site.register(BugReport)
admin_site.register(BugComment)
admin_site.register(Deliverable)
admin_site.register(DataModelEntity)
admin_site.register(ProjectDataModelEntity)
admin_site.register(DeliverableVersion)
admin_site.register(DeliverableFile)
admin_site.register(DeliverableClientFolder)
admin_site.register(DeliverableClientUpload)
admin_site.register(Notification)
admin_site.register(HostingSubscription)
admin_site.register(Payment)
admin_site.register(PaymentHistory)
