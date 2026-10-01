"""Django Admin's project-owner boundary shares financial validation."""
from django import forms
from django.db import transaction
from rest_framework.exceptions import ValidationError

from accounts.models import Project
from accounts.services.billing_reassignment import validate_project_billing_reassignment


def billing_validation_message(exc):
    return str(exc.detail.get('detail', exc.detail) if isinstance(exc.detail, dict) else exc.detail)


class BillingProjectAdminConflict(Exception):
    """Abort Admin's write transaction, then render a bound invalid form."""


class BillingProjectAdminForm(forms.ModelForm):
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
                validate_project_billing_reassignment(original, client)
            except ValidationError as exc:
                raise forms.ValidationError(billing_validation_message(exc)) from exc
        return client
