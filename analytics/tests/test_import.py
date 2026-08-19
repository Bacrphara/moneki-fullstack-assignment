import csv
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from analytics.models import ImportBatch, Sale


class ImportSalesCommandTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.stores = root / "stores.csv"
        self.products = root / "products.csv"
        self.sales = root / "sales.csv"
        self._write(self.stores, [
            ["store_id", "store_name", "category", "district"],
            ["S01", "测试门店", "拉面", "上海·徐汇"],
        ])
        self._write(self.products, [
            ["product_id", "product_name", "product_category", "unit_price"],
            ["P01", "牛肉poke", "主食", "40"],
        ])
        rows = [["order_id", "date", "store_id", "product_id", "qty", "amount", "payment"],
                ["O1", "2026-06-01", "S01", "P01", "2", "80", "微信"],
                ["O1", "2026-06-01", "S01", "P01", "2", "80", "微信"],
                ["O2", "坏日期", "S01", "P01", "1", "40", "现金"],
                ["O3", "2026-06-02", "S99", "P01", "1", "40", "现金"],
                ["O4", "2026-06-02", "S01", "P01", "0", "0", "现金"]]
        self._write(self.sales, rows)

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def _write(path, rows):
        with path.open("w", newline="", encoding="utf-8") as stream:
            csv.writer(stream).writerows(rows)

    def run_import(self):
        call_command("import_sales", stores=self.stores, products=self.products, sales=self.sales)

    def test_import_is_audited_and_idempotent(self):
        self.run_import()
        batch = ImportBatch.objects.get()
        self.assertEqual(Sale.objects.count(), 1)
        self.assertEqual(batch.raw_rows, 5)
        self.assertEqual(batch.accepted_rows, 1)
        self.assertEqual(batch.duplicate_rows, 1)
        self.assertEqual(batch.invalid_date_rows, 1)
        self.assertEqual(batch.invalid_foreign_key_rows, 1)
        self.assertEqual(batch.invalid_value_rows, 1)

        self.run_import()
        self.assertEqual(ImportBatch.objects.count(), 1)
        self.assertEqual(Sale.objects.count(), 1)
