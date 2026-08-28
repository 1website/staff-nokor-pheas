"""
Unit & Integration Tests for State Asset Management Feature (គ្រប់គ្រងទ្រព្យសម្បត្តិរដ្ឋ)
"""
import unittest
import io
from app import app
from database import get_db, clear_all_demo_data

class TestStateAssetManagement(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.app = app
        self.app.testing = True
        clear_all_demo_data()

        # Login as admin
        self.client.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)

        # Create 2 staff members
        self.client.post('/staff/new', data={
            'officer_code': 'NP-001',
            'name_kh': 'មី គន់',
            'gender': 'ប្រុស',
            'category': 'council',
            'position_title_kh': 'មេឃុំ',
            'base_salary': '1345000',
            'village': 'នគរភាស១',
            'status': 'active'
        }, follow_redirects=True)

        self.client.post('/staff/new', data={
            'officer_code': 'NP-021',
            'name_kh': 'យន់ សុធា',
            'gender': 'ប្រុស',
            'category': 'contract',
            'position_title_kh': 'ជំនួយការហិរញ្ញវត្ថុ',
            'base_salary': '1000000',
            'village': 'ទន្លេស',
            'status': 'active'
        }, follow_redirects=True)

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM staff WHERE officer_code = 'NP-001'")
        self.staff_1_id = cursor.fetchone()["id"]
        cursor.execute("SELECT id FROM staff WHERE officer_code = 'NP-021'")
        self.staff_2_id = cursor.fetchone()["id"]
        conn.close()

    def test_01_create_asset_and_listing(self):
        """Test asset registration and appearance on dashboard"""
        res = self.client.post('/assets/new', data={
            'name_kh': 'កុំព្យូទ័រយួរដៃ Dell Vostro 3510',
            'name_en': 'Dell Vostro 3510 Laptop',
            'category': 'it_equipment',
            'brand_model': 'Dell Vostro 3510 Core i5',
            'serial_number': 'SN-DELL-2026-991',
            'acquisition_date': '2026-08-15',
            'acquisition_type': 'commune_fund',
            'original_value': '2800000',
            'condition_status': 'good',
            'location': 'បន្ទប់ស្មៀន',
            'custodian_staff_id': str(self.staff_1_id),
            'notes': 'កុំព្យូទ័រសម្រាប់ស្មៀនវាយឯកសាររដ្ឋបាល'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn('Dell Vostro'.encode('utf-8'), res.data)

        # Check DB
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM assets WHERE name_kh LIKE '%Dell%'")
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["category"], 'it_equipment')
        self.assertEqual(row["original_value"], 2800000)
        self.assertEqual(row["custodian_staff_id"], self.staff_1_id)
        conn.close()

    def test_02_asset_detail_and_qr_tag(self):
        """Test asset detail page and printable QR tag"""
        # Create asset
        self.client.post('/assets/new', data={
            'asset_code': 'NP-AST-2026-001',
            'name_kh': 'ម៉ូតូ Honda Dream 125cc',
            'category': 'vehicle',
            'brand_model': 'Honda Dream 125',
            'original_value': '9500000',
            'condition_status': 'good',
            'location': 'សាលាឃុំនគរភាស',
            'custodian_staff_id': str(self.staff_1_id)
        }, follow_redirects=True)

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM assets WHERE asset_code = 'NP-AST-2026-001'")
        asset_id = cursor.fetchone()["id"]
        conn.close()

        # View Detail
        res_detail = self.client.get(f'/assets/{asset_id}')
        self.assertEqual(res_detail.status_code, 200)
        self.assertIn('Honda Dream'.encode('utf-8'), res_detail.data)

        # View QR Tag
        res_qr = self.client.get(f'/assets/{asset_id}/qr_tag')
        self.assertEqual(res_qr.status_code, 200)
        self.assertIn('NP-AST-2026-001'.encode('utf-8'), res_qr.data)

    def test_03_asset_handover_and_maintenance(self):
        """Test asset custody handover and maintenance logging"""
        # Create asset
        self.client.post('/assets/new', data={
            'asset_code': 'NP-AST-2026-002',
            'name_kh': 'ម៉ាស៊ីនព្រីន Canon LBP2900',
            'category': 'it_equipment',
            'brand_model': 'Canon LBP2900',
            'original_value': '850000',
            'condition_status': 'good',
            'location': 'បន្ទប់ស្មៀន',
            'custodian_staff_id': str(self.staff_1_id)
        }, follow_redirects=True)

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM assets WHERE asset_code = 'NP-AST-2026-002'")
        asset_id = cursor.fetchone()["id"]

        # 1. Handover to staff 2
        res_ho = self.client.post(f'/assets/{asset_id}/handover', data={
            'to_staff_id': str(self.staff_2_id),
            'location': 'បន្ទប់ហិរញ្ញវត្ថុ',
            'action_date': '2026-08-20',
            'description': 'ផ្ទេរការប្រើប្រាស់ជូនជំនួយការហិរញ្ញវត្ថុ'
        }, follow_redirects=True)
        self.assertEqual(res_ho.status_code, 200)

        # Verify handover in DB
        cursor.execute("SELECT custodian_staff_id, location FROM assets WHERE id = ?", (asset_id,))
        updated_ast = cursor.fetchone()
        self.assertEqual(updated_ast["custodian_staff_id"], self.staff_2_id)
        self.assertEqual(updated_ast["location"], 'បន្ទប់ហិរញ្ញវត្ថុ')

        # 2. Record Maintenance
        res_maint = self.client.post(f'/assets/{asset_id}/maintenance', data={
            'condition_status': 'good',
            'action_date': '2026-08-25',
            'cost': '120000',
            'description': 'ផ្លាស់ប្តូរ Drum និងចាក់ទឹកថ្នាំម៉ាស៊ីនព្រីនថ្មី'
        }, follow_redirects=True)
        self.assertEqual(res_maint.status_code, 200)

        # Check logs in DB
        cursor.execute("SELECT * FROM asset_logs WHERE asset_id = ? ORDER BY id ASC", (asset_id,))
        logs = cursor.fetchall()
        self.assertEqual(len(logs), 3)  # created, handover, maintenance
        self.assertEqual(logs[1]["action_type"], 'handover')
        self.assertEqual(logs[2]["action_type"], 'maintenance')
        self.assertEqual(logs[2]["cost"], 120000)
        conn.close()

    def test_04_asset_excel_export_and_delete(self):
        """Test asset Excel export and deletion"""
        # Create asset
        self.client.post('/assets/new', data={
            'asset_code': 'NP-AST-2026-003',
            'name_kh': 'ទូដែកផ្ទុកឯកសារ ២ ទ្វារ',
            'category': 'office_furniture',
            'original_value': '1200000',
            'condition_status': 'good',
            'location': 'សាលប្រជុំ'
        }, follow_redirects=True)

        # Test Excel export
        res_excel = self.client.get('/assets/export_excel')
        self.assertEqual(res_excel.status_code, 200)
        self.assertEqual(res_excel.mimetype, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

        # Test Delete
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM assets WHERE asset_code = 'NP-AST-2026-003'")
        asset_id = cursor.fetchone()["id"]
        conn.close()

        res_del = self.client.post(f'/assets/{asset_id}/delete', follow_redirects=True)
        self.assertEqual(res_del.status_code, 200)

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM assets WHERE id = ?", (asset_id,))
        self.assertIsNone(cursor.fetchone())
        conn.close()

if __name__ == '__main__':
    unittest.main()
