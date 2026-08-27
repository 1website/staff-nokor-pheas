import os
import sys
import unittest
from datetime import date

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from database import get_db, init_db, seed_data
from app import app
from utils.export_excel import export_finance_excel

class TestFinanceModule(unittest.TestCase):
    def setUp(self):
        init_db()
        seed_data()
        self.app = app.test_client()
        self.app.testing = True

    def login_admin(self):
        return self.app.post('/login', data={
            'username': 'admin',
            'password': 'admin123'
        }, follow_redirects=True)

    def test_01_db_table_and_seed_data(self):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM finance_transactions")
        count = cursor.fetchone()[0]
        self.assertGreater(count, 0, "finance_transactions table should have seeded sample data")

        cursor.execute("SELECT COUNT(*) FROM finance_transactions WHERE type = 'income'")
        inc_count = cursor.fetchone()[0]
        self.assertGreater(inc_count, 0, "Should have seeded income records")

        cursor.execute("SELECT COUNT(*) FROM finance_transactions WHERE type = 'expense'")
        exp_count = cursor.fetchone()[0]
        self.assertGreater(exp_count, 0, "Should have seeded expense records")
        conn.close()
        print(f"✓ DB Seed verification passed: Total {count} transactions ({inc_count} incomes, {exp_count} expenses)")

    def test_02_finance_list_view(self):
        self.login_admin()
        resp = self.app.get('/finance?from_month=2026-01&to_month=2026-08')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('គ្រប់គ្រងហិរញ្ញវត្ថុ និងចំណូល-ចំណាយ'.encode('utf-8'), resp.data)
        self.assertIn('សរុបចំណូល'.encode('utf-8'), resp.data)
        self.assertIn('សរុបចំណាយ'.encode('utf-8'), resp.data)
        self.assertIn('ពីខែ៖'.encode('utf-8'), resp.data)
        self.assertIn('ដល់ខែ៖'.encode('utf-8'), resp.data)
        print("✓ Finance List page loads with month range filter and Khmer content")

    def test_03_create_income_and_expense(self):
        self.login_admin()
        
        # 1. Create Income
        resp_inc = self.app.post('/finance/new', data={
            'type': 'income',
            'category': 'imprest_fund',
            'title': 'ដកប្រាក់រជ្ជទេយ្យបុរេប្រទានតេស្ត',
            'amount': '250000',
            'transaction_date': '2026-08-27',
            'payer_payee': 'លោក ម៉ៅ សុខា',
            'receipt_voucher_no': 'REC-TEST-001',
            'payment_method': 'cash',
            'notes': 'រជ្ជទេយ្យបុរេប្រទានតេស្ត'
        }, follow_redirects=True)
        self.assertEqual(resp_inc.status_code, 200)

        # 2. Create Expense
        resp_exp = self.app.post('/finance/new', data={
            'type': 'expense',
            'category': 'administrative',
            'title': 'ទិញសម្ភារៈការិយាល័យតេស្ត',
            'amount': '150000',
            'transaction_date': '2026-08-27',
            'payer_payee': 'ហាងអង្គរជុំ',
            'receipt_voucher_no': 'INV-TEST-001',
            'payment_method': 'aba',
            'notes': 'ចំណាយរដ្ឋបាលតេស្ត'
        }, follow_redirects=True)
        self.assertEqual(resp_exp.status_code, 200)

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM finance_transactions WHERE receipt_voucher_no = 'REC-TEST-001'")
        row_inc = cursor.fetchone()
        self.assertIsNotNone(row_inc)
        self.assertEqual(row_inc['amount'], 250000.0)

        cursor.execute("SELECT * FROM finance_transactions WHERE receipt_voucher_no = 'INV-TEST-001'")
        row_exp = cursor.fetchone()
        self.assertIsNotNone(row_exp)
        self.assertEqual(row_exp['amount'], 150000.0)
        conn.close()
        print("✓ Create income & expense transactions passed")

    def test_04_receipt_view(self):
        self.login_admin()
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM finance_transactions LIMIT 1")
        tx_id = cursor.fetchone()[0]
        conn.close()

        resp = self.app.get(f'/finance/{tx_id}/receipt')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('រដ្ឋបាលឃុំនគរភាស'.encode('utf-8'), resp.data)
        print("✓ Printable receipt voucher view passed")

    def test_05_excel_export(self):
        stream = export_finance_excel(from_month='2026-01', to_month='2026-08')
        self.assertIsNotNone(stream)
        self.assertGreater(len(stream.getvalue()), 1000)

        # Test route
        self.login_admin()
        resp = self.app.get('/finance/export/excel?from_month=2026-01&to_month=2026-08')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        print("✓ Excel export generation & download route with range passed")

    def test_06_dashboard_finance_integration(self):
        self.login_admin()
        resp = self.app.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('ចរន្តសាច់ប្រាក់ ចំណូល-ចំណាយ'.encode('utf-8'), resp.data)
        print("✓ Dashboard financial widget integration passed")


if __name__ == '__main__':
    unittest.main()
