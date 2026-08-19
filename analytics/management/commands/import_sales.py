import csv
import hashlib
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from analytics.models import ImportBatch, Product, Sale, Store


class Command(BaseCommand):
    help = "幂等导入门店、商品和销售数据，并记录质量审计"

    def add_arguments(self, parser):
        parser.add_argument("--stores", type=Path, default=Path("data/stores.csv"))
        parser.add_argument("--products", type=Path, default=Path("data/products.csv"))
        parser.add_argument("--sales", type=Path, default=Path("data/sales.csv"))

    @transaction.atomic
    def handle(self, *args, **options):
        paths = [options["stores"], options["products"], options["sales"]]
        digest = hashlib.sha256()
        for path in paths:
            digest.update(path.read_bytes())
        source_hash = digest.hexdigest()
        if ImportBatch.objects.filter(source_hash=source_hash).exists():
            self.stdout.write("数据源已导入，跳过重复批次")
            return

        self._import_dimensions(paths[0], paths[1])
        batch = ImportBatch.objects.create(source_hash=source_hash)
        stores = {item.external_id: item for item in Store.objects.all()}
        products = {item.external_id: item for item in Product.objects.all()}
        seen = set()
        with paths[2].open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                batch.raw_rows += 1
                fingerprint = hashlib.sha256("\x1f".join(row.values()).encode()).hexdigest()
                if fingerprint in seen:
                    batch.duplicate_rows += 1
                    continue
                seen.add(fingerprint)
                try:
                    sale_date = date.fromisoformat(row["date"].strip())
                except (ValueError, TypeError):
                    batch.invalid_date_rows += 1
                    continue
                store, product = stores.get(row["store_id"].strip()), products.get(row["product_id"].strip())
                if not store or not product:
                    batch.invalid_foreign_key_rows += 1
                    continue
                try:
                    qty, amount = int(row["qty"]), Decimal(row["amount"])
                    if qty <= 0 or amount < 0:
                        raise ValueError
                except (ValueError, InvalidOperation):
                    batch.invalid_value_rows += 1
                    continue
                Sale.objects.create(fingerprint=fingerprint, order_id=row["order_id"].strip(), date=sale_date,
                                    store=store, product=product, qty=qty, amount=amount,
                                    payment=row["payment"].strip(), batch=batch)
                batch.accepted_rows += 1
        batch.save()
        self.stdout.write(self.style.SUCCESS(f"导入完成：接受 {batch.accepted_rows}/{batch.raw_rows} 行"))

    @staticmethod
    def _import_dimensions(stores_path, products_path):
        with stores_path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                Store.objects.update_or_create(external_id=row["store_id"].strip(), defaults={
                    "name": row["store_name"].strip(), "category": row["category"].strip(),
                    "district": row["district"].strip()})
        with products_path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                Product.objects.update_or_create(external_id=row["product_id"].strip(), defaults={
                    "name": row["product_name"].strip(), "category": row["product_category"].strip(),
                    "unit_price": Decimal(row["unit_price"])})
