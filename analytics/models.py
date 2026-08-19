from django.db import models


class Store(models.Model):
    external_id = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=120)
    category = models.CharField(max_length=64)
    district = models.CharField(max_length=64)


class Product(models.Model):
    external_id = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=120)
    category = models.CharField(max_length=64)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)


class ImportBatch(models.Model):
    source_hash = models.CharField(max_length=64, unique=True)
    raw_rows = models.PositiveIntegerField(default=0)
    accepted_rows = models.PositiveIntegerField(default=0)
    duplicate_rows = models.PositiveIntegerField(default=0)
    invalid_date_rows = models.PositiveIntegerField(default=0)
    invalid_foreign_key_rows = models.PositiveIntegerField(default=0)
    invalid_value_rows = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)


class Sale(models.Model):
    fingerprint = models.CharField(max_length=64, unique=True)
    order_id = models.CharField(max_length=32, db_index=True)
    date = models.DateField(db_index=True)
    store = models.ForeignKey(Store, on_delete=models.PROTECT)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    qty = models.PositiveIntegerField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment = models.CharField(max_length=32)
    batch = models.ForeignKey(ImportBatch, on_delete=models.PROTECT)


class AssistantSession(models.Model):
    id = models.UUIDField(primary_key=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)


class AssistantMessage(models.Model):
    session = models.ForeignKey(AssistantSession, on_delete=models.CASCADE, related_name="messages")
    question = models.TextField()
    answer = models.TextField()
    evidence = models.JSONField(default=dict)
    mode = models.CharField(max_length=24, default="local")
    created_at = models.DateTimeField(auto_now_add=True)
