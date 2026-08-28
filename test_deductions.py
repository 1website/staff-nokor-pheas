"""
Unit & Integration Tests for Payroll Custom Deductions Feature
"""
import unittest
from app import app
from database import get_db, clear_all_demo_data

class TestPayrollDeductions(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.app = app
        self.app.testing = True
        clear_all_demo_data()

        # Login as admin
        self.client.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)

        # Create 2 staff
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

    def test_01_payroll_generate_and_custom_deductions(self):
        """Test payroll generation and custom deduction modification"""
        # Generate payroll for 2026-08
        res_gen = self.client.post('/payroll/generate', data={'month_year': '2026-08'}, follow_redirects=True)
        self.assertEqual(res_gen.status_code, 200)

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, staff_id, base_salary, gross_salary, nssf_deduction, net_salary FROM payroll WHERE month_year = '2026-08'")
        rows = cursor.fetchall()
        self.assertEqual(len(rows), 2)
        p1 = [r for r in rows if r["base_salary"] == 1345000][0]
        p2 = [r for r in rows if r["base_salary"] == 1000000][0]

        # Update deductions for NP-001 (NSSF: 26900, Attendance: 50000, Tax/Other: 20000)
        res_ded = self.client.post(
            f'/payroll/{p1["id"]}/deductions',
            data={
                'nssf_deduction': '26900',
                'attendance_deduction': '50000',
                'tax_deduction': '20000',
                'remarks': 'កាត់អវត្តមាន ២ ថ្ងៃ និងសងបុរេប្រទាន'
            },
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        self.assertEqual(res_ded.status_code, 200)
        data = res_ded.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['total_deductions'], 96900)
        self.assertEqual(data['net_salary'], 1345000 - 96900)

        # Check in DB
        cursor.execute("SELECT nssf_deduction, attendance_deduction, tax_deduction, net_salary, remarks FROM payroll WHERE id = ?", (p1["id"],))
        updated_row = cursor.fetchone()
        self.assertEqual(updated_row["attendance_deduction"], 50000)
        self.assertEqual(updated_row["tax_deduction"], 20000)
        self.assertEqual(updated_row["net_salary"], 1248100)
        self.assertEqual(updated_row["remarks"], 'កាត់អវត្តមាន ២ ថ្ងៃ និងសងបុរេប្រទាន')

        # Check payslip view
        res_slip = self.client.get(f'/payroll/{p1["id"]}/payslip')
        self.assertEqual(res_slip.status_code, 200)
        self.assertIn('50,000'.encode('utf-8'), res_slip.data)
        self.assertIn('20,000'.encode('utf-8'), res_slip.data)
        self.assertIn('1,248,100'.encode('utf-8'), res_slip.data)
        self.assertIn('កាត់អវត្តមាន ២ ថ្ងៃ'.encode('utf-8'), res_slip.data)

        # Check payroll list page
        res_list = self.client.get('/payroll?month=2026-08')
        self.assertEqual(res_list.status_code, 200)
        self.assertIn('96,900'.encode('utf-8'), res_list.data)
        conn.close()

if __name__ == '__main__':
    unittest.main()
