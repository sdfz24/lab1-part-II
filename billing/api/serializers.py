from decimal import Decimal
from rest_framework import serializers
from ..models import Provider, Barrel, Invoice, InvoiceLine



class ProviderSerializer(serializers.ModelSerializer):
    billed_barrels = serializers.SerializerMethodField()
    barrels_to_bill = serializers.SerializerMethodField()

    def get_billed_barrels(self, obj):
        # Iterate over barrels to check dynamic billing status
        return [b.id for b in obj.barrels.all() if b.is_totally_billed()]

    def get_barrels_to_bill(self, obj):
        return [b.id for b in obj.barrels.all() if not b.is_totally_billed()]

    class Meta:
        model = Provider
        fields = ["id", "name", "address", "tax_id", "has_barrels_to_bill", "liters_to_bill", "billed_barrels", "barrels_to_bill"]


class BarrelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Barrel
        fields = ["id", "provider", "number", "oil_type", "liters", "billed"]


class InvoiceLineNestedSerializer(serializers.ModelSerializer):
    # Requirement: return invoice lines WITHOUT the barrel object included.
    # We expose barrel_id only (not nested barrel details).
    barrel_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = InvoiceLine
        fields = ["id", "barrel_id", "liters", "description", "unit_price", "provider"]


class InvoiceLineCreateSerializer(serializers.Serializer):
    barrel = serializers.PrimaryKeyRelatedField(queryset=Barrel.objects.all())
    liters = serializers.IntegerField(min_value=1)
    description = serializers.CharField(max_length=255)
    unit_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )

    def create(self, validated_data: dict) -> InvoiceLine:
        invoice = self.context["invoice"]
        return invoice.add_line_for_barrel(
            barrel=validated_data["barrel"],
            liters=validated_data["liters"],
            unit_price_per_liter=validated_data["unit_price"],
            description=validated_data["description"],
        )
    
class InvoiceSerializer(serializers.ModelSerializer):
    # 1. Definimos el campo calculado usando SerializerMethodField [cite: 113, 118, 160]
    total_amount = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        # 2. Añadimos "total_amount" a la lista de campos[cite: 121].  
        fields = ["id", "invoice_no", "issued_on", "total_amount"] 

    # 3. Creamos la función para calcular el valor total [cite: 122, 123]
    def get_total_amount(self, obj: Invoice):
        # Multiplicamos litros por el precio unitario de cada línea y lo sumamos todo
        return sum(line.liters * line.unit_price for line in obj.lines.all())

