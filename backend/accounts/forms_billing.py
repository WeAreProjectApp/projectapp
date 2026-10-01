"""Django Admin's client transfer boundary composes the shared domain guards."""
from django import forms
from django.db import transaction
from rest_framework.exceptions import APIException

from accounts.models import Project
from accounts.services.billing_reassignment import validate_project_billing_reassignment
from accounts.services.delivery_client_transfer import assert_delivery_client_transfer_safe
from accounts.services.issue_client_transfer import assert_issue_client_transfer_safe


def billing_validation_message(exc):
    return str(exc.detail.get('detail', exc.detail) if isinstance(exc.detail, dict) else exc.detail)


class BillingProjectAdminConflict(Exception):
    """Abort Admin's write transaction, then render a bound invalid form."""


def validate_project_admin_client_transfer(project, new_client, *, actor=None):
    validate_project_billing_reassignment(project, new_client)
    current = assert_delivery_client_transfer_safe(project, new_client, actor=actor)
    assert_issue_client_transfer_safe(current, new_client)
    return current


class BillingProjectAdminForm(forms.ModelForm):
    billing_actor = None

    class Meta:
        model = Project
        fields = '__all__'

    @transaction.atomic
    def clean_client(self):
        client = self.cleaned_data['client']
        if self.instance.pk:
            # Django Admin's POST transaction encloses validation and saving;
            # this lock lives until that outer transaction finishes.
            original = Project.objects.select_for_update().get(pk=self.instance.pk)
            try:
                validate_project_admin_client_transfer(original, client, actor=self.billing_actor)
            except APIException as exc:
                raise forms.ValidationError(billing_validation_message(exc)) from exc
        return client
