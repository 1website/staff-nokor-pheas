"""
Unit & Integration Tests for Profile Photo Upload, Base64 Persistence, and Error Fallback
"""
import io
import os
import unittest
from PIL import Image
from app import app
from database import get_db, init_db, clear_all_demo_data

class TestProfilePhotoSystem(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.app = app
        self.app.testing = True
        clear_all_demo_data()

    def create_test_image(self, width=200, height=200, color="blue"):
        img = Image.new("RGB", (width, height), color=color)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        buf.seek(0)
        return buf

    def test_01_create_staff_with_photo(self):
        """Verify staff creation with photo auto-encodes to base64 Data URL"""
        self.client.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)

        img_buf = self.create_test_image()
        res = self.client.post('/staff/new', data={
            'officer_code': 'NP-001',
            'name_kh': 'មី គន់',
            'name_en': 'MY KONN',
            'gender': 'ប្រុស',
            'dob': '1952-04-04',
            'national_id': '040123456',
            'phone': '012 345 678',
            'email': 'mykonn@nokorpheas.gov.kh',
            'village': 'នគរភាស១',
            'category': 'council',
            'position_title_kh': 'មេឃុំ',
            'position_title_en': 'Commune Chief',
            'cadre_level': 'ក.១',
            'appointment_date': '2022-06-05',
            'base_salary': '1150000',
            'position_allowance': '0',
            'family_allowance': '0',
            'education_level': 'មធ្យមសិក្សា',
            'status': 'active',
            'photo': (img_buf, 'my_konn.jpg')
        }, content_type='multipart/form-data', follow_redirects=True)

        self.assertEqual(res.status_code, 200)

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, photo FROM staff WHERE officer_code = 'NP-001'")
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        staff_id = row[0]
        photo_val = row[1]
        self.assertIsNotNone(photo_val)
        self.assertTrue(photo_val.startswith('data:image/jpeg;base64,'), "Photo must be stored as self-contained base64 Data URL")

        # Verify detail page displays photo without broken image
        res_detail = self.client.get(f'/staff/{staff_id}')
        self.assertEqual(res_detail.status_code, 200)
        self.assertIn(b'data:image/jpeg;base64,', res_detail.data)
        self.assertIn('មី គន់'.encode('utf-8'), res_detail.data)

        # Verify list page renders photo
        res_list = self.client.get('/staff')
        self.assertEqual(res_list.status_code, 200)
        self.assertIn(b'data:image/jpeg;base64,', res_list.data)

        # Verify ID card renders photo
        res_card = self.client.get(f'/staff/{staff_id}/id-card')
        self.assertEqual(res_card.status_code, 200)
        self.assertIn(b'data:image/jpeg;base64,', res_card.data)
        conn.close()

    def test_02_quick_photo_update_endpoint(self):
        """Verify 1-click photo update endpoint works via AJAX / form submit"""
        self.client.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)

        # Create staff without photo first
        self.client.post('/staff/new', data={
            'officer_code': 'NP-002',
            'name_kh': 'ស៊ូ វណ្ណា',
            'name_en': 'SOU VANNA',
            'gender': 'ប្រុស',
            'dob': '1965-08-12',
            'village': 'រមៀត',
            'category': 'council',
            'position_title_kh': 'ជំទប់ទី១',
            'base_salary': '950000'
        }, follow_redirects=True)

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM staff WHERE officer_code = 'NP-002'")
        staff_id = cursor.fetchone()[0]
        conn.close()

        # Quick update photo
        new_img = self.create_test_image(color="green")
        res_update = self.client.post(
            f'/staff/{staff_id}/photo',
            data={'photo': (new_img, 'new_avatar.jpg')},
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        self.assertEqual(res_update.status_code, 200)
        json_data = res_update.get_json()
        self.assertTrue(json_data['success'])
        self.assertTrue(json_data['photo_url'].startswith('data:image/jpeg;base64,'))

        # Check DB updated
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT photo FROM staff WHERE id = ?", (staff_id,))
        updated_photo = cursor.fetchone()[0]
        self.assertTrue(updated_photo.startswith('data:image/jpeg;base64,'))
        conn.close()

    def test_03_static_uploads_route_and_fuzzy_fallback(self):
        """Verify static uploads route serves files and handles fallbacks gracefully"""
        # Static file that exists
        res = self.client.get('/static/uploads/photo_NP_001_1787454039.jpg')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content_type, 'image/jpeg')

        # Non-existent file falls back to default avatar SVG
        res_none = self.client.get('/static/uploads/photo_non_existent_9999.jpg')
        self.assertEqual(res_none.status_code, 200)
        self.assertIn('svg', res_none.content_type)

if __name__ == '__main__':
    unittest.main()
