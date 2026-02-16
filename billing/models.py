from __future__ import annotations

from decimal import Decimal
from django.db import models, transaction
from django.core.validators import MinValueValidator


class Provider(models.Model):
    name = models.CharField(max_length=255)
    address = models.TextField()
    tax_id = models.CharField(max_length=64)

    def __str__(self) -> str:
        return f"{self.name} ({self.tax_id})"

    def has_barrels_to_bill(self) -> bool:
        return (
            self.barrels.annotate(billed_sum=models.Sum("invoice_lines__liters"))
            .filter(
                models.Q(billed_sum__lt=models.F("liters")) | models.Q(billed_sum__isnull=True)
            )
            .exists()
        )

    @property
    def liters_to_bill(self) -> int:
        total_liters = self.barrels.aggregate(t=models.Sum("liters"))["t"] or 0
        billed_liters = self.barrels.aggregate(t=models.Sum("invoice_lines__liters"))["t"] or 0
        return total_liters - billed_liters


class Barrel(models.Model):
    class OilType(models.TextChoices):
        EXTRA_VIRGIN = "EVOO", "Extra Virgin Olive Oil"
        VIRGIN = "EVO", "Virgin Olive Oil"
        REFINED = "ROO", "Refined Olive Oil"
        POMACE = "OPO", "Olive Pomace Oil"

    provider = models.ForeignKey(Provider, related_name="barrels", on_delete=models.CASCADE)
    number = models.CharField(max_length=64)
    oil_type = models.CharField(max_length=10, choices=OilType.choices, default=OilType.EXTRA_VIRGIN)

    liters = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    billed = models.BooleanField(default=False)

    class Meta:
        unique_together = ("provider", "number")

    def __str__(self) -> str:
        return f"Barrel {self.number} ({self.oil_type})"

    def is_totally_billed(self) -> bool:
        billed_liters = self.invoice_lines.aggregate(total=models.Sum("liters"))["total"] or 0
        return billed_liters >= self.liters


class Invoice(models.Model):
    invoice_no = models.CharField(max_length=64, unique=True)
    provider = models.ForeignKey(Provider, related_name="invoices", on_delete=models.PROTECT)
    issued_on = models.DateField()

    def __str__(self) -> str:
        return self.invoice_no

    @transaction.atomic
    def add_line_for_barrel(
        self,
        barrel: Barrel,
        liters: int,
        unit_price_per_liter: Decimal,
        description: str,
    ) -> "InvoiceLine":
        if liters <= 0:
            raise ValueError("liters must be > 0")
        if unit_price_per_liter <= 0:
            raise ValueError("unit_price must be > 0")

        # Business rule from the prompt:
        if barrel.is_totally_billed():
            raise ValueError("The barrel is already fully billed")

        if barrel.provider != self.provider:
            raise ValueError("The barrel does not belong to the invoice provider")

        if barrel.liters != liters:
            raise ValueError("liters must equal barrel.liters to bill the full barrel")
        
        # new rule: Check that the barrel has not already been invoiced
        if barrel.billed:
            raise ValueError("This barrel is already billed")

        new_line = InvoiceLine.objects.create(
            invoice=self,
            barrel=barrel,
            liters=liters,
            unit_price=unit_price_per_liter,
            description=description,
        )
        return new_line


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, related_name="lines", on_delete=models.CASCADE)
    barrel = models.ForeignKey(Barrel, related_name="invoice_lines", on_delete=models.PROTECT)
    liters = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    description = models.CharField(max_length=255)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])

    def __str__(self) -> str:
        return f"Line {self.id} ({self.liters} L @ {self.unit_price})"
