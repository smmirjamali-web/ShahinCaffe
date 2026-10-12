from django import forms
from django.contrib import admin, messages
from django.http import Http404
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.db.models import Q

from .models import (
    PaymentGatewayConfig,
    PaymentReservationResolution,
    PaymentTransaction,
)
from .services import resolve_unreferenced_payment_reservation


class PaymentReservationResolutionForm(forms.Form):
    reason = forms.CharField(
        label='شرح بررسی و دلیل تعیین تکلیف',
        min_length=20,
        max_length=5000,
        widget=forms.Textarea(attrs={'rows': 5}),
    )

    confirmed_not_registered = forms.BooleanField(
        label=(
            'پنل رسمی پذیرنده را بررسی کرده‌ام و تأیید می‌کنم '
            'که درخواست پرداخت مربوط به این رزرو ثبت نشده است.'
        ),
        required=True,
    )


@admin.register(PaymentGatewayConfig)
class PaymentGatewayConfigAdmin(admin.ModelAdmin):
    list_display = ['gateway_name', 'is_active']
    list_editable = ['is_active']
    readonly_fields = ['created_at', 'updated_at']


class PendingReferenceFilter(admin.SimpleListFilter):
    title = 'وضعیت شناسه درگاه'
    parameter_name = 'reference_status'

    def lookups(self, request, model_admin):
        return [
            ('missing', 'تراکنش معلق بدون شناسه'),
            ('present', 'دارای شناسه درگاه'),
        ]

    def queryset(self, request, queryset):
        missing_reference = (
            Q(reference_id__isnull=True)
            | Q(reference_id='')
        )

        if self.value() == 'missing':
            return queryset.filter(
                status='pending',
            ).filter(missing_reference)

        if self.value() == 'present':
            return queryset.exclude(missing_reference)

        return queryset


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'reference_id',
        'order',
        'amount',
        'status',
        'gateway',
        'created_at',
        'verification_started_at',
        'needs_reconciliation',
        'error_summary',
    ]

    list_filter = [
        'status',
        'gateway',
        'created_at',
        PendingReferenceFilter,
    ]

    search_fields = [
        'reference_id',
        'order__id',
        'customer_phone',
        'error_message',
    ]

    readonly_fields = [
        'order',
        'gateway',
        'reference_id',
        'amount',
        'status',
        'payment_method',
        'gateway_response',
        'customer_phone',
        'customer_email',
        'created_at',
        'verified_at',
        'verification_started_at',
        'error_message',
        'resolution_action',
    ]

    @admin.display(
        description='نیازمند بررسی',
        boolean=True,
    )
    def needs_reconciliation(self, obj):
        return (
            obj.status == 'pending'
            and not obj.reference_id
        )

    @admin.display(description='آخرین خطا')
    def error_summary(self, obj):
        if not obj.error_message:
            return '-'

        if len(obj.error_message) > 60:
            return f'{obj.error_message[:60]}...'

        return obj.error_message

    @admin.display(description='عملیات رزرو')
    def resolution_action(self, obj):
        if (
            obj is None
            or obj.status != 'pending'
            or obj.reference_id
        ):
            return '-'

        url = reverse(
            'admin:payments_paymenttransaction_resolve_reservation',
            args=[obj.pk],
        )

        return format_html(
            '<a class="button" href="{}">'
            'بررسی و تعیین تکلیف رزرو'
            '</a>',
            url,
        )

    def get_urls(self):
        custom_urls = [
            path(
                '<path:object_id>/resolve-reservation/',
                self.admin_site.admin_view(
                    self.resolve_reservation_view,
                ),
                name='payments_paymenttransaction_resolve_reservation',
            ),
        ]

        return custom_urls + super().get_urls()

    def resolve_reservation_view(self, request, object_id):
        obj = self.get_object(request, object_id)

        if obj is None:
            raise Http404('تراکنش پرداخت یافت نشد.')

        if not self.has_change_permission(request, obj):
            raise PermissionDenied

        if obj.status != 'pending' or obj.reference_id:
            self.message_user(
                request,
                (
                    'فقط تراکنش معلق بدون شناسه درگاه '
                    'از این مسیر قابل بررسی است.'
                ),
                level=messages.ERROR,
            )

            return HttpResponseRedirect(
                reverse(
                    'admin:payments_paymenttransaction_change',
                    args=[obj.pk],
                )
            )

        form = PaymentReservationResolutionForm(
            request.POST or None,
        )

        if request.method == 'POST' and form.is_valid():
            result = resolve_unreferenced_payment_reservation(
                transaction_id=obj.pk,
                resolved_by=request.user,
                reason=form.cleaned_data['reason'],
                confirmed_not_registered=(
                    form.cleaned_data['confirmed_not_registered']
                ),
            )

            if result['success']:
                self.message_user(
                    request,
                    'تعیین تکلیف رزرو با موفقیت ثبت شد.',
                    level=messages.SUCCESS,
                )

                return HttpResponseRedirect(
                    reverse(
                        'admin:payments_paymenttransaction_change',
                        args=[obj.pk],
                    )
                )

            self.message_user(
                request,
                result.get(
                    'error',
                    'تعیین تکلیف رزرو انجام نشد.',
                ),
                level=messages.ERROR,
            )

        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': 'تعیین تکلیف رزرو پرداخت',
            'transaction': obj,
            'original': obj,
            'form': form,
            'media': form.media,
            'back_url': reverse(
                'admin:payments_paymenttransaction_change',
                args=[obj.pk],
            ),
        }

        return TemplateResponse(
            request,
            'admin/payments/paymenttransaction/resolve_reservation.html',
            context,
        )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PaymentReservationResolution)
class PaymentReservationResolutionAdmin(admin.ModelAdmin):
    list_display = [
        'transaction',
        'resolved_by',
        'created_at',
    ]

    list_filter = ['created_at']

    search_fields = [
        'transaction__reference_id',
        'reason',
    ]

    readonly_fields = [
        'transaction',
        'resolved_by',
        'reason',
        'created_at',
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False