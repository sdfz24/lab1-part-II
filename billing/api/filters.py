import django_filters
from ..models import Invoice, Provider


class InvoiceFilter(django_filters.FilterSet):
    invoice_no = django_filters.CharFilter(lookup_expr="icontains")
    issued_on = django_filters.DateFromToRangeFilter()

    class Meta:
        model = Invoice
        fields = ["invoice_no", "issued_on", "provider"]


class ProviderFilter(django_filters.FilterSet):
    has_barrels_to_bill = django_filters.BooleanFilter(method='filter_has_barrels_to_bill')

    class Meta:
        model = Provider
        fields = []

    def filter_has_barrels_to_bill(self, queryset, name, value):
        if value:
            return queryset.filter(barrels__billed=False).distinct()
        return queryset
