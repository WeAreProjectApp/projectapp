"""Explicit write contracts: DRF otherwise silently discards unknown keys."""

from collections.abc import Mapping

from rest_framework import serializers


class StrictInputMixin:
    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            writable = {
                name for name, field in self.fields.items() if not field.read_only
            }
            unexpected = set(data) - writable
            if unexpected:
                raise serializers.ValidationError(
                    {
                        name: ["Campo desconocido o de solo lectura."]
                        for name in sorted(unexpected)
                    }
                )
        return super().to_internal_value(data)
