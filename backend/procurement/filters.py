"""One validated query language for the panel, alerts, export and MCP."""
import re
from functools import reduce
from operator import or_

from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({key: 'Campo no permitido.' for key in sorted(unknown)})
        return super().to_internal_value(data)


class FiltersSerializer(StrictSerializer):
    search = serializers.CharField(max_length=200, required=False, allow_blank=True)
    keywords = serializers.ListField(child=serializers.CharField(max_length=150), max_length=30, required=False)
    unspsc_codes = serializers.ListField(child=serializers.RegexField(r'^\d{2,8}$'), max_length=30, required=False)
    entity_names = serializers.ListField(child=serializers.CharField(max_length=500), max_length=30, required=False)
    departments = serializers.ListField(child=serializers.CharField(max_length=120), max_length=33, required=False)
    methods = serializers.ListField(child=serializers.CharField(max_length=250), max_length=30, required=False)
    contract_types = serializers.ListField(child=serializers.CharField(max_length=150), max_length=30, required=False)
    statuses = serializers.ListField(child=serializers.CharField(max_length=100), max_length=30, required=False)
    min_budget = serializers.DecimalField(max_digits=22, decimal_places=2, min_value=0, required=False)
    max_budget = serializers.DecimalField(max_digits=22, decimal_places=2, min_value=0, required=False)
    published_from = serializers.DateField(required=False)
    published_to = serializers.DateField(required=False)
    closing_from = serializers.DateField(required=False)
    closing_to = serializers.DateField(required=False)
    is_open = serializers.BooleanField(required=False)

    def validate(self, attrs):
        for start, end in [('min_budget', 'max_budget'), ('published_from', 'published_to'), ('closing_from', 'closing_to')]:
            if start in attrs and end in attrs and attrs[start] > attrs[end]:
                raise serializers.ValidationError({end: 'Debe ser mayor o igual al inicio del rango.'})
        return attrs


def validate_filters(data):
    if not isinstance(data, dict):
        raise serializers.ValidationError({'filters': 'Usa un objeto de filtros.'})
    serializer = FiltersSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    # Serializer output makes dates/decimals JSON-safe for saved searches and MCP.
    return dict(serializer.data)


def open_query():
    return Q(source_status__in=['Abierto', 'Publicado']) & (Q(closing_at__gt=timezone.now()) | Q(closing_at__isnull=True))


def apply_filters(queryset, filters):
    filters = validate_filters(filters)
    if filters.get('is_open', True):
        queryset = queryset.filter(open_query())
    for key, field in [('entity_names', 'entity_name'), ('departments', 'department'), ('methods', 'method'),
                       ('contract_types', 'contract_type'), ('statuses', 'source_status')]:
        if filters.get(key):
            queryset = queryset.filter(reduce(or_, [Q(**{f'{field}__iexact': value}) for value in filters[key]]))
    for key, field in [('min_budget', 'budget__gte'), ('max_budget', 'budget__lte'),
                       ('published_from', 'published_at__date__gte'), ('published_to', 'published_at__date__lte'),
                       ('closing_from', 'closing_at__date__gte'), ('closing_to', 'closing_at__date__lte')]:
        if key in filters:
            queryset = queryset.filter(**{field: filters[key]})
    if filters.get('search'):
        value = filters['search']
        queryset = queryset.filter(Q(title__icontains=value) | Q(description__icontains=value) |
                                  Q(entity_name__icontains=value) | Q(reference__icontains=value))
    alternatives = []
    for phrase in filters.get('keywords', []):
        query = Q()
        for word in phrase.split():
            query &= Q(title__icontains=word) | Q(description__icontains=word)
        if phrase.strip():
            alternatives.append(query)
    alternatives += [Q(unspsc_code__startswith=code) for code in filters.get('unspsc_codes', [])]
    if alternatives:
        queryset = queryset.filter(reduce(or_, alternatives))
    return queryset


def normalize_unspsc(value):
    return re.sub(r'^V\d+\.', '', str(value or '').strip(), flags=re.I)
