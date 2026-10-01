from copy import deepcopy
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Max, Q
from rest_framework import serializers

from accounts.models import SavedFilterTab, UserProfile
from accounts.services.billing_code import (
    BILLING_CODE_MAX_LENGTH,
    billing_code_error,
    normalize_billing_code,
)

User = get_user_model()


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    recaptcha_token = serializers.CharField(required=False, allow_blank=True, write_only=True, max_length=4096)


class VerifyOnboardingSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=6, min_length=6)
    new_password = serializers.CharField(min_length=8, write_only=True)

    def validate_new_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError('La contraseña debe tener al menos 8 caracteres.')
        return value


class ResendCodeSerializer(serializers.Serializer):
    """No fields needed — the user is identified via the verification token."""
    pass


class EmailVerifyConfirmSerializer(serializers.Serializer):
    """Confirm email ownership by submitting the OTP code sent to the client."""
    code = serializers.CharField(max_length=6, min_length=6)


class DocumentSignSerializer(serializers.Serializer):
    """Client acceptance ("firma") of a document via click-to-accept."""
    accept = serializers.BooleanField()
    signature_name = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default='',
    )

    def validate_accept(self, value):
        if not value:
            raise serializers.ValidationError(
                'Debes aceptar el documento para firmarlo.',
            )
        return value


class UserProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    avatar_display_url = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            'user_id', 'email', 'first_name', 'last_name',
            'role', 'company_name', 'phone', 'cedula',
            'date_of_birth', 'gender', 'education_level',
            'avatar_display_url', 'is_onboarded', 'profile_completed',
            'email_verified', 'email_verified_at',
            'theme_color', 'cover_image', 'custom_cover_image',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'role', 'is_onboarded', 'profile_completed',
            'email_verified', 'email_verified_at',
            'created_at', 'updated_at',
        ]

    def get_avatar_display_url(self, obj):
        request = self.context.get('request')
        url = obj.avatar_display_url
        if url and request and not url.startswith('http'):
            return request.build_absolute_uri(url)
        return url


class UpdateProfileSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)
    company_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    cedula = serializers.CharField(max_length=20, required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    gender = serializers.ChoiceField(
        choices=UserProfile.GENDER_CHOICES, required=False, allow_blank=True,
    )
    education_level = serializers.ChoiceField(
        choices=UserProfile.EDUCATION_CHOICES, required=False, allow_blank=True,
    )
    avatar = serializers.ImageField(required=False, allow_null=True)
    theme_color = serializers.CharField(max_length=7, required=False, allow_blank=True)
    cover_image = serializers.CharField(max_length=300, required=False, allow_blank=True)
    custom_cover_image = serializers.ImageField(required=False, allow_null=True)


class CompleteProfileSerializer(serializers.Serializer):
    """Mandatory profile completion after first onboarding."""
    company_name = serializers.CharField(max_length=200)
    phone = serializers.CharField(max_length=30)
    cedula = serializers.CharField(max_length=20)
    date_of_birth = serializers.DateField()
    gender = serializers.ChoiceField(choices=UserProfile.GENDER_CHOICES)
    education_level = serializers.ChoiceField(choices=UserProfile.EDUCATION_CHOICES)
    avatar = serializers.ImageField(required=False, allow_null=True)
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)

    def validate_cedula(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('La cédula es obligatoria.')
        return value

    def validate_phone(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('El teléfono es obligatorio.')
        return value


class AdminListSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email')
    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')
    user_id = serializers.IntegerField(source='user.id')
    is_active = serializers.BooleanField(source='user.is_active')

    class Meta:
        model = UserProfile
        fields = [
            'user_id', 'email', 'first_name', 'last_name',
            'is_onboarded', 'is_active', 'created_at',
        ]


class CreateAdminSerializer(serializers.Serializer):
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)

    def validate_email(self, value):
        value = value.lower().strip()
        if User.objects.filter(Q(email=value) | Q(username=value)).exists():
            raise serializers.ValidationError('Ya existe un usuario con este email.')
        return value


class CreateClientSerializer(serializers.Serializer):
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    company_name = serializers.CharField(max_length=200, required=False, default='')
    phone = serializers.CharField(max_length=30, required=False, default='')

    def validate_email(self, value):
        value = value.lower().strip()
        if User.objects.filter(Q(email=value) | Q(username=value)).exists():
            raise serializers.ValidationError('Ya existe un usuario con este email.')
        return value


class UpdateClientSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)
    company_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    nit = serializers.CharField(max_length=32, required=False, allow_blank=True)
    billing_code = serializers.CharField(
        max_length=BILLING_CODE_MAX_LENGTH, required=False, allow_blank=True,
    )
    is_active = serializers.BooleanField(required=False)

    def validate_billing_code(self, value):
        code = normalize_billing_code(value)
        if code is None:
            return ''
        error = billing_code_error(code)
        if error:
            raise serializers.ValidationError(error)
        return code


class ClientListSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email')
    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')
    user_id = serializers.IntegerField(source='user.id')
    is_active = serializers.BooleanField(source='user.is_active')
    avatar_display_url = serializers.SerializerMethodField()

    # Platform IA aggregates (admin table) — added 2026-05-17
    hosting_plan = serializers.SerializerMethodField()
    hosting_renewal_at = serializers.SerializerMethodField()
    hosting_renewal_value = serializers.SerializerMethodField()
    active_projects_count = serializers.SerializerMethodField()
    total_projects_count = serializers.SerializerMethodField()
    last_activity_at = serializers.SerializerMethodField()
    has_logged_in_once = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            'user_id', 'email', 'first_name', 'last_name',
            'company_name', 'phone', 'nit', 'billing_code',
            'is_onboarded', 'is_active',
            'profile_completed', 'avatar_display_url', 'created_at',
            'hosting_plan', 'hosting_renewal_at', 'hosting_renewal_value',
            'active_projects_count', 'total_projects_count',
            'last_activity_at', 'has_logged_in_once',
        ]

    def get_avatar_display_url(self, obj):
        request = self.context.get('request')
        url = obj.avatar_display_url
        if url and request and not url.startswith('http'):
            return request.build_absolute_uri(url)
        return url

    def _active_subscription(self, obj):
        if hasattr(obj, '_list_active_subscription'):
            return obj._list_active_subscription
        from accounts.models import HostingSubscription
        return (
            HostingSubscription.objects
            .filter(project__client=obj.user, status=HostingSubscription.STATUS_ACTIVE)
            .order_by('next_billing_date')
            .first()
        )

    def get_hosting_plan(self, obj):
        sub = self._active_subscription(obj)
        return sub.plan if sub else None

    def get_hosting_renewal_at(self, obj):
        sub = self._active_subscription(obj)
        return sub.next_billing_date if sub else None

    def get_hosting_renewal_value(self, obj):
        sub = self._active_subscription(obj)
        return sub.billing_amount if sub else None

    def get_active_projects_count(self, obj):
        if hasattr(obj, '_list_active_projects_count'):
            return obj._list_active_projects_count
        from accounts.models import Project
        return Project.objects.filter(
            client=obj.user, status=Project.STATUS_ACTIVE,
        ).count()

    def get_total_projects_count(self, obj):
        if hasattr(obj, '_list_total_projects_count'):
            return obj._list_total_projects_count
        from accounts.models import Project
        return Project.objects.filter(client=obj.user).exclude(
            status=Project.STATUS_ARCHIVED,
        ).count()

    def get_last_activity_at(self, obj):
        if hasattr(obj, '_list_latest_project_update'):
            latest = obj._list_latest_project_update
        else:
            from django.db.models import Max
            from accounts.models import Project
            latest = Project.objects.filter(client=obj.user).aggregate(
                m=Max('updated_at'),
            )['m']
        login = obj.user.last_login
        if latest and login:
            return max(latest, login)
        return latest or login

    def get_has_logged_in_once(self, obj):
        return obj.user.last_login is not None


# =========================================================================
# Project serializers
# =========================================================================

from accounts.models import Project  # noqa: E402


class ProjectListSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    status_label = serializers.SerializerMethodField()
    current_state = serializers.SerializerMethodField()
    client_name = serializers.SerializerMethodField()
    client_email = serializers.EmailField(source='client.email', read_only=True)
    client_id = serializers.IntegerField(source='client.id', read_only=True)
    client_company = serializers.SerializerMethodField()
    proposal_id = serializers.SerializerMethodField()
    proposal_title = serializers.SerializerMethodField()

    # Platform IA aggregates (admin tables) — added 2026-05-17
    bugs_open_count = serializers.SerializerMethodField()
    changes_pending_count = serializers.SerializerMethodField()
    next_deliverable = serializers.SerializerMethodField()
    next_hosting_payment = serializers.SerializerMethodField()
    phases_total_amount = serializers.SerializerMethodField()
    last_activity_at = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            'id', 'name', 'description', 'status', 'status_label',
            'current_state', 'state_review_required', 'progress',
            'start_date', 'estimated_end_date',
            'client_id', 'client_name', 'client_email', 'client_company',
            'proposal_id', 'proposal_title',
            'hosting_start_date',
            'bugs_open_count', 'changes_pending_count', 'next_deliverable',
            'next_hosting_payment',
            'phases_total_amount',
            'last_activity_at',
            'created_at', 'updated_at',
        ]

    def _business_proposal(self, obj):
        if hasattr(obj, '_list_business_proposal'):
            return obj._list_business_proposal
        return obj.linked_business_proposal()

    def get_proposal_id(self, obj):
        bp = self._business_proposal(obj)
        return bp.id if bp else None

    def get_status(self, obj):
        state = obj.current_state
        return (state.system_key or state.slug) if state else None

    def get_status_label(self, obj):
        return obj.current_state.name if obj.current_state else 'Sin clasificar'

    def get_current_state(self, obj):
        state = obj.current_state
        if state is None:
            return None
        return {
            'id': state.pk,
            'name': state.name,
            'slug': state.slug,
            'color': state.color,
            'system_key': state.system_key,
            'operational_effect': state.operational_effect,
        }

    def get_proposal_title(self, obj):
        bp = self._business_proposal(obj)
        return bp.title if bp else None

    def get_client_name(self, obj):
        u = obj.client
        return f'{u.first_name} {u.last_name}'.strip() or u.email

    def get_client_company(self, obj):
        profile = getattr(obj.client, 'profile', None)
        return profile.company_name if profile else ''

    def get_bugs_open_count(self, obj):
        if hasattr(obj, '_list_bugs_open_count'):
            return obj._list_bugs_open_count
        from accounts.models import BugReport
        open_statuses = [
            BugReport.STATUS_REPORTED, BugReport.STATUS_CONFIRMED,
            BugReport.STATUS_FIXING, BugReport.STATUS_QA,
        ]
        return BugReport.objects.filter(
            project=obj, status__in=open_statuses,
        ).count()

    def get_changes_pending_count(self, obj):
        if hasattr(obj, '_list_changes_pending_count'):
            return obj._list_changes_pending_count
        from accounts.models import ChangeRequest
        return ChangeRequest.objects.filter(
            project=obj, status=ChangeRequest.STATUS_PENDING,
        ).count()

    def get_next_deliverable(self, obj):
        # Deprecated: kept for backward compat with old admin tables.
        return None

    def get_next_hosting_payment(self, obj):
        from accounts.models import HostingSubscription
        sub = getattr(obj, 'hosting_subscription', None)
        if sub is None or sub.status != HostingSubscription.STATUS_ACTIVE:
            return None
        return {
            'date': sub.next_billing_date,
            'amount': sub.billing_amount,
            'plan': sub.plan,
        }

    def get_phases_total_amount(self, obj):
        if hasattr(obj, '_list_phases_total_amount'):
            return obj._list_phases_total_amount or 0
        total = 0
        for phase in obj.phases.select_related('business_proposal').all():
            bp = phase.business_proposal
            if bp is None:
                continue
            total += getattr(bp, 'total_investment', None) or 0
        return total

    def get_last_activity_at(self, obj):
        # MVP: project's updated_at. Future: MAX across modules — contract stable.
        return obj.updated_at


class ProjectDetailSerializer(ProjectListSerializer):
    _ADMIN_ONLY_FIELDS = (
        'payment_milestones',
        'production_url', 'staging_url', 'repository_url',
        'has_admin_password',
    )

    hosting_tiers = serializers.SerializerMethodField()
    has_subscription = serializers.SerializerMethodField()
    production_url = serializers.URLField(read_only=True)
    staging_url = serializers.URLField(read_only=True)
    repository_url = serializers.URLField(read_only=True)
    has_admin_password = serializers.SerializerMethodField()

    class Meta(ProjectListSerializer.Meta):
        fields = ProjectListSerializer.Meta.fields + [
            'payment_milestones', 'hosting_tiers', 'has_subscription',
            'production_url', 'staging_url', 'repository_url',
            'has_admin_password',
        ]

    def _phase_summary(self, obj):
        """Stream narrow phase rows once for an optimized GET detail instance."""
        if not hasattr(obj, '_detail_legacy_proposal_id'):
            return None
        if hasattr(obj, '_detail_phase_summary'):
            return obj._detail_phase_summary

        from decimal import Decimal

        summary = {'first': None, 'investment_total': 0, 'monthly_total': Decimal('0')}
        rows = obj.phases.order_by('order').values(
            'business_proposal_id', 'business_proposal__title',
            'business_proposal__total_investment', 'business_proposal__hosting_percent',
            'business_proposal__hosting_discount_quarterly',
            'business_proposal__hosting_discount_semiannual',
            'business_proposal__hosting_discount_nine_month', 'business_proposal__currency',
        ).iterator(chunk_size=200)
        for row in rows:
            if summary['first'] is None:
                summary['first'] = row
            investment = row['business_proposal__total_investment'] or 0
            summary['investment_total'] += investment
            summary['monthly_total'] += (
                Decimal(str(investment)) * Decimal(str(row['business_proposal__hosting_percent']))
                / Decimal('100') / Decimal('12')
            )
        obj._detail_phase_summary = summary
        return summary

    def get_proposal_id(self, obj):
        summary = self._phase_summary(obj)
        if summary is None:
            return super().get_proposal_id(obj)
        first = summary['first']
        return first['business_proposal_id'] if first else obj._detail_legacy_proposal_id

    def get_proposal_title(self, obj):
        summary = self._phase_summary(obj)
        if summary is None:
            return super().get_proposal_title(obj)
        first = summary['first']
        return first['business_proposal__title'] if first else obj._detail_legacy_proposal_title

    def get_phases_total_amount(self, obj):
        summary = self._phase_summary(obj)
        if summary is None:
            return super().get_phases_total_amount(obj)
        return summary['investment_total']

    def get_hosting_tiers(self, obj):
        """
        Combined hosting tiers computed from all project phases.
        Falls back to the legacy project.hosting_tiers snapshot when no phases exist.
        Discounts come from Phase 1's proposal (the primary subscription basis).
        """
        from decimal import Decimal, ROUND_HALF_UP

        summary = self._phase_summary(obj)
        if summary is not None:
            first = summary['first']
            if first is None:
                return obj.hosting_tiers or []
            total_monthly = summary['monthly_total']
            disc_q = first['business_proposal__hosting_discount_quarterly']
            disc_s = first['business_proposal__hosting_discount_semiannual']
            disc_n = first['business_proposal__hosting_discount_nine_month']
            currency = str(first['business_proposal__currency'])
        else:
            phases = list(obj.phases.select_related('business_proposal').order_by('order'))
            if not phases:
                return obj.hosting_tiers or []

            total_monthly = Decimal('0')
            for phase in phases:
                bp = phase.business_proposal
                total_inv = Decimal(str(getattr(bp, 'total_investment', 0) or 0))
                hosting_pct = Decimal(str(getattr(bp, 'hosting_percent', 80)))
                total_monthly += (total_inv * hosting_pct / Decimal('100') / Decimal('12'))

            bp1 = phases[0].business_proposal
            disc_q = getattr(bp1, 'hosting_discount_quarterly', 10)
            disc_s = getattr(bp1, 'hosting_discount_semiannual', 20)
            disc_n = getattr(bp1, 'hosting_discount_nine_month', 40)
            currency = str(getattr(bp1, 'currency', 'COP'))
        total_monthly = total_monthly.quantize(Decimal('1'), rounding=ROUND_HALF_UP)

        def _tier(frequency, months, label, badge, discount):
            factor = (Decimal('100') - Decimal(str(discount))) / Decimal('100')
            eff_monthly = (total_monthly * factor).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            billing = (eff_monthly * months).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            return {
                'frequency': frequency,
                'months': months,
                'label': label,
                'badge': badge,
                'discount_percent': discount,
                'base_monthly': int(total_monthly),
                'effective_monthly': int(eff_monthly),
                'billing_amount': int(billing),
                'currency': currency,
            }

        return [
            _tier('nine_month', 9, 'Cada 9 meses', 'Máximo descuento', disc_n),
            _tier('semiannual', 6, 'Semestral', f'{disc_s}% dcto' if disc_s else '', disc_s),
            _tier('quarterly', 3, 'Trimestral', f'{disc_q}% dcto' if disc_q else '', disc_q),
        ]

    def get_has_subscription(self, obj):
        return hasattr(obj, 'hosting_subscription')

    def get_has_admin_password(self, obj):
        if hasattr(obj, '_detail_has_admin_access'):
            return bool(obj.admin_password_encrypted or obj._detail_has_admin_access)
        return bool(
            obj.admin_password_encrypted
            or obj.admin_accesses.exclude(admin_password_encrypted='').exists()
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        profile = getattr(request.user, 'profile', None) if request else None
        if not (profile and profile.is_admin):
            for field in self._ADMIN_ONLY_FIELDS:
                if field == 'payment_milestones':
                    data[field] = []
                elif field == 'has_admin_password':
                    data[field] = False
                else:
                    data[field] = ''
        else:
            data['payment_milestones'] = instance.payment_milestones or []
        return data


class CreateProjectSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, default='', allow_blank=True)
    client_id = serializers.IntegerField()
    proposal_id = serializers.IntegerField(required=False, allow_null=True)
    progress = serializers.IntegerField(min_value=0, max_value=100, default=0)
    start_date = serializers.DateField(required=False, allow_null=True)
    estimated_end_date = serializers.DateField(required=False, allow_null=True)
    hosting_start_date = serializers.DateField(required=False, allow_null=True)

    def validate_client_id(self, value):
        try:
            user = User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError('Cliente no encontrado.')
        profile = getattr(user, 'profile', None)
        if not profile or profile.role != UserProfile.ROLE_CLIENT:
            raise serializers.ValidationError('El usuario no es un cliente.')
        return value

    def validate_proposal_id(self, value):
        if value is not None:
            from content.models import BusinessProposal
            bp = BusinessProposal.objects.filter(id=value).select_related('deliverable').first()
            if not bp:
                raise serializers.ValidationError('Propuesta no encontrada.')
            if bp.deliverable_id:
                raise serializers.ValidationError(
                    'Esta propuesta ya está vinculada a un proyecto (entregable).',
                )
        return value


class UpdateProjectSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    progress = serializers.IntegerField(min_value=0, max_value=100, required=False)
    start_date = serializers.DateField(required=False, allow_null=True)
    estimated_end_date = serializers.DateField(required=False, allow_null=True)
    production_url = serializers.URLField(required=False, allow_blank=True, max_length=500)
    staging_url = serializers.URLField(required=False, allow_blank=True, max_length=500)
    repository_url = serializers.URLField(required=False, allow_blank=True, max_length=500)


# =========================================================================
# Published delivery requirement selectors
# =========================================================================

from accounts.models import Requirement  # noqa: E402


class RequirementListSerializer(serializers.ModelSerializer):
    stage_title = serializers.CharField(source='stage.title', read_only=True)
    phase_id = serializers.IntegerField(source='stage.phase_id', read_only=True)
    phase_title = serializers.CharField(source='stage.phase.title', read_only=True)
    scope_id = serializers.IntegerField(source='stage.phase.scope_id', read_only=True)
    scope_title = serializers.CharField(source='stage.phase.scope.title', read_only=True)

    class Meta:
        model = Requirement
        fields = [
            'id', 'stage_id', 'stage_title', 'phase_id', 'phase_title',
            'scope_id', 'scope_title', 'key', 'title', 'description', 'guide',
            'order', 'version', 'review_status', 'created_at', 'updated_at',
        ]


class _SourceRequirementSerializer(serializers.Serializer):
    """Published context for bugs and change requests, separate from commercial phases."""
    id = serializers.IntegerField()
    title = serializers.CharField()
    review_status = serializers.CharField()
    stage_id = serializers.IntegerField()
    stage_title = serializers.CharField(source='stage.title')
    phase_id = serializers.IntegerField(source='stage.phase_id')
    phase_title = serializers.CharField(source='stage.phase.title')


def published_requirement_rows(project_id, actor):
    """Flatten the common client snapshot view, never expose live draft edits."""
    from accounts.services.delivery_workflow import overview

    rows = []
    for scope in overview(project_id, actor)['scopes']:
        for phase in scope['phases']:
            for stage in phase['stages']:
                for snapshot in stage['requirements']:
                    row = dict(snapshot)
                    row.update({
                        'stage_id': stage['id'], 'stage_title': stage['title'],
                        'phase_id': phase['id'], 'phase_title': phase['title'],
                        'scope_id': scope['id'], 'scope_title': scope['title'],
                    })
                    rows.append(row)
    return rows


class _SourceRequirementVisibilityMixin:
    def get_source_requirement(self, obj):
        if not obj.source_requirement_id:
            return None
        request = self.context.get('request')
        if request is None:
            return None
        profile = getattr(request.user, 'profile', None)
        if profile and profile.is_admin:
            return _SourceRequirementSerializer(obj.source_requirement).data
        cache = getattr(request, '_delivery_visible_requirement_rows', None)
        if cache is None:
            cache = {}
            request._delivery_visible_requirement_rows = cache
        if obj.project_id not in cache:
            cache[obj.project_id] = {
                row['id']: row for row in published_requirement_rows(obj.project_id, request.user)
            }
        row = cache[obj.project_id].get(obj.source_requirement_id)
        if row is None:
            return None
        return {key: row[key] for key in (
            'id', 'title', 'review_status', 'stage_id', 'stage_title', 'phase_id', 'phase_title',
        )}


# =========================================================================
# Change Request serializers
# =========================================================================

from accounts.models import ChangeRequest, ChangeRequestComment  # noqa: E402


class ChangeRequestCommentSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = ChangeRequestComment
        fields = ['id', 'content', 'is_internal', 'user_email', 'user_name', 'created_at']

    def get_user_name(self, obj):
        u = obj.user
        return f'{u.first_name} {u.last_name}'.strip() or u.email


class ChangeRequestListSerializer(_SourceRequirementVisibilityMixin, serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)
    comments_count = serializers.SerializerMethodField()
    screenshot_url = serializers.SerializerMethodField()
    source_requirement = serializers.SerializerMethodField()

    class Meta:
        model = ChangeRequest
        fields = [
            'id', 'title', 'description', 'module_or_screen',
            'suggested_priority', 'is_urgent', 'status',
            'admin_response', 'estimated_cost', 'estimated_time',
            'linked_requirement_id', 'screenshot_url',
            'source_requirement',
            'is_archived', 'archived_at',
            'created_by_name', 'created_by_email',
            'comments_count', 'created_at', 'updated_at',
        ]

    def get_created_by_name(self, obj):
        u = obj.created_by
        return f'{u.first_name} {u.last_name}'.strip() or u.email

    def get_comments_count(self, obj):
        if hasattr(obj, '_comments_count'):
            return obj._comments_count
        return obj.comments.count()

    def get_screenshot_url(self, obj):
        if not obj.screenshot:
            return None
        request = self.context.get('request')
        url = obj.screenshot.url
        if request and not url.startswith('http'):
            return request.build_absolute_uri(url)
        return url


class ChangeRequestDetailSerializer(_SourceRequirementVisibilityMixin, serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)
    comments = serializers.SerializerMethodField()
    screenshot_url = serializers.SerializerMethodField()
    source_requirement = serializers.SerializerMethodField()

    class Meta:
        model = ChangeRequest
        fields = [
            'id', 'title', 'description', 'module_or_screen',
            'suggested_priority', 'is_urgent', 'status',
            'admin_response', 'estimated_cost', 'estimated_time',
            'linked_requirement_id', 'screenshot_url',
            'source_requirement',
            'is_archived', 'archived_at',
            'created_by_name', 'created_by_email',
            'comments', 'created_at', 'updated_at',
        ]

    def get_created_by_name(self, obj):
        u = obj.created_by
        return f'{u.first_name} {u.last_name}'.strip() or u.email

    def get_comments(self, obj):
        request = self.context.get('request')
        profile = getattr(request.user, 'profile', None) if request else None
        if hasattr(obj, '_detail_comments'):
            comments = obj._detail_comments
            if not profile or not profile.is_admin:
                comments = [comment for comment in comments if not comment.is_internal]
            return ChangeRequestCommentSerializer(comments, many=True).data
        qs = obj.comments.select_related('user').all()
        if not profile or not profile.is_admin:
            qs = qs.filter(is_internal=False)
        return ChangeRequestCommentSerializer(qs, many=True).data

    def get_screenshot_url(self, obj):
        if not obj.screenshot:
            return None
        request = self.context.get('request')
        url = obj.screenshot.url
        if request and not url.startswith('http'):
            return request.build_absolute_uri(url)
        return url


class CreateChangeRequestSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=300)
    description = serializers.CharField(required=False, default='', allow_blank=True)
    module_or_screen = serializers.CharField(max_length=200, required=False, default='', allow_blank=True)
    suggested_priority = serializers.ChoiceField(
        choices=ChangeRequest.PRIORITY_CHOICES, default=ChangeRequest.PRIORITY_MEDIUM,
    )
    is_urgent = serializers.BooleanField(default=False)
    screenshot = serializers.ImageField(required=False, allow_null=True)
    source_requirement_id = serializers.IntegerField(required=True, allow_null=False)

    def validate_source_requirement_id(self, value):
        project = self.context.get('project')
        if project is None:
            raise serializers.ValidationError('Contexto de proyecto requerido.')
        request = self.context.get('request')
        if request is None:
            raise serializers.ValidationError('Contexto de usuario requerido.')
        from accounts.services.delivery_workflow import visible_requirements

        if not visible_requirements(project.pk, request.user).filter(pk=value).exists():
            raise serializers.ValidationError(
                'Requerimiento no encontrado o no está publicado para este proyecto.',
            )
        return value


class EvaluateChangeRequestSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=ChangeRequest.STATUS_CHOICES)
    admin_response = serializers.CharField(required=False, default='', allow_blank=True)
    estimated_cost = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True,
    )
    estimated_time = serializers.CharField(max_length=100, required=False, default='', allow_blank=True)


class CreateChangeRequestCommentSerializer(serializers.Serializer):
    content = serializers.CharField()
    is_internal = serializers.BooleanField(default=False)


# =========================================================================
# Bug Report serializers
# =========================================================================

from accounts.models import BugComment, BugReport, Deliverable  # noqa: E402


class BugCommentSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = BugComment
        fields = ['id', 'content', 'is_internal', 'user_email', 'user_name', 'created_at']

    def get_user_name(self, obj):
        u = obj.user
        return f'{u.first_name} {u.last_name}'.strip() or u.email


class BugReportListSerializer(_SourceRequirementVisibilityMixin, serializers.ModelSerializer):
    reported_by_name = serializers.SerializerMethodField()
    reported_by_email = serializers.EmailField(source='reported_by.email', read_only=True)
    comments_count = serializers.SerializerMethodField()
    screenshot_url = serializers.SerializerMethodField()
    source_requirement = serializers.SerializerMethodField()

    class Meta:
        model = BugReport
        fields = [
            'id', 'project_id',
            'title', 'description', 'severity', 'status',
            'environment', 'device_browser', 'is_recurring',
            'steps_to_reproduce', 'expected_behavior', 'actual_behavior',
            'admin_response', 'linked_bug_id', 'screenshot_url',
            'source_requirement',
            'is_archived', 'archived_at',
            'reported_by_name', 'reported_by_email',
            'comments_count', 'created_at', 'updated_at',
        ]

    def get_reported_by_name(self, obj):
        u = obj.reported_by
        return f'{u.first_name} {u.last_name}'.strip() or u.email

    def get_comments_count(self, obj):
        if hasattr(obj, '_comments_count'):
            return obj._comments_count
        return obj.comments.count()

    def get_screenshot_url(self, obj):
        if not obj.screenshot:
            return None
        request = self.context.get('request')
        url = obj.screenshot.url
        if request and not url.startswith('http'):
            return request.build_absolute_uri(url)
        return url


class BugReportDetailSerializer(_SourceRequirementVisibilityMixin, serializers.ModelSerializer):
    reported_by_name = serializers.SerializerMethodField()
    reported_by_email = serializers.EmailField(source='reported_by.email', read_only=True)
    comments = serializers.SerializerMethodField()
    screenshot_url = serializers.SerializerMethodField()
    source_requirement = serializers.SerializerMethodField()

    class Meta:
        model = BugReport
        fields = [
            'id', 'project_id',
            'title', 'description', 'severity', 'status',
            'environment', 'device_browser', 'is_recurring',
            'steps_to_reproduce', 'expected_behavior', 'actual_behavior',
            'admin_response', 'linked_bug_id', 'screenshot_url',
            'source_requirement',
            'is_archived', 'archived_at',
            'reported_by_name', 'reported_by_email',
            'comments', 'created_at', 'updated_at',
        ]

    def get_reported_by_name(self, obj):
        u = obj.reported_by
        return f'{u.first_name} {u.last_name}'.strip() or u.email

    def get_comments(self, obj):
        request = self.context.get('request')
        profile = getattr(request.user, 'profile', None) if request else None
        if hasattr(obj, '_detail_comments'):
            comments = obj._detail_comments
            if not profile or not profile.is_admin:
                comments = [comment for comment in comments if not comment.is_internal]
            return BugCommentSerializer(comments, many=True).data
        qs = obj.comments.select_related('user').all()
        if not profile or not profile.is_admin:
            qs = qs.filter(is_internal=False)
        return BugCommentSerializer(qs, many=True).data

    def get_screenshot_url(self, obj):
        if not obj.screenshot:
            return None
        request = self.context.get('request')
        url = obj.screenshot.url
        if request and not url.startswith('http'):
            return request.build_absolute_uri(url)
        return url


class CreateBugReportSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=300)
    description = serializers.CharField(required=False, default='', allow_blank=True)
    severity = serializers.ChoiceField(
        choices=BugReport.SEVERITY_CHOICES, default=BugReport.SEVERITY_MEDIUM,
    )
    steps_to_reproduce = serializers.ListField(
        child=serializers.CharField(), required=False, default=list,
    )
    expected_behavior = serializers.CharField(required=False, default='', allow_blank=True)
    actual_behavior = serializers.CharField(required=False, default='', allow_blank=True)
    environment = serializers.ChoiceField(
        choices=BugReport.ENV_CHOICES, default=BugReport.ENV_PRODUCTION,
    )
    device_browser = serializers.CharField(max_length=200, required=False, default='', allow_blank=True)
    is_recurring = serializers.BooleanField(default=False)
    screenshot = serializers.ImageField(required=False, allow_null=True)
    source_requirement_id = serializers.IntegerField(required=True, allow_null=False)

    def validate_source_requirement_id(self, value):
        project = self.context.get('project')
        if project is None:
            raise serializers.ValidationError('Contexto de proyecto requerido.')
        request = self.context.get('request')
        if request is None:
            raise serializers.ValidationError('Contexto de usuario requerido.')
        from accounts.services.delivery_workflow import visible_requirements

        if not visible_requirements(project.pk, request.user).filter(pk=value).exists():
            raise serializers.ValidationError(
                'Requerimiento no encontrado o no está publicado para este proyecto.',
            )
        return value


class EvaluateBugReportSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=BugReport.STATUS_CHOICES)
    admin_response = serializers.CharField(required=False, default='', allow_blank=True)
    linked_bug_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        linked_id = attrs.get('linked_bug_id')
        bug = self.context.get('bug')
        if linked_id is not None and bug is not None:
            other = BugReport.objects.filter(pk=linked_id).first()
            if not other:
                raise serializers.ValidationError({'linked_bug_id': 'Bug vinculado no encontrado.'})
            if other.is_archived:
                raise serializers.ValidationError({'linked_bug_id': 'El bug vinculado está archivado.'})
            if other.project_id != bug.project_id:
                raise serializers.ValidationError({
                    'linked_bug_id': 'El bug vinculado debe pertenecer al mismo proyecto.',
                })
        return attrs


class CreateBugCommentSerializer(serializers.Serializer):
    content = serializers.CharField()
    is_internal = serializers.BooleanField(default=False)


# =========================================================================
# Deliverable serializers
# =========================================================================

from accounts.models import (  # noqa: E402
    DataModelEntity,
    DeliverableClientFolder,
    DeliverableClientUpload,
    DeliverableFile,
    DeliverableVersion,
    ProjectDataModelEntity,
)


class DeliverableVersionSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()
    file_name = serializers.CharField(read_only=True)
    file_size = serializers.IntegerField(read_only=True)

    class Meta:
        model = DeliverableVersion
        fields = [
            'id', 'version_number', 'file_url', 'file_name', 'file_size',
            'uploaded_by_name', 'created_at',
        ]

    def get_uploaded_by_name(self, obj):
        u = obj.uploaded_by
        return f'{u.first_name} {u.last_name}'.strip() or u.email

    def get_file_url(self, obj):
        if not obj.file:
            return None
        request = self.context.get('request')
        url = obj.file.url
        if request and not url.startswith('http'):
            return request.build_absolute_uri(url)
        return url


class DeliverableListSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()
    file_name = serializers.CharField(read_only=True)
    file_size = serializers.IntegerField(read_only=True)
    versions_count = serializers.SerializerMethodField()

    class Meta:
        model = Deliverable
        fields = [
            'id', 'title', 'description', 'category', 'current_version',
            'file_url', 'file_name', 'file_size',
            'uploaded_by_name', 'versions_count',
            'source_epic_key', 'source_epic_title',
            'is_archived', 'archived_at',
            'created_at', 'updated_at',
        ]

    def get_uploaded_by_name(self, obj):
        u = obj.uploaded_by
        return f'{u.first_name} {u.last_name}'.strip() or u.email

    def get_file_url(self, obj):
        if not obj.file:
            return None
        request = self.context.get('request')
        url = obj.file.url
        if request and not url.startswith('http'):
            return request.build_absolute_uri(url)
        return url

    def get_versions_count(self, obj):
        if hasattr(obj, '_versions_count'):
            return obj._versions_count
        return obj.versions.count()


class DeliverableFileSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    uploaded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = DeliverableFile
        fields = ['id', 'title', 'category', 'file_url', 'uploaded_by_name', 'created_at']

    def get_file_url(self, obj):
        if not obj.file:
            return None
        request = self.context.get('request')
        url = obj.file.url
        if request and not url.startswith('http'):
            return request.build_absolute_uri(url)
        return url

    def get_uploaded_by_name(self, obj):
        u = obj.uploaded_by
        return f'{u.first_name} {u.last_name}'.strip() or u.email


class DeliverableClientFolderSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliverableClientFolder
        fields = ['id', 'name', 'order', 'created_at']


class DeliverableClientUploadSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    uploaded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = DeliverableClientUpload
        fields = [
            'id', 'folder', 'title', 'file_url', 'file_name',
            'uploaded_by_name', 'created_at',
        ]

    def get_file_url(self, obj):
        if not obj.file:
            return None
        request = self.context.get('request')
        url = obj.file.url
        if request and not url.startswith('http'):
            return request.build_absolute_uri(url)
        return url

    def get_uploaded_by_name(self, obj):
        u = obj.uploaded_by
        return f'{u.first_name} {u.last_name}'.strip() or u.email


class CreateDeliverableClientFolderSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    order = serializers.IntegerField(required=False, default=0, min_value=0)


class CreateDeliverableClientUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    title = serializers.CharField(required=False, default='', allow_blank=True)
    folder_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_file(self, f):
        max_bytes = 15 * 1024 * 1024
        if f.size > max_bytes:
            raise serializers.ValidationError('El PDF no puede superar 15 MB.')
        name = (getattr(f, 'name', '') or '').lower()
        if not name.endswith('.pdf'):
            raise serializers.ValidationError('Solo se permiten archivos PDF.')
        ct = (getattr(f, 'content_type', '') or '').lower()
        if ct and 'pdf' not in ct:
            raise serializers.ValidationError('El archivo debe ser PDF.')
        return f

    def validate(self, attrs):
        deliverable = self.context.get('deliverable')
        fid = attrs.get('folder_id')
        if fid is not None and deliverable is not None:
            if not DeliverableClientFolder.objects.filter(pk=fid, deliverable=deliverable).exists():
                raise serializers.ValidationError(
                    {'folder_id': 'La carpeta no pertenece a este entregable.'},
                )
        return attrs


class DataModelEntitySerializer(serializers.ModelSerializer):
    class Meta:
        model = DataModelEntity
        fields = [
            'id', 'name', 'description', 'key_fields',
            'source_entity_name', 'synced_from_proposal',
            'created_at', 'updated_at',
        ]


class ProjectDataModelEntitySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectDataModelEntity
        fields = [
            'id', 'name', 'description', 'key_fields',
            'relationship', 'created_at', 'updated_at',
        ]


class ProjectDataModelEntityItemSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=300)
    description = serializers.CharField(required=False, default='', allow_blank=True)
    keyFields = serializers.CharField(required=False, default='', allow_blank=True)
    relationship = serializers.CharField(required=False, default='', allow_blank=True)


class ProjectDataModelUploadSerializer(serializers.Serializer):
    entities = ProjectDataModelEntityItemSerializer(many=True)


class DeliverableDetailSerializer(DeliverableListSerializer):
    versions = serializers.SerializerMethodField()
    has_business_proposal = serializers.SerializerMethodField()
    proposal_id = serializers.SerializerMethodField()
    proposal_title = serializers.SerializerMethodField()
    attachment_files = serializers.SerializerMethodField()
    pdf_download_paths = serializers.SerializerMethodField()
    client_folders = serializers.SerializerMethodField()
    client_uploads = serializers.SerializerMethodField()
    collection_accounts = serializers.SerializerMethodField()
    data_model_entities = serializers.SerializerMethodField()

    class Meta(DeliverableListSerializer.Meta):
        fields = DeliverableListSerializer.Meta.fields + [
            'versions',
            'has_business_proposal',
            'proposal_id',
            'proposal_title',
            'attachment_files',
            'pdf_download_paths',
            'source_epic_key',
            'source_epic_title',
            'client_folders',
            'client_uploads',
            'collection_accounts',
            'data_model_entities',
        ]

    def get_versions_count(self, obj):
        if hasattr(obj, '_detail_versions'):
            return len(obj._detail_versions)
        return super().get_versions_count(obj)

    def get_versions(self, obj):
        versions = (
            obj._detail_versions if hasattr(obj, '_detail_versions')
            else obj.versions.select_related('uploaded_by').all()
        )
        return DeliverableVersionSerializer(versions, many=True, context=self.context).data

    def get_has_business_proposal(self, obj):
        bp = getattr(obj, 'business_proposal', None)
        return bp is not None

    def get_proposal_id(self, obj):
        bp = getattr(obj, 'business_proposal', None)
        return bp.id if bp else None

    def get_proposal_title(self, obj):
        bp = getattr(obj, 'business_proposal', None)
        return bp.title if bp else None

    def get_attachment_files(self, obj):
        qs = obj.attachment_files.select_related('uploaded_by').all()
        return DeliverableFileSerializer(qs, many=True, context=self.context).data

    def get_pdf_download_paths(self, obj):
        pid = obj.project_id
        did = obj.id
        return {
            'commercial': f'projects/{pid}/deliverables/{did}/download/commercial-proposal-pdf/',
            'technical': f'projects/{pid}/deliverables/{did}/download/technical-document-pdf/',
        }

    def get_client_folders(self, obj):
        qs = obj.client_folders.all()
        return DeliverableClientFolderSerializer(qs, many=True).data

    def get_client_uploads(self, obj):
        qs = obj.client_uploads.select_related('uploaded_by', 'folder').all()
        return DeliverableClientUploadSerializer(qs, many=True, context=self.context).data

    def get_collection_accounts(self, obj):
        try:
            from content.models import Document
            from content.services.document_type_codes import COLLECTION_ACCOUNT
        except ImportError:
            return []

        qs = Document.objects.filter(
            project_id=obj.project_id,
            document_type__code=COLLECTION_ACCOUNT,
            deliverable_id=obj.id,
        ).only('id', 'uuid', 'title', 'public_number', 'commercial_status').order_by('-created_at')[:50]
        return [
            {
                'id': d.id,
                'uuid': str(d.uuid),
                'title': d.title,
                'public_number': d.public_number,
                'commercial_status': d.commercial_status,
            }
            for d in qs
        ]

    def get_data_model_entities(self, obj):
        qs = obj.data_model_entities.filter(is_archived=False)
        return DataModelEntitySerializer(qs, many=True).data


def _validate_deliverable_file(category, f):
    """Raise ValidationError if file extension doesn't match category rules.

    designs → .zip only.
    All other categories → .pdf only.
    """
    name = (getattr(f, 'name', '') or '').lower()
    ct = (getattr(f, 'content_type', '') or '').lower()
    if category == Deliverable.CATEGORY_DESIGNS:
        if not name.endswith('.zip'):
            raise serializers.ValidationError(
                {'file': 'Los diseños deben subirse como archivo .zip.'},
            )
    else:
        if not name.endswith('.pdf'):
            raise serializers.ValidationError(
                {'file': 'Solo se permiten archivos PDF en esta categoría.'},
            )
        if ct and 'pdf' not in ct:
            raise serializers.ValidationError({'file': 'El archivo debe ser PDF.'})


class CreateDeliverableSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=300)
    description = serializers.CharField(required=False, default='', allow_blank=True)
    category = serializers.ChoiceField(
        choices=Deliverable.CATEGORY_CHOICES, default=Deliverable.CATEGORY_OTHER,
    )
    file = serializers.FileField()

    def validate(self, attrs):
        cat = attrs.get('category', Deliverable.CATEGORY_OTHER)
        f = attrs.get('file')
        if f is not None:
            _validate_deliverable_file(cat, f)
        return attrs


class UpdateDeliverableSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=300, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    category = serializers.ChoiceField(choices=Deliverable.CATEGORY_CHOICES, required=False)
    is_archived = serializers.BooleanField(required=False)


class UploadNewVersionSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate(self, attrs):
        deliverable = self.context.get('deliverable')
        f = attrs.get('file')
        if deliverable is not None and f is not None:
            _validate_deliverable_file(deliverable.category, f)
        return attrs


class CreateDeliverableFileSerializer(serializers.Serializer):
    file = serializers.FileField()
    title = serializers.CharField(required=False, default='', allow_blank=True)
    category = serializers.ChoiceField(
        choices=Deliverable.CATEGORY_CHOICES, default=Deliverable.CATEGORY_OTHER,
    )


# =========================================================================
# Notification serializers
# =========================================================================

from accounts.models import Notification  # noqa: E402


class NotificationSerializer(serializers.ModelSerializer):
    project_name = serializers.SerializerMethodField()
    deliverable_title = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            'id', 'type', 'title', 'message',
            'related_object_type', 'related_object_id',
            'project', 'project_name',
            'deliverable', 'deliverable_title',
            'is_read', 'created_at',
        ]

    def get_project_name(self, obj):
        if obj.project:
            return obj.project.name
        return None

    def get_deliverable_title(self, obj):
        if obj.deliverable:
            return obj.deliverable.title
        return None


# =========================================================================
# Payment / Subscription serializers
# =========================================================================

from accounts.models import HostingSubscription, Payment, PaymentHistory  # noqa: E402


class PaymentHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentHistory
        fields = ['id', 'from_status', 'to_status', 'source', 'metadata', 'created_at']


class ManualPaymentSerializer(serializers.Serializer):
    frequency = serializers.ChoiceField(choices=['quarterly', 'semiannual', 'nine_month'])
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('1'))
    billing_period_start = serializers.DateField()
    description = serializers.CharField(max_length=300, required=False, default='', allow_blank=True)


class PaymentSerializer(serializers.ModelSerializer):
    project_id = serializers.IntegerField(source='subscription.project_id', read_only=True)
    project_name = serializers.SerializerMethodField()
    history = PaymentHistorySerializer(many=True, read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id', 'amount', 'description',
            'billing_period_start', 'billing_period_end', 'due_date',
            'status', 'paid_at',
            'wompi_payment_link_url',
            'charge_attempts', 'last_charge_error', 'next_retry_at',
            'is_archived', 'archived_at',
            'project_id', 'project_name',
            'history',
            'created_at',
        ]

    def get_project_name(self, obj):
        return obj.subscription.project.name


class HostingSubscriptionSerializer(serializers.ModelSerializer):
    project_name = serializers.SerializerMethodField()
    project_id = serializers.IntegerField(source='project.id', read_only=True)
    plan_display = serializers.CharField(source='plan_label', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    has_payment_source = serializers.SerializerMethodField()

    class Meta:
        model = HostingSubscription
        fields = [
            'id', 'plan', 'plan_display',
            'base_monthly_amount', 'discount_percent',
            'effective_monthly_amount', 'billing_amount',
            'status', 'status_display',
            'start_date', 'next_billing_date',
            'has_payment_source',
            'card_brand', 'card_last_four', 'card_exp_month', 'card_exp_year',
            'is_archived', 'archived_at',
            'project_id', 'project_name',
            'payments', 'created_at', 'updated_at',
        ]

    def get_project_name(self, obj):
        return obj.project.name

    def get_has_payment_source(self, obj):
        return bool(obj.wompi_payment_source_id)


class HostingSubscriptionListSerializer(serializers.ModelSerializer):
    project_name = serializers.SerializerMethodField()
    project_id = serializers.IntegerField(source='project.id', read_only=True)
    plan_display = serializers.CharField(source='plan_label', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    pending_payments = serializers.SerializerMethodField()
    has_payment_source = serializers.SerializerMethodField()

    class Meta:
        model = HostingSubscription
        fields = [
            'id', 'plan', 'plan_display',
            'base_monthly_amount', 'discount_percent',
            'effective_monthly_amount', 'billing_amount',
            'status', 'status_display',
            'start_date', 'next_billing_date',
            'has_payment_source',
            'card_brand', 'card_last_four', 'card_exp_month', 'card_exp_year',
            'is_archived', 'archived_at',
            'project_id', 'project_name',
            'pending_payments', 'created_at',
        ]

    def get_has_payment_source(self, obj):
        return bool(obj.wompi_payment_source_id)

    def get_project_name(self, obj):
        return obj.project.name

    def get_pending_payments(self, obj):
        if hasattr(obj, '_pending_payments_count'):
            return obj._pending_payments_count
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now().date() + timedelta(days=7)
        return obj.payments.filter(
            is_archived=False,
            status__in=['pending', 'overdue', 'failed'],
            due_date__lte=cutoff,
        ).count()


class UpdateSubscriptionSerializer(serializers.Serializer):
    plan = serializers.ChoiceField(
        choices=HostingSubscription.PLAN_CHOICES, required=False,
    )
    status = serializers.ChoiceField(
        choices=HostingSubscription.STATUS_CHOICES, required=False,
    )
    is_archived = serializers.BooleanField(required=False)


class ProposalSummarySerializer(serializers.Serializer):
    """Lightweight serializer for proposal selection in project creation."""
    id = serializers.IntegerField()
    title = serializers.CharField()
    client_name = serializers.CharField()
    client_email = serializers.EmailField()
    total_investment = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField()
    hosting_percent = serializers.IntegerField()
    hosting_discount_nine_month = serializers.IntegerField()
    hosting_discount_semiannual = serializers.IntegerField()
    hosting_discount_quarterly = serializers.IntegerField()
    status = serializers.CharField()


# ==========================================================================
# Password recovery — input serializers for the 3-step wizard
# ==========================================================================


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetVerifyCodeSerializer(serializers.Serializer):
    reset_request_token = serializers.CharField()
    code = serializers.CharField(min_length=6, max_length=6)


class PasswordResetConfirmSerializer(serializers.Serializer):
    reset_verified_token = serializers.CharField()
    new_password = serializers.CharField(min_length=8, write_only=True)


# =========================================================================
# Project phases (platform IA refactor)
# =========================================================================


class _NestedProposalSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    total_amount = serializers.SerializerMethodField()
    status = serializers.CharField()
    deliverable_id = serializers.SerializerMethodField()

    def get_total_amount(self, obj):
        return getattr(obj, 'total_investment', None) or 0

    def get_deliverable_id(self, obj):
        return obj.deliverable_id


class ProjectPhaseSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    order = serializers.IntegerField()
    hosting_start_date = serializers.DateField(allow_null=True, required=False)
    hosting_activated_at = serializers.DateField(allow_null=True, required=False, read_only=True)
    proposal = serializers.SerializerMethodField()
    hosting_tiers = serializers.SerializerMethodField()

    def get_proposal(self, obj):
        return _NestedProposalSerializer(obj.business_proposal).data

    def get_hosting_tiers(self, obj):
        """Calculated hosting tiers for this phase from its proposal."""
        from accounts.services.hosting_billing import phase_tiers
        return phase_tiers(obj)


class UpdateProjectPhaseSerializer(serializers.Serializer):
    hosting_start_date = serializers.DateField(allow_null=True, required=True)


# ==========================================================================
# Saved filter tabs — pestañas de filtros guardados por usuario del panel
# ==========================================================================


class SavedFilterTabSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedFilterTab
        fields = [
            'id', 'view', 'name', 'filters', 'base_filters', 'order',
            'is_seeded', 'is_hidden', 'builtin_key', 'created_at', 'updated_at',
        ]
        # `is_seeded` is the seeding's own bookkeeping: letting the panel set
        # it would let a user's tab claim to be a factory one and be wiped by
        # the next "Restablecer". `builtin_key` is the same kind of claim: it
        # would turn a real tab into a placeholder whose filters are ignored.
        read_only_fields = [
            'id', 'is_seeded', 'builtin_key', 'created_at', 'updated_at',
        ]

    def create(self, validated_data):
        # A new tab's definition is whatever it was created with; writable
        # afterwards so "Fijar como base" can re-baseline deliberately.
        if 'base_filters' not in validated_data:
            validated_data['base_filters'] = deepcopy(
                validated_data.get('filters') or {},
            )
        # New user views belong after the existing strip, including builtin
        # placeholders. Leaving the model default (0) would insert every new
        # Communications view between the first factory chips until reload.
        if 'order' not in validated_data:
            current_max = SavedFilterTab.objects.filter(
                user=validated_data['user'], view=validated_data['view'],
            ).aggregate(value=Max('order'))['value']
            validated_data['order'] = 0 if current_max is None else current_max + 1
        return super().create(validated_data)

    def validate(self, attrs):
        if self.instance is None:
            user = self.context['request'].user
            view = attrs.get('view')
            # Placeholders are scaffolding for the builtins, not tabs the user
            # made: counting them would shrink the real cap from 12 to 7 in
            # Ingresos and leave Clientes unable to save a single one.
            count = SavedFilterTab.objects.filter(
                user=user, view=view, builtin_key='',
            ).count()
            if count >= SavedFilterTab.MAX_TABS_PER_VIEW:
                raise serializers.ValidationError({
                    'view': (
                        f'Límite de {SavedFilterTab.MAX_TABS_PER_VIEW} '
                        f'pestañas alcanzado para esta vista.'
                    ),
                })
        return attrs
