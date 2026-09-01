"""
Automated Test Suite for Nokor Pheas Commune Staff Management System
Tests all routes, authentication, CRUD, exports, and permissions
"""

import os
import sys
import io
import time
import json
import unittest
from app import app
from database import get_db, init_db, seed_data

class TestNokorPheasStaffSystem(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        init_db()
        seed_data()

    def login(self, username, password):
        return self.client.post('/login', data={
            'username': username,
            'password': password
        }, follow_redirects=True)

    def test_01_login_page_loads(self):
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn('រដ្ឋបាលឃុំនគរភាស'.encode('utf-8'), response.data)

    def test_02_admin_login_and_dashboard(self):
        res = self.login('admin', 'admin123')
        self.assertEqual(res.status_code, 200)
        self.assertIn('ផ្ទាំងគ្រប់គ្រងទូទៅ'.encode('utf-8'), res.data)
        self.assertIn('ក្រុមប្រឹក្សាឃុំ'.encode('utf-8'), res.data)

    def test_03_staff_list_and_filters(self):
        self.login('admin', 'admin123')
        conn = get_db()
        staff1 = conn.execute("SELECT name_kh FROM staff WHERE officer_code = 'NP-001'").fetchone()
        staff1_name = staff1["name_kh"] if staff1 else "NP-001"
        conn.close()

        # All staff
        res = self.client.get('/staff')
        self.assertEqual(res.status_code, 200)
        self.assertIn(staff1_name.encode('utf-8'), res.data)
        self.assertIn('NP-001'.encode('utf-8'), res.data)

        # Filter council
        res_council = self.client.get('/staff?category=council')
        self.assertEqual(res_council.status_code, 200)
        self.assertIn(staff1_name.encode('utf-8'), res_council.data)

        # Filter village
        conn = get_db()
        staff_v = conn.execute("SELECT name_kh FROM staff WHERE village = 'រមៀត'").fetchone()
        staff_v_name = staff_v["name_kh"] if staff_v else "NP-010"
        conn.close()
        res_village = self.client.get('/staff', query_string={'village': 'រមៀត'})
        self.assertEqual(res_village.status_code, 200)
        self.assertIn(staff_v_name.encode('utf-8'), res_village.data)

    def test_04_staff_detail_and_print_cv(self):
        self.login('admin', 'admin123')
        # Detail dossier
        res = self.client.get('/staff/1')
        self.assertEqual(res.status_code, 200)
        self.assertIn('ព័ត៌មានផ្ទាល់ខ្លួន'.encode('utf-8'), res.data)
        self.assertIn('NP-001'.encode('utf-8'), res.data)

        # Printable CV
        res_cv = self.client.get('/staff/1/print-cv')
        self.assertEqual(res_cv.status_code, 200)
        self.assertIn('ជីវប្រវត្តិសង្ខេប'.encode('utf-8'), res_cv.data)
        self.assertIn('ព្រះរាជាណាចក្រកម្ពុជា'.encode('utf-8'), res_cv.data)

    def test_05_attendance_daily_and_monthly(self):
        self.login('admin', 'admin123')
        # Daily view
        res = self.client.get('/attendance/daily')
        self.assertEqual(res.status_code, 200)
        self.assertIn('កត់ត្រាវត្តមានប្រចាំថ្ងៃ'.encode('utf-8'), res.data)

        # Monthly view
        res_m = self.client.get('/attendance/monthly?month=2026-08')
        self.assertEqual(res_m.status_code, 200)
        self.assertIn('តារាងស្រង់វត្តមានប្រចាំខែ'.encode('utf-8'), res_m.data)

    def test_06_leave_request_and_print_slip(self):
        self.login('admin', 'admin123')
        # Leave list
        res = self.client.get('/leave')
        self.assertEqual(res.status_code, 200)
        self.assertIn('ការសុំច្បាប់ឈប់សម្រាក'.encode('utf-8'), res.data)

        # Submit leave
        res_post = self.client.post('/leave/request', data={
            'staff_id': 1,
            'leave_type': 'annual',
            'start_date': '2026-08-28',
            'end_date': '2026-08-30',
            'reason': 'សុំច្បាប់សម្រាកព្យាបាលជំងឺ'
        }, follow_redirects=True)
        self.assertEqual(res_post.status_code, 200)

        # Print slip
        res_slip = self.client.get('/leave/1/print')
        self.assertEqual(res_slip.status_code, 200)
        self.assertIn('លិខិតអនុញ្ញាតច្បាប់ឈប់សម្រាក'.encode('utf-8'), res_slip.data)

    def test_07_missions_and_print_order(self):
        self.login('admin', 'admin123')
        # Missions list
        res = self.client.get('/missions')
        self.assertEqual(res.status_code, 200)
        self.assertIn('MS-2026-001'.encode('utf-8'), res.data)

        # Create new mission with attachment
        import io
        dummy_file = (io.BytesIO(b"%PDF-1.4 test mission document content"), "sample_mission_order.pdf")
        res_create = self.client.post('/missions/new', data={
            'title': 'ចុះអធិការកិច្ចបរិស្ថានមូលដ្ឋាន',
            'destination': 'ភូមិរមៀត',
            'start_date': '2026-08-28',
            'end_date': '2026-08-29',
            'mission_order_no': 'លប.០២៨/២៦',
            'purpose': 'ចុះពិនិត្យអនាម័យ និងបរិស្ថានតាមភូមិ',
            'allowance_per_day': 50000,
            'staff_ids': [1, 2],
            'attachment': dummy_file
        }, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(res_create.status_code, 200)
        self.assertIn('ឯកសារយោង'.encode('utf-8'), res_create.data)

        # Print order
        res_order = self.client.get('/missions/1/print-order')
        self.assertEqual(res_order.status_code, 200)
        self.assertIn('លិខិតបញ្ជាបេសកកម្ម'.encode('utf-8'), res_order.data)

    def test_08_payroll_and_payslip(self):
        self.login('admin', 'admin123')
        # Payroll list August (standard month)
        res = self.client.get('/payroll?month=2026-08')
        self.assertEqual(res.status_code, 200)
        self.assertIn('ប្រាក់បៀវត្សរ៍គោល'.encode('utf-8'), res.data)

        # Generate April (Khmer New Year month)
        res_apr = self.client.post('/payroll/generate', data={'month_year': '2026-04'}, follow_redirects=True)
        self.assertEqual(res_apr.status_code, 200)
        self.assertIn('រដូវចូលឆ្នាំថ្មី'.encode('utf-8'), res_apr.data)

        # Generate October (Pchum Ben month)
        res_oct = self.client.post('/payroll/generate', data={'month_year': '2026-10'}, follow_redirects=True)
        self.assertEqual(res_oct.status_code, 200)
        self.assertIn('រដូវបុណ្យភ្ជុំបិណ្ឌ'.encode('utf-8'), res_oct.data)

        # Individual Payslip
        from database import get_db
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id FROM payroll LIMIT 1")
        p_row = c.fetchone()
        pid = p_row["id"] if p_row else 1
        conn.close()

        res_slip = self.client.get(f'/payroll/{pid}/payslip')
        self.assertEqual(res_slip.status_code, 200)
        self.assertIn('ប័ណ្ណបើកប្រាក់បៀវត្សរ៍ និងប្រាក់ឧបត្ថម្ភ'.encode('utf-8'), res_slip.data)
        self.assertIn('ប្រាក់កាត់ផ្សេងៗ'.encode('utf-8'), res_slip.data)

    def test_09_excel_exports(self):
        self.login('admin', 'admin123')
        # Export attendance excel
        res_att = self.client.get('/reports/export/attendance-excel?month=2026-08')
        self.assertEqual(res_att.status_code, 200)
        self.assertEqual(res_att.mimetype, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertGreater(len(res_att.data), 1000)

        # Export staff list excel
        res_staff = self.client.get('/reports/export/staff-excel')
        self.assertEqual(res_staff.status_code, 200)
        self.assertEqual(res_staff.mimetype, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertGreater(len(res_staff.data), 1000)

        # Export payroll excel
        res_pay = self.client.get('/reports/export/payroll-excel?month=2026-08')
        self.assertEqual(res_pay.status_code, 200)
        self.assertEqual(res_pay.mimetype, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertGreater(len(res_pay.data), 1000)

    def test_10_evaluation_and_reports(self):
        self.login('admin', 'admin123')
        # Trainings
        res_t = self.client.get('/evaluation/trainings')
        self.assertEqual(res_t.status_code, 200)
        self.assertIn('វគ្គបណ្តុះបណ្តាល'.encode('utf-8'), res_t.data)

        # Achievements
        res_a = self.client.get('/evaluation/achievements')
        self.assertEqual(res_a.status_code, 200)
        self.assertIn('ស្នាដៃ និងគ្រឿងឥស្សរិយយស'.encode('utf-8'), res_a.data)

        # Reports hub
        res_r = self.client.get('/reports')
        self.assertEqual(res_r.status_code, 200)
        self.assertIn('មជ្ឈមណ្ឌលរបាយការណ៍'.encode('utf-8'), res_r.data)

    def test_11_photo_upload_and_display(self):
        self.login('admin', 'admin123')
        # Tiny 1x1 PNG bytes
        tiny_png = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05'
            b'\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        unique_code = f"NP-P{int(time.time() * 1000) % 100000}"
        data = {
            'officer_code': unique_code,
            'name_kh': 'សាកល្បង រូបថត',
            'name_en': 'Test Photo',
            'gender': 'ប្រុស',
            'dob': '1990-01-01',
            'village': 'រមៀត',
            'category': 'contract',
            'position_title_kh': 'មន្ត្រីសាកល្បង',
            'base_salary': '800000',
            'photo': (io.BytesIO(tiny_png), 'my_avatar.png')
        }
        try:
            res_post = self.client.post('/staff/new', data=data, content_type='multipart/form-data', follow_redirects=True)
            self.assertEqual(res_post.status_code, 200)
            self.assertIn('សាកល្បង រូបថត'.encode('utf-8'), res_post.data)
            # Check photo image tag exists in rendered HTML
            self.assertIn(f'uploads/photo_{unique_code.replace("-", "_")}_'.encode('utf-8'), res_post.data)
            self.assertIn('.png'.encode('utf-8'), res_post.data)

            # Check in staff list
            res_list = self.client.get('/staff')
            self.assertIn(f'uploads/photo_{unique_code.replace("-", "_")}_'.encode('utf-8'), res_list.data)
        finally:
            # Cleanup test staff and test photo file
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT photo FROM staff WHERE officer_code = ?", (unique_code,))
            row = cursor.fetchone()
            if row and row['photo']:
                photo_path = os.path.join(app.config['UPLOAD_FOLDER'], row['photo'])
                if os.path.exists(photo_path):
                    os.remove(photo_path)
            cursor.execute("DELETE FROM staff WHERE officer_code = ?", (unique_code,))
            conn.commit()
            conn.close()

    def test_12_id_card_and_batch_cards(self):
        self.login('admin', 'admin123')
        # Single ID card
        res_card = self.client.get('/staff/1/id-card')
        self.assertEqual(res_card.status_code, 200)
        self.assertIn('ប័ណ្ណសម្គាល់ខ្លួន'.encode('utf-8'), res_card.data)
        self.assertIn('រដ្ឋបាលឃុំនគរភាស'.encode('utf-8'), res_card.data)
        self.assertIn('data:image/png;base64,'.encode('utf-8'), res_card.data)

        # Batch ID cards sheet
        res_batch = self.client.get('/staff/id-cards')
        self.assertEqual(res_batch.status_code, 200)
        self.assertIn('បោះពុម្ពប័ណ្ណសម្គាល់ខ្លួនមន្ត្រី'.encode('utf-8'), res_batch.data)
        self.assertIn('ស្រុកអង្គរជុំ'.encode('utf-8'), res_batch.data)

    def test_13_qr_attendance_scanner_and_api(self):
        self.login('admin', 'admin123')
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO staff (id, officer_code, name_kh, name_en, gender, dob, village, category, position_title_kh, status)
            VALUES (1, 'NP-001', 'មី គន់', 'Mi Kun', 'ប្រុស', '1965-01-01', 'នគរភាស១', 'council', 'មេឃុំ', 'active'),
                   (2, 'NP-002', 'សួន វណ្ណា', 'Suon Vanna', 'ប្រុស', '1980-01-01', 'នគរភាស១', 'clerk', 'ស្មៀន', 'active')
        """)
        conn.commit()

        # Scanner page
        res_scanner = self.client.get('/attendance/scan')
        self.assertEqual(res_scanner.status_code, 200)
        self.assertIn('ស្កេនវត្តមានតាម QR Code'.encode('utf-8'), res_scanner.data)

        # Kiosk poster page
        res_kiosk = self.client.get('/attendance/kiosk-qr')
        self.assertEqual(res_kiosk.status_code, 200)
        self.assertIn('QR Code វត្តមានប្រចាំថ្ងៃ'.encode('utf-8'), res_kiosk.data)

        # Weekend rejection test (e.g. 2026-08-23 is Sunday)
        res_weekend = self.client.post('/api/attendance/scan',
            data=json.dumps({'code': 'NP-001', 'date': '2026-08-23'}),
            content_type='application/json'
        )
        self.assertEqual(res_weekend.status_code, 400)
        data_we = json.loads(res_weekend.data.decode('utf-8'))
        self.assertFalse(data_we['success'])
        self.assertTrue(data_we['is_weekend'])
        self.assertIn('ថ្ងៃឈប់សម្រាក', data_we['message'])

        # Weekday scan test (e.g. 2026-08-24 is Monday)
        res_api = self.client.post('/api/attendance/scan', 
            data=json.dumps({'code': 'NP-001', 'date': '2026-08-24'}),
            content_type='application/json'
        )
        self.assertEqual(res_api.status_code, 200)
        data = json.loads(res_api.data.decode('utf-8'))
        self.assertTrue(data['success'])
        self.assertEqual(data['staff']['officer_code'], 'NP-001')
        self.assertIn(data['action'], ['check_in', 'check_out'])

        # API scan with full QR payload on weekday
        res_api_full = self.client.post('/api/attendance/scan', 
            data=json.dumps({'code': 'NP-STAFF:NP-002|សួន វណ្ណា|ស្មៀន', 'date': '2026-08-24'}),
            content_type='application/json'
        )
        self.assertEqual(res_api_full.status_code, 200)
        data2 = json.loads(res_api_full.data.decode('utf-8'))
        self.assertTrue(data2['success'])
        self.assertEqual(data2['staff']['officer_code'], 'NP-002')

    def test_14_village_management_and_edit(self):
        self.login('admin', 'admin123')
        
        # View villages page
        res = self.client.get('/settings/villages')
        self.assertEqual(res.status_code, 200)
        self.assertIn('គ្រប់គ្រងស្ថិតិភូមិទាំង ១០'.encode('utf-8'), res.data)

        # Edit village 1 (Romeat): update families, population, female
        res_edit = self.client.post('/settings/villages/1/edit', data={
            'village_name_kh': 'រមៀត',
            'village_name_en': 'Romeat',
            'total_families': 205,
            'total_population': 910,
            'female_population': 468
        }, follow_redirects=True)
        self.assertEqual(res_edit.status_code, 200)
        self.assertIn('បានកែប្រែទិន្នន័យស្ថិតិភូមិ'.encode('utf-8'), res_edit.data)

        # Verify DB updated
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM villages WHERE id = 1")
        v = cursor.fetchone()
        self.assertEqual(v['total_families'], 205)
        self.assertEqual(v['total_population'], 910)
        self.assertEqual(v['female_population'], 468)
        conn.close()

    def test_15_national_id_validation_and_duplicate(self):
        self.login('admin', 'admin123')

        # 1. API check valid
        res_api_valid = self.client.get('/api/check-national-id?national_id=099887766')
        self.assertEqual(res_api_valid.status_code, 200)
        d1 = json.loads(res_api_valid.data.decode('utf-8'))
        self.assertTrue(d1['valid'])
        self.assertFalse(d1['duplicate'])

        conn = get_db()
        existing_s = conn.execute("SELECT national_id FROM staff WHERE national_id IS NOT NULL AND length(national_id) = 9 LIMIT 1").fetchone()
        existing_nid = existing_s["national_id"] if existing_s else "040293841"
        conn.close()

        # 2. API check duplicate
        res_api_dup = self.client.get(f'/api/check-national-id?national_id={existing_nid}')
        self.assertEqual(res_api_dup.status_code, 200)
        d2 = json.loads(res_api_dup.data.decode('utf-8'))
        self.assertFalse(d2['valid'])
        self.assertTrue(d2['duplicate'])
        self.assertIn('staff', d2)
        self.assertIn('officer_code', d2['staff'])
        self.assertIn('name_kh', d2['staff'])

        # 3. API check invalid length
        res_api_inv = self.client.get('/api/check-national-id?national_id=1234')
        self.assertEqual(res_api_inv.status_code, 200)
        d3 = json.loads(res_api_inv.data.decode('utf-8'))
        self.assertFalse(d3['valid'])

        # 4. Form submission with duplicate national_id
        res_dup_post = self.client.post('/staff/new', data={
            'officer_code': 'NP-TEST-DUP',
            'name_kh': 'ស្ទួន អត្តសញ្ញាណ',
            'name_en': 'Test Dup',
            'gender': 'ប្រុស',
            'dob': '1990-01-01',
            'national_id': existing_nid, # already belongs to a staff member
            'village': 'រមៀត',
            'category': 'contract',
            'position_title_kh': 'មន្ត្រីសាកល្បង',
            'base_salary': '800000'
        }, follow_redirects=True)
        self.assertIn('ស្ទួន'.encode('utf-8'), res_dup_post.data)

        # 5. Form submission with non-9-digit national_id
        res_short_post = self.client.post('/staff/new', data={
            'officer_code': 'NP-TEST-SHORT',
            'name_kh': 'ខ្វះខ្ទង់',
            'name_en': 'Test Short',
            'gender': 'ប្រុស',
            'dob': '1990-01-01',
            'national_id': '12345', # only 5 digits
            'village': 'រមៀត',
            'category': 'contract',
            'position_title_kh': 'មន្ត្រីសាកល្បង',
            'base_salary': '800000'
        }, follow_redirects=True)
        self.assertIn('៩ ខ្ទង់'.encode('utf-8'), res_short_post.data)

    def test_16_mission_filters_by_period(self):
        self.login('admin', 'admin123')

        # 1. Filter by All
        res_all = self.client.get('/missions?period=all')
        self.assertEqual(res_all.status_code, 200)
        self.assertIn('បញ្ជីបេសកកម្ម'.encode('utf-8'), res_all.data)

        # 2. Filter by Month
        res_month = self.client.get('/missions?period=month&month=8&year=2026')
        self.assertEqual(res_month.status_code, 200)
        self.assertIn('ខែសីហា'.encode('utf-8'), res_month.data)

        # 3. Filter by Week
        res_week = self.client.get('/missions?period=week&week=this_week')
        self.assertEqual(res_week.status_code, 200)
        self.assertIn('សប្តាហ៍នេះ'.encode('utf-8'), res_week.data)

        # 4. Filter by Year
        res_year = self.client.get('/missions?period=year&year=2026')
        self.assertEqual(res_year.status_code, 200)
        self.assertIn('ឆ្នាំ២០២៦'.encode('utf-8'), res_year.data)

        # 5. Search query
        res_search = self.client.get('/missions?q=ភូមិរមៀត')
        self.assertEqual(res_search.status_code, 200)

    def test_17_clerk_salary_zeroed(self):
        self.login('admin', 'admin123')

        # Create clerk staff
        unique_code = f"NP-CK{int(time.time() * 1000) % 100000}"
        res_post = self.client.post('/staff/new', data={
            'officer_code': unique_code,
            'name_kh': 'ស្មៀន សាកល្បង',
            'name_en': 'Test Clerk',
            'gender': 'ប្រុស',
            'dob': '1989-01-01',
            'village': 'នគរភាស១',
            'category': 'clerk',
            'position_title_kh': 'ស្មៀនឃុំ',
            'base_salary': '1350000', # should be overridden to 0
            'position_allowance': '200000',
            'family_allowance': '100000'
        }, follow_redirects=True)
        self.assertEqual(res_post.status_code, 200)

        # Verify in DB that base_salary is 0 for clerk
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT base_salary, position_allowance, family_allowance FROM staff WHERE officer_code = ?", (unique_code,))
        row = cursor.fetchone()
        self.assertEqual(row['base_salary'], 0.0)
        self.assertEqual(row['position_allowance'], 0.0)
        self.assertEqual(row['family_allowance'], 0.0)
        cursor.execute("DELETE FROM staff WHERE officer_code = ?", (unique_code,))
        conn.commit()
        conn.close()

    def test_18_senior_age_red_highlight(self):
        """Test that staff with age > 65 has age-senior red highlight badge in staff list"""
        self.login('admin', 'admin123')
        res = self.client.get('/staff')
        self.assertEqual(res.status_code, 200)
        # Should contain age-senior class for staff over 65 (e.g. Sou Vanna born 1952 is 74 years old)
        self.assertIn(b'age-senior', res.data)

    def test_19_commune_calendar_and_events(self):
        """Test commune calendar page, event creation, retrieval, and deletion"""
        self.login('admin', 'admin123')

        # 1. Open Calendar page
        res = self.client.get('/calendar')
        self.assertEqual(res.status_code, 200)
        self.assertIn('ប្រតិទិនកិច្ចការរដ្ឋបាល'.encode('utf-8'), res.data)
        self.assertIn('តារាងប្រតិទិនប្រចាំខែ'.encode('utf-8'), res.data)

        # 2. Filter calendar by type
        res_filter = self.client.get('/calendar?type=ordinary_meeting')
        self.assertEqual(res_filter.status_code, 200)

        # 3. Create a new event
        unique_title = f"ប្រជុំសាកល្បង {int(time.time())}"
        res_create = self.client.post('/calendar/events/create', data={
            'title': unique_title,
            'event_type': 'ordinary_meeting',
            'event_date': '2026-08-15',
            'start_time': '08:00',
            'end_time': '11:00',
            'location': 'សាលាឃុំនគរភាស',
            'chairperson': 'លោក ឌី គន់',
            'participants': 'សមាជិកក្រុមប្រឹក្សាឃុំ',
            'description': 'របៀបវារៈសាកល្បង',
            'status': 'scheduled'
        }, follow_redirects=True)
        self.assertEqual(res_create.status_code, 200)
        self.assertIn('បានបង្កើតកិច្ចការ'.encode('utf-8'), res_create.data)

        # 4. Query event from DB
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM commune_events WHERE title = ?", (unique_title,))
        ev_row = cursor.fetchone()
        self.assertIsNotNone(ev_row)
        ev_id = ev_row['id']

        # 5. Fetch Event JSON via API
        res_api = self.client.get(f'/calendar/events/{ev_id}')
        self.assertEqual(res_api.status_code, 200)
        data = json.loads(res_api.data.decode('utf-8'))
        self.assertEqual(data['title'], unique_title)
        self.assertEqual(data['event_type'], 'ordinary_meeting')

        # 6. Delete Event
        res_delete = self.client.post(f'/calendar/events/{ev_id}/delete', follow_redirects=True)
        self.assertEqual(res_delete.status_code, 200)
        self.assertIn('បានលុបកិច្ចការ'.encode('utf-8'), res_delete.data)

        conn.close()

if __name__ == '__main__':
    unittest.main()

