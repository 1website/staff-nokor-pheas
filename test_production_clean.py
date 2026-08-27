"""
Production Clean State and Workflow Verification
"""
import unittest
from app import app
from database import get_db, init_db, clear_all_demo_data, ensure_baseline_data

class TestCleanProductionState(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        clear_all_demo_data()

    def test_01_verify_clean_baseline(self):
        """Verify baseline has 10 villages, 5 system users, and 0 demo records"""
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM villages")
        self.assertEqual(cursor.fetchone()[0], 10, "Must have 10 official villages")

        cursor.execute("SELECT COUNT(*) FROM users")
        self.assertEqual(cursor.fetchone()[0], 5, "Must have 5 default system user accounts")

        # Zero demo tables
        tables = [
            'staff', 'attendance', 'leave_requests', 'missions',
            'mission_participants', 'payroll', 'trainings', 'achievements',
            'commune_events', 'finance_transactions', 'documents'
        ]
        for tbl in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {tbl}")
            count = cursor.fetchone()[0]
            self.assertEqual(count, 0, f"Table {tbl} must have 0 demo rows, found {count}")
        conn.close()

    def test_02_login_all_roles(self):
        """Verify that all 5 system accounts can successfully log in"""
        accounts = [
            ("admin", "admin123"),
            ("clerk", "clerk123"),
            ("it_admin", "it123"),
            ("staff", "staff123"),
            ("village_chief", "village123"),
        ]
        for username, password in accounts:
            res = self.app.post('/login', data={'username': username, 'password': password}, follow_redirects=True)
            self.assertEqual(res.status_code, 200, f"Login failed for {username}")
            self.assertIn("ផ្ទាំងគ្រប់គ្រងទូទៅ".encode('utf-8'), res.data)

    def test_03_create_new_staff_and_attendance(self):
        """Verify adding a real staff member and recording attendance"""
        self.app.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)

        # 1. Create Staff
        res = self.app.post('/staff/new', data={
            'officer_code': 'NP-2026-001',
            'name_kh': 'សុខ ចាន់ដា',
            'name_en': 'Sok Chanda',
            'gender': 'ប្រុស',
            'dob': '1990-05-15',
            'national_id': '040998811',
            'phone': '012 345 678',
            'email': 'chanda@nokorpheas.gov.kh',
            'village': 'នគរភាស១',
            'category': 'clerk',
            'position_title_kh': 'មន្ត្រីរដ្ឋបាល',
            'position_title_en': 'Admin Officer',
            'cadre_level': 'ក.៣',
            'appointment_date': '2026-01-01',
            'base_salary': '1200000',
            'position_allowance': '100000',
            'family_allowance': '50000',
            'education_level': 'បរិញ្ញាបត្រ',
            'status': 'active',
            'emergency_contact': '012 999 888',
            'notes': 'មន្ត្រីទើបតែងតាំងថ្មី'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM staff WHERE officer_code = 'NP-2026-001'")
        staff_row = cursor.fetchone()
        self.assertIsNotNone(staff_row, "Created staff record must exist in DB")
        staff_id = staff_row[0]

        # 2. Record Daily Attendance
        res_att = self.app.post('/attendance/daily', data={
            f'status_{staff_id}': 'present',
            f'check_in_{staff_id}': '07:30',
            f'check_out_{staff_id}': '17:00',
            f'remarks_{staff_id}': 'វត្តមានពេញម៉ោង',
            'attendance_date': '2026-08-28'
        }, follow_redirects=True)
        self.assertEqual(res_att.status_code, 200)

        cursor.execute("SELECT status FROM attendance WHERE staff_id = ?", (staff_id,))
        att_row = cursor.fetchone()
        self.assertIsNotNone(att_row)
        self.assertEqual(att_row[0], 'present')
        conn.close()

    def test_04_create_finance_transaction(self):
        """Verify creating real finance income/expense transaction"""
        self.app.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)

        res = self.app.post('/finance/new', data={
            'type': 'income',
            'category': 'commune_fund',
            'title': 'ថវិកាមូលនិធិឃុំពីរដ្ឋបាលថ្នាក់ជាតិ',
            'amount': '15000000',
            'transaction_date': '2026-08-28',
            'payer_payee': 'រតនាគារខេត្តសៀមរាប',
            'receipt_voucher_no': 'TR-2026-001',
            'payment_method': 'bank_transfer',
            'notes': 'ថវិកាអភិវឌ្ឍន៍ឃុំ'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM finance_transactions")
        self.assertEqual(cursor.fetchone()[0], 1)
        conn.close()

if __name__ == '__main__':
    unittest.main()
