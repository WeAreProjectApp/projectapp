"""Django Admin's project-owner boundary shares financial validation."""
from django import forms
from rest_framework.exceptions import ValidationError

from accounts.models import Project
from accounts.services.billing_reassignment import validate_project_billing_reassignment


class BillingProjectAdminForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = '__all__'

    def clean_client(self):
        client = self.cleaned_data['client']
        if self.instance.pk:
            original = Project.objects.get(pk=self.instance.pk)
            try:
                validate_project_billing_reassignment(original, client)
            except ValidationError as exc:
                raise forms.ValidationError(str(exc.detail.get('detail', exc.detail))) from exc
        return client
