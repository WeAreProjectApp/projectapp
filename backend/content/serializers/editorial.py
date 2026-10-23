"""Explicit serializer base for editorial aggregates only."""
from rest_framework import serializers
from content.services.editorial_format import validate_editorial_values


class EditorialModelSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not data.get('text_formats'):
            data.pop('text_formats', None)
        return data

    def get_field_names(self, declared_fields, info):
        names = list(super().get_field_names(declared_fields, info))
        if 'text_formats' in info.fields and 'text_formats' not in names:
            names.append('text_formats')
        return names

    def run_validation(self, data=serializers.empty):
        values = super().run_validation(data)
        if not isinstance(values, dict) or 'text_formats' not in self.fields:
            return values
        return validate_editorial_values(self.Meta.model._meta.model_name, values, instance=self.instance)
