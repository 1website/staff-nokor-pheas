"""
Database Initialization and Seed Data for Nokor Pheas Commune Staff Management System
(ប្រព័ន្ធគ្រប់គ្រងបុគ្គលិករដ្ឋបាលឃុំនគរភាស ស្រុកអង្គរជុំ ខេត្តសៀមរាប)
"""

import os
import shutil
import sqlite3
from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash

# Dual Database Support: Neon PostgreSQL (Production/Cloud) & SQLite (Local)
DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
IS_VERCEL = bool(os.environ.get("VERCEL"))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ORIGINAL_DB_PATH = os.path.join(BASE_DIR, "staff_management.db")

if IS_VERCEL and not DATABASE_URL:
    DB_PATH = os.path.join("/tmp", "staff_management.db")
    if not os.path.exists(DB_PATH) and os.path.exists(ORIGINAL_DB_PATH):
        try:
            shutil.copy2(ORIGINAL_DB_PATH, DB_PATH)
        except Exception:
            pass
else:
    DB_PATH = ORIGINAL_DB_PATH


class PostgresCursorWrapper:
    """Wrapper to make psycopg2 cursor compatible with sqlite3 cursor semantics"""
    def __init__(self, raw_cursor):
        self.cur = raw_cursor
        self.lastrowid = None

    def execute(self, query, params=None):
        pg_query = query.replace("?", "%s")
        pg_query = pg_query.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        
        # Check if INSERT statement without RETURNING
        trimmed = pg_query.strip()
        is_insert = trimmed.upper().startswith("INSERT INTO")
        if is_insert and "RETURNING" not in trimmed.upper():
            # Append RETURNING id if table has id
            clean_q = trimmed.rstrip(";")
            pg_query = f"{clean_q} RETURNING id;"

        try:
            if params is not None:
                self.cur.execute(pg_query, params)
            else:
                self.cur.execute(pg_query)

            if is_insert and self.cur.description:
                row = self.cur.fetchone()
                if row:
                    self.lastrowid = row[0]
        except Exception as e:
            raise e
        return self

    def executemany(self, query, params_seq):
        pg_query = query.replace("?", "%s")
        pg_query = pg_query.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        return self.cur.executemany(pg_query, params_seq)

    def fetchone(self):
        return self.cur.fetchone()

    def fetchall(self):
        return self.cur.fetchall()

    def fetchmany(self, size=None):
        return self.cur.fetchmany(size) if size else self.cur.fetchmany()

    @property
    def rowcount(self):
        return self.cur.rowcount

    @property
    def description(self):
        return self.cur.description

    def close(self):
        return self.cur.close()


class PostgresConnectionWrapper:
    """Wrapper to make psycopg2 connection compatible with sqlite3 connection semantics"""
    def __init__(self, raw_conn):
        self.conn = raw_conn

    def cursor(self):
        import psycopg2.extras
        return PostgresCursorWrapper(self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor))

    def commit(self):
        return self.conn.commit()

    def rollback(self):
        return self.conn.rollback()

    def close(self):
        return self.conn.close()

    def execute(self, query, params=None):
        cur = self.cursor()
        return cur.execute(query, params)


def get_db():
    if DATABASE_URL:
        try:
            import psycopg2
            import psycopg2.extras
            url = DATABASE_URL.strip()
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)
            raw_conn = psycopg2.connect(url, sslmode="require")
            raw_conn.autocommit = True
            return PostgresConnectionWrapper(raw_conn)
        except Exception as e:
            print(f"[DB Warning] Could not connect to PostgreSQL via DATABASE_URL: {e}. Using SQLite fallback.")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # 1. Users Table (គណនីប្រើប្រាស់)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'staff', -- 'admin', 'clerk', 'staff'
        staff_id INTEGER,
        avatar TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (staff_id) REFERENCES staff (id) ON DELETE SET NULL
    )
    """)

    # 2. Staff Table (ព័ត៌មានមន្ត្រី និងបុគ្គលិក)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS staff (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        officer_code TEXT UNIQUE NOT NULL,
        name_kh TEXT NOT NULL,
        name_en TEXT NOT NULL,
        gender TEXT NOT NULL, -- 'ប្រុស', 'ស្រី'
        dob TEXT NOT NULL,
        national_id TEXT,
        phone TEXT,
        email TEXT,
        village TEXT NOT NULL,
        commune TEXT DEFAULT 'នគរភាស',
        district TEXT DEFAULT 'អង្គរជុំ',
        province TEXT DEFAULT 'សៀមរាប',
        address TEXT,
        category TEXT NOT NULL, -- 'council', 'clerk', 'contract', 'village'
        position_title_kh TEXT NOT NULL,
        position_title_en TEXT,
        cadre_level TEXT, -- កម្រិតក្របខណ្ឌ
        appointment_date TEXT,
        contract_end_date TEXT,
        base_salary REAL DEFAULT 0,
        position_allowance REAL DEFAULT 0,
        family_allowance REAL DEFAULT 0,
        education_level TEXT,
        photo TEXT,
        status TEXT DEFAULT 'active', -- 'active', 'resigned', 'retired', 'suspended'
        emergency_contact TEXT,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 3. Documents Table (ឯកសារភ្ជាប់ស្កេន)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_id INTEGER NOT NULL,
        doc_type TEXT NOT NULL, -- 'appointment_deka', 'contract', 'degree_certificate', 'cv', 'other'
        title TEXT NOT NULL,
        filename TEXT NOT NULL,
        file_path TEXT NOT NULL,
        upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        file_size INTEGER DEFAULT 0,
        notes TEXT,
        FOREIGN KEY (staff_id) REFERENCES staff (id) ON DELETE CASCADE
    )
    """)

    # 4. Attendance Table (វត្តមានប្រចាំថ្ងៃ)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        check_in_time TEXT,
        check_out_time TEXT,
        status TEXT NOT NULL DEFAULT 'present', -- 'present', 'late', 'early_leave', 'absent', 'on_leave', 'mission'
        remarks TEXT,
        recorded_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(staff_id, date),
        FOREIGN KEY (staff_id) REFERENCES staff (id) ON DELETE CASCADE
    )
    """)

    # 5. Leave Requests Table (ការសុំច្បាប់)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS leave_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_id INTEGER NOT NULL,
        leave_type TEXT NOT NULL, -- 'annual', 'sick', 'personal', 'maternity', 'special'
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        total_days REAL NOT NULL DEFAULT 1,
        reason TEXT NOT NULL,
        attachment TEXT,
        status TEXT DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
        approved_by INTEGER,
        approval_remarks TEXT,
        approved_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (staff_id) REFERENCES staff (id) ON DELETE CASCADE
    )
    """)

    # 6. Missions Table (កត់ត្រាបេសកកម្ម)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS missions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mission_code TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        destination TEXT NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        total_days INTEGER NOT NULL DEFAULT 1,
        mission_order_no TEXT,
        purpose TEXT NOT NULL,
        allowance_per_day REAL DEFAULT 0,
        total_allowance REAL DEFAULT 0,
        attachment TEXT, -- ឯកសារយោង (PDF ឬ រូបភាព)
        status TEXT DEFAULT 'completed', -- 'planned', 'in_progress', 'completed', 'cancelled'
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 7. Mission Participants Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mission_participants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mission_id INTEGER NOT NULL,
        staff_id INTEGER NOT NULL,
        role_in_mission TEXT,
        allowance REAL DEFAULT 0,
        FOREIGN KEY (mission_id) REFERENCES missions (id) ON DELETE CASCADE,
        FOREIGN KEY (staff_id) REFERENCES staff (id) ON DELETE CASCADE
    )
    """)

    # 8. Payroll Table (ប្រាក់បៀវត្សរ៍ និងប្រាក់ឧបត្ថម្ភ)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payroll (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_id INTEGER NOT NULL,
        month_year TEXT NOT NULL, -- 'YYYY-MM'
        base_salary REAL NOT NULL DEFAULT 0,
        position_allowance REAL DEFAULT 0,
        mission_allowance REAL DEFAULT 0,
        meeting_allowance REAL DEFAULT 0,
        incentive_allowance REAL DEFAULT 0,
        family_allowance REAL DEFAULT 0,
        gross_salary REAL NOT NULL DEFAULT 0,
        nssf_deduction REAL DEFAULT 0,
        attendance_deduction REAL DEFAULT 0,
        tax_deduction REAL DEFAULT 0,
        net_salary REAL NOT NULL DEFAULT 0,
        payment_status TEXT DEFAULT 'paid', -- 'pending', 'paid'
        paid_date TEXT,
        payment_method TEXT DEFAULT 'Wing', -- 'Wing', 'ABA', 'ACLEDA', 'Canadia', 'Cash'
        remarks TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(staff_id, month_year),
        FOREIGN KEY (staff_id) REFERENCES staff (id) ON DELETE CASCADE
    )
    """)

    # 9. Trainings Table (វគ្គបណ្តុះបណ្តាល)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trainings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_id INTEGER NOT NULL,
        course_title TEXT NOT NULL,
        organizer TEXT NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        duration_days INTEGER DEFAULT 1,
        location TEXT,
        certificate_title TEXT,
        status TEXT DEFAULT 'completed',
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (staff_id) REFERENCES staff (id) ON DELETE CASCADE
    )
    """)

    # 10. Achievements Table (ស្នាដៃ និងគ្រឿងឥស្សរិយយស)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS achievements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_id INTEGER NOT NULL,
        honor_type TEXT NOT NULL, -- 'letter_of_praise', 'certificate_of_appreciation', 'work_medal', 'royal_order'
        title TEXT NOT NULL,
        awarded_by TEXT NOT NULL,
        decree_prakas_no TEXT,
        award_date TEXT NOT NULL,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (staff_id) REFERENCES staff (id) ON DELETE CASCADE
    )
    """)

    # 11. Villages Table (បញ្ជីភូមិក្នុងឃុំនគរភាស)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS villages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        village_name_kh TEXT UNIQUE NOT NULL,
        village_name_en TEXT NOT NULL,
        total_population INTEGER DEFAULT 0,
        female_population INTEGER DEFAULT 0,
        total_families INTEGER DEFAULT 0
    )
    """)

    # 12. Commune Events & Meetings Table (ប្រតិទិនកិច្ចការ និងកិច្ចប្រជុំក្រុមប្រឹក្សាឃុំ)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS commune_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        event_type TEXT NOT NULL, -- 'ordinary_meeting', 'extraordinary_meeting', 'public_forum', 'ceremony', 'urgent', 'training', 'other'
        event_date TEXT NOT NULL, -- YYYY-MM-DD
        start_time TEXT, -- HH:MM
        end_time TEXT, -- HH:MM
        location TEXT DEFAULT 'សាលាឃុំនគរភាស',
        chairperson TEXT,
        participants TEXT,
        description TEXT,
        status TEXT DEFAULT 'scheduled', -- 'scheduled', 'completed', 'postponed', 'cancelled'
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE SET NULL
    )
    """)

    # 13. Finance & Transactions Table (សៀវភៅកត់ត្រាចំណូល-ចំណាយ និងហិរញ្ញវត្ថុឃុំ)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS finance_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transaction_code TEXT UNIQUE NOT NULL,
        type TEXT NOT NULL, -- 'income', 'expense'
        category TEXT NOT NULL, -- income: 'commune_fund', 'imprest_fund', 'other_income'
                                -- expense: 'administrative', 'utility', 'maintenance', 'reception_event', 'mission_travel', 'other_expense'
        title TEXT NOT NULL,
        amount REAL NOT NULL DEFAULT 0,
        transaction_date TEXT NOT NULL, -- YYYY-MM-DD
        payer_payee TEXT, -- ឈ្មោះអ្នកបង់ប្រាក់ ឬអ្នកទទួលប្រាក់
        receipt_voucher_no TEXT, -- លេខបង្កាន់ដៃ ឬលេខប័ណ្ណចំណាយ
        payment_method TEXT DEFAULT 'cash', -- 'cash', 'aba', 'wing', 'acleda', 'canadia', 'bank_transfer'
        attachment TEXT, -- វិក្កយបត្រស្កេន ឬបង្កាន់ដៃ
        notes TEXT,
        status TEXT DEFAULT 'completed', -- 'completed', 'pending', 'cancelled'
        recorded_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (recorded_by) REFERENCES users (id) ON DELETE SET NULL
    )
    """)

    # Safe migration for existing DB
    try:
        cursor.execute("ALTER TABLE missions ADD COLUMN IF NOT EXISTS attachment TEXT")
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE villages ADD COLUMN IF NOT EXISTS female_population INTEGER DEFAULT 0")
    except Exception:
        pass

    # Seed sample commune events if table is empty
    cursor.execute("SELECT COUNT(*) FROM commune_events")
    if cursor.fetchone()[0] == 0:
        sample_events = [
            (
                "កិច្ចប្រជុំសាមញ្ញក្រុមប្រឹក្សាឃុំប្រចាំខែសីហា ២០២៦",
                "ordinary_meeting",
                "2026-08-05",
                "08:00",
                "11:30",
                "សាលប្រជុំសាលាឃុំនគរភាស",
                "លោក ឌី គន់ (មេឃុំ)",
                "សមាជិកក្រុមប្រឹក្សាឃុំ និងស្មៀនឃុំ",
                "ពិនិត្យ និងអនុម័តរបាយការណ៍ប្រចាំខែកក្កដា និងលើកទិសដៅការងារខែសីហា ២០២៦",
                "completed"
            ),
            (
                "វេទិកាសាធារណៈជាមួយប្រជាពលរដ្ឋភូមិល្បើក",
                "public_forum",
                "2026-08-14",
                "08:30",
                "11:00",
                "វត្តល្បើក ភូមិល្បើក",
                "លោក ឈឺន គឹមស៊ាន (ជំទប់ទី១)",
                "ប្រជាពលរដ្ឋភូមិល្បើក និងគណៈកម្មាធិការភូមិ",
                "ស្តាប់មតិយោបល់ និងដោះស្រាយកង្វល់របស់ប្រជាពលរដ្ឋលើការងារអភិវឌ្ឍន៍ភូមិ-ឃុំ",
                "completed"
            ),
            (
                "កិច្ចប្រជុំវិសាមញ្ញស្តីពីការរៀបចំផែនការវិនិយោគឃុំ (CIP)",
                "extraordinary_meeting",
                "2026-08-20",
                "09:00",
                "11:30",
                "សាលាឃុំនគរភាស",
                "លោក ឌី គន់ (មេឃុំ)",
                "ក្រុមប្រឹក្សាឃុំ មន្ត្រីជំនួយការ និងមេភូមិទាំង១០",
                "កិច្ចប្រជុំពិភាក្សាជ្រើសរើសគម្រោងអាទិភាពសម្រាប់ផែនការវិនិយោគបីឆ្នាំរំកិល",
                "completed"
            ),
            (
                "កិច្ចប្រជុំគណៈកម្មាធិការទទួលបន្ទុកកិច្ចការនារី និងកុមារ (គ.ក.ន.ក)",
                "ordinary_meeting",
                "2026-08-28",
                "08:00",
                "10:30",
                "សាលាឃុំនគរភាស",
                "លោកស្រី ឈឺន ចិត្ត (មេភូមិសរសរស្រទង់)",
                "សមាជិក គ.ក.ន.ក ឃុំនគរភាស",
                "តាមដានការងារអនាម័យ សុខភាពមាតា-ទារក និងការចុះឈ្មោះសំបុត្រកំណើត",
                "scheduled"
            ),
            (
                "កិច្ចប្រជុំសាមញ្ញក្រុមប្រឹក្សាឃុំប្រចាំខែកញ្ញា ២០២៦",
                "ordinary_meeting",
                "2026-09-02",
                "08:00",
                "11:30",
                "សាលាឃុំនគរភាស",
                "លោក ឌី គន់ (មេឃុំ)",
                "សមាជិកក្រុមប្រឹក្សាឃុំ និងស្មៀនឃុំ",
                "ត្រួតពិនិត្យការងាររដ្ឋបាល សន្តិសុខសណ្តាប់ធ្នាប់ និងការផ្តល់សេវាសាធារណៈ",
                "scheduled"
            ),
            (
                "ពិធីប្រារព្ធទិវាបរិស្ថាន និងអនាម័យជនបទឃុំនគរភាស",
                "ceremony",
                "2026-09-10",
                "07:30",
                "11:00",
                "បរិវេណសាលាឃុំ និងភូមិគោកថ្មី",
                "លោក ឌី គន់ (មេឃុំ)",
                "អាជ្ញាធរឃុំ-ភូមិ លោកគ្រូ អ្នកគ្រូ សិស្សានុសិស្ស និងប្រជាពលរដ្ឋ",
                "យុទ្ធនាការដាំដើមឈើ និងសម្អាតបរិស្ថានសាធារណៈក្នុងឃុំ",
                "scheduled"
            )
        ]
        cursor.executemany("""
        INSERT INTO commune_events (
            title, event_type, event_date, start_time, end_time, location,
            chairperson, participants, description, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, sample_events)

    # Seed sample finance transactions if table is empty
    cursor.execute("SELECT COUNT(*) FROM finance_transactions")
    if cursor.fetchone()[0] == 0:
        sample_finance = [
            # Incomes (ចំណូល)
            ("INC-202606-001", "income", "commune_fund", "ថវិកាមូលនិធិឃុំពីរដ្ឋបាលថ្នាក់ជាតិ ត្រីមាសទី២", 18500000, "2026-06-10", "រតនាគារខេត្តសៀមរាប", "TR-77120", "bank_transfer", None, "ថវិកាគាំទ្ររដ្ឋបាល និងអភិវឌ្ឍន៍ឃុំ", "completed", 1),
            ("INC-202606-002", "income", "imprest_fund", "ដកប្រាក់រជ្ជទេយ្យបុរេប្រទានសម្រាប់ចំណាយរដ្ឋបាលប្រចាំខែមិថុនា", 1450000, "2026-06-28", "រជ្ជទេយ្យករបុរេប្រទានឃុំ", "REC-202606-01", "cash", None, "បុរេប្រទានចំណាយរដ្ឋបាលខែមិថុនា", "completed", 1),
            ("INC-202607-001", "income", "imprest_fund", "ដកប្រាក់រជ្ជទេយ្យបុរេប្រទានសម្រាប់ចំណាយរដ្ឋបាលប្រចាំខែកក្កដា", 1680000, "2026-07-28", "រជ្ជទេយ្យករបុរេប្រទានឃុំ", "REC-202607-01", "cash", None, "បុរេប្រទានចំណាយរដ្ឋបាលខែកក្កដា", "completed", 1),
            ("INC-202607-002", "income", "other_income", "ចំណូលផ្សេងៗ (លក់ដេញថ្លៃសម្ភារៈជួសជុលចាស់ៗ)", 3200000, "2026-07-15", "អ្នកទិញសម្ភារៈជួសជុល", "REC-202607-02", "bank_transfer", None, "ប្រាក់ចំណូលផ្សេងៗចូលមូលនិធិឃុំ", "completed", 1),
            ("INC-202608-001", "income", "imprest_fund", "ដកប្រាក់រជ្ជទេយ្យបុរេប្រទានសប្តាហ៍ទី១ សម្រាប់ចំណាយរដ្ឋបាល", 1500000, "2026-08-05", "រជ្ជទេយ្យករបុរេប្រទានឃុំ", "REC-202608-01", "cash", None, "បុរេប្រទានចំណាយរដ្ឋបាលសប្តាហ៍ទី១", "completed", 1),
            ("INC-202608-002", "income", "commune_fund", "ថវិកាមូលនិធិឃុំពីរដ្ឋបាលថ្នាក់ជាតិ ត្រីមាសទី៣", 18500000, "2026-08-10", "រតនាគារខេត្តសៀមរាប", "TR-88291", "bank_transfer", None, "ថវិកាគាំទ្ររដ្ឋបាល និងអភិវឌ្ឍន៍មូលដ្ឋាន", "completed", 1),
            ("INC-202608-003", "income", "other_income", "ចំណូលផ្សេងៗចូលមូលនិធិសង្គមកិច្ចឃុំ", 580000, "2026-08-15", "លោក អ៊ុំ ម៉ៅ (ភូមិគោកថ្មី)", "REC-202608-02", "aba", None, "ចំណូលផ្សេងៗចូលមូលនិធិឃុំ", "completed", 1),
            ("INC-202608-004", "income", "other_income", "ចំណូលផ្សេងៗពីការផ្ទេរប្រាក់ឧបត្ថម្ភ", 1200000, "2026-08-18", "គណៈកម្មការសហគមន៍", "REC-202608-03", "aba", None, "ចំណូលផ្សេងៗ", "completed", 1),
            ("INC-202608-005", "income", "imprest_fund", "ដកប្រាក់រជ្ជទេយ្យបុរេប្រទានសម្រាប់ចំណាយប្រតិបត្តិការឃុំ", 2000000, "2026-08-22", "រជ្ជទេយ្យករបុរេប្រទានឃុំ", "REC-202608-04", "cash", None, "បុរេប្រទានសាច់ប្រាក់ប្រចាំខែសីហា", "completed", 1),
            ("INC-202608-006", "income", "other_income", "ចំណូលផ្សេងៗបម្រើការងារសាលាឃុំ", 420000, "2026-08-25", "ប្រជាពលរដ្ឋក្នុងឃុំ", "REC-202608-05", "cash", None, "ចំណូលផ្សេងៗ", "completed", 1),

            # Expenses (ចំណាយ)
            ("EXP-202606-001", "expense", "administrative", "ទិញសម្ភារៈការិយាល័យ និងក្រដាសរដ្ឋបាលប្រចាំខែមិថុនា", 520000, "2026-06-08", "ហាងផ្គត់ផ្គង់សម្ភារៈអង្គរជុំ", "INV-0981", "cash", None, "ក្រដាស A4 ទឹកថ្នាំ និងសៀវភៅកត់ត្រា", "completed", 1),
            ("EXP-202606-002", "expense", "utility", "ទូទាត់ថ្លៃអគ្គិសនី និងទឹកស្អាតសាលាឃុំ ខែមិថុនា", 340000, "2026-06-12", "អគ្គិសនីកម្ពុជា & រដ្ឋាករទឹក", "EDC-3910", "aba", None, "ថ្លៃភ្លើង និងទឹកប្រើប្រាស់សាលាឃុំ", "completed", 1),
            ("EXP-202607-001", "expense", "maintenance", "ជួសជុលអណ្ដូងទឹកស្នប់ជូនប្រជាពលរដ្ឋភូមិសំបួរ និងភូមិកុក", 2800000, "2026-07-18", "ក្រុមជាងជួសជុលអណ្ដូង", "VOU-202607-01", "cash", None, "គម្រោងផ្គត់ផ្គង់ទឹកស្អាតជនបទ", "completed", 1),
            ("EXP-202607-002", "expense", "administrative", "ទិញសម្ភារៈការិយាល័យ និងទឹកថ្នាំព្រីនធ័រ", 460000, "2026-07-05", "ហាងផ្គត់ផ្គង់សម្ភារៈអង្គរជុំ", "INV-1032", "cash", None, "សម្ភារៈបម្រើការងាររដ្ឋបាល", "completed", 1),
            ("EXP-202608-001", "expense", "administrative", "ទិញសម្ភារៈការិយាល័យ ក្រដាស A4 ទឹកថ្នាំព្រីន និងសៀវភៅកត់ត្រា", 480000, "2026-08-04", "ហាងផ្គត់ផ្គង់សម្ភារៈអង្គរជុំ", "INV-1092", "cash", None, "សម្ភារៈរដ្ឋបាលសម្រាប់ត្រីមាសទី៣", "completed", 1),
            ("EXP-202608-002", "expense", "utility", "ទូទាត់ថ្លៃអគ្គិសនី និងទឹកស្អាតសាលាឃុំ ប្រចាំខែកក្កដា-សីហា", 360000, "2026-08-06", "អគ្គិសនីកម្ពុជា & រដ្ឋាករទឹក", "EDC-4819", "aba", None, "វិក្កយបត្រអគ្គិសនី និងទឹកស្អាត", "completed", 1),
            ("EXP-202608-003", "expense", "reception_event", "ចំណាយរៀបចំពិធីវេទិកាសាធារណៈភូមិល្បើក (ទឹកបរិសុទ្ធ និងអាហារសម្រន់)", 280000, "2026-08-14", "អ្នកស្រី សុខ ហៀង", "EXP-202608-01", "cash", None, "បដិសណ្ឋារកិច្ចវេទិកាប្រជាពលរដ្ឋ", "completed", 1),
            ("EXP-202608-004", "expense", "maintenance", "ចំណាយជួសជុលអំពូលសូឡាបំភ្លឺមុខសាលាឃុំ និងបរិក្ខារការិយាល័យ", 450000, "2026-08-16", "ជាង គឹម សារ៉េត", "REC-7731", "cash", None, "ជួសជុល និងប្តូរគ្រឿងបន្លាស់សូឡា", "completed", 1),
            ("EXP-202608-005", "expense", "mission_travel", "ទូទាត់ប្រាក់ឧបត្ថម្ភចុះបេសកកម្មត្រួតពិនិត្យផ្លូវលំជនបទ", 320000, "2026-08-21", "ក្រុមការងារបច្ចេកទេសឃុំ", "MIS-2026-08", "cash", None, "ចុះពិនិត្យស្ថានភាពផ្លូវលំភូមិពង្រ និងភូមិជំពូង", "completed", 1),
            ("EXP-202608-006", "expense", "administrative", "ទិញប្រេងឥន្ធនៈសម្រាប់ម៉ាស៊ីនភ្លើង និងម៉ូតូការងាររដ្ឋបាលឃុំ", 250000, "2026-08-25", "ស្ថានីយប្រេងឥន្ធនៈអង្គរជុំ", "PET-5501", "cash", None, "ប្រេងសាំង និងម៉ាស៊ូតសម្រាប់ដំណើរការការងាររដ្ឋបាល", "completed", 1)
        ]
        cursor.executemany("""
        INSERT INTO finance_transactions (
            transaction_code, type, category, title, amount, transaction_date,
            payer_payee, receipt_voucher_no, payment_method, attachment, notes, status, recorded_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, sample_finance)

    conn.commit()
    conn.close()


def reset_and_seed_data():
    """Reset database tables and seed fresh data with exact 10 villages"""
    conn = get_db()
    cursor = conn.cursor()

    tables = [
        "mission_participants", "missions", "leave_requests", "attendance",
        "documents", "payroll", "trainings", "achievements", "users",
        "staff", "villages"
    ]
    for t in tables:
        cursor.execute(f"DROP TABLE IF EXISTS {t}")
    conn.commit()
    conn.close()

    init_db()
    seed_data()


def seed_data():
    conn = get_db()
    cursor = conn.cursor()

    # Check if already seeded
    cursor.execute("SELECT COUNT(*) FROM staff")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return

    # 10 Villages of Nokor Pheas Commune (ភូមិទាំង ១០ ក្នុងឃុំនគរភាស ស្រុកអង្គរជុំ ខេត្តសៀមរាប)
    villages_data = [
        ("រមៀត", "Romeat", 850, 435, 190),
        ("ល្បើក", "Lbeuk", 720, 370, 160),
        ("សំបួរ", "Sambuor", 940, 480, 210),
        ("គោកថ្មី", "Kouk Thmei", 1120, 575, 245),
        ("ទន្លេស", "Tonle Sa", 890, 455, 195),
        ("កុក", "Kok", 680, 350, 150),
        ("ពង្រ", "Pongro", 910, 465, 200),
        ("នគរភាស១", "Nokor Pheas 1", 1250, 640, 280),
        ("នគរភាស២", "Nokor Pheas 2", 1180, 605, 260),
        ("ជំពូង", "Chumpoang", 790, 405, 175),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO villages (village_name_kh, village_name_en, total_population, female_population, total_families) VALUES (?, ?, ?, ?, ?)",
        villages_data
    )

    # Seed Staff members (មន្ត្រី និងបុគ្គលិកសាលាឃុំនគរភាស)
    staff_members = [
        # 1. ក្រុមប្រឹក្សាឃុំ (Commune Council)
        (
            "NP-001", "ស៊ូ វណ្ណា", "Sou Vanna", "ប្រុស", "1968-04-12", "040182910", "012 889 901",
            "vanna.sou@nokorpheas.gov.kh", "នគរភាស១", "council", "មេឃុំ", "Commune Chief",
            "នយោបាយ", "2022-07-01", None, 1450000, 250000, 100000, "បរិញ្ញាបត្ររដ្ឋបាលសាធារណៈ",
            "active", "ភរិយា៖ ០១២ ៤៤៥ ៦៦៧", "ប្រធានក្រុមប្រឹក្សាឃុំនគរភាស"
        ),
        (
            "NP-002", "កែវ សោភា", "Keo Sophea", "ស្រី", "1974-09-20", "040293841", "097 555 4321",
            "sophea.keo@nokorpheas.gov.kh", "រមៀត", "council", "ជំទប់ទី១", "1st Deputy Chief",
            "នយោបាយ", "2022-07-01", None, 1200000, 180000, 80000, "ទុតិយភូមិ",
            "active", "ស្វាមី៖ ០៩៧ ២២២ ៣៣៣", "ទទួលបន្ទុកសេដ្ឋកិច្ច និងសង្គមកិច្ច"
        ),
        (
            "NP-003", "ជុំ រដ្ឋា", "Chum Ratha", "ប្រុស", "1972-11-15", "040112233", "088 667 8899",
            "ratha.chum@nokorpheas.gov.kh", "ល្បើក", "council", "ជំទប់ទី២", "2nd Deputy Chief",
            "នយោបាយ", "2022-07-01", None, 1150000, 160000, 80000, "ទុតិយភូមិ",
            "active", "ភរិយា៖ ០៨៨ ៩៩៩ ៨៨៨", "ទទួលបន្ទុកសន្តិសុខ និងសណ្តាប់ធ្នាប់"
        ),
        (
            "NP-004", "អ៊ុំ សារ៉ន", "Oum Saron", "ស្រី", "1980-03-08", "040445566", "077 123 456",
            "saron.oum@nokorpheas.gov.kh", "សំបួរ", "council", "សមាជិកក្រុមប្រឹក្សាឃុំ", "Council Member",
            "នយោបាយ", "2022-07-01", None, 980000, 100000, 60000, "ទុតិយភូមិ",
            "active", "ស្វាមី៖ ០៧៧ ៦៥៤ ៣២១", "ប្រធានគណៈកម្មាធិការពិគ្រោះយោបល់កិច្ចការស្ត្រីនិងកុមារ (គ.ក.ស.ក)"
        ),
        (
            "NP-005", "ខៀវ វិបុល", "Khiev Vibol", "ប្រុស", "1978-06-25", "040778899", "092 345 678",
            "vibol.khiev@nokorpheas.gov.kh", "គោកថ្មី", "council", "សមាជិកក្រុមប្រឹក្សាឃុំ", "Council Member",
            "នយោបាយ", "2022-07-01", None, 980000, 100000, 60000, "ទុតិយភូមិ",
            "active", "ភរិយា៖ ០៩២ ៨៧៦ ៥៤៣", "សមាជិកគណៈកម្មាធិការរៀបចំផែនការថវិកាឃុំ"
        ),

        # 2. ស្មៀនឃុំ និងរដ្ឋបាល (Clerk & Administration)
        (
            "NP-006", "ហេង ចាន់រិទ្ធ", "Heng Chanrith", "ប្រុស", "1989-02-14", "040998877", "012 334 455",
            "chanrith.heng@nokorpheas.gov.kh", "នគរភាស១", "clerk", "ស្មៀនឃុំ", "Commune Clerk",
            "ក.៣ (ក្រសួងមហាផ្ទៃ)", "2018-03-15", None, 1350000, 200000, 100000, "បរិញ្ញាបត្រនីតិសាស្ត្រ",
            "active", "ភរិយា៖ ០១២ ៩៩៨ ៨៧៧", "ទទួលបន្ទុករដ្ឋបាល លិខិតបទដ្ឋាន និងការងារអត្រានុកូលដ្ឋាន"
        ),

        # 3. ជំនួយការឃុំ (Commune Assistants)
        (
            "NP-007", "លាង ស្រីម៉ៅ", "Leang Sreymao", "ស្រី", "1997-08-22", "040556677", "096 789 0123",
            "sreymao.leang@nokorpheas.gov.kh", "ទន្លេស", "contract", "ជំនួយការហិរញ្ញវត្ថុ និងគណនេយ្យ", "Finance Assistant",
            "កិច្ចសន្យា", "2023-01-01", "2026-12-31", 850000, 80000, 40000, "បរិញ្ញាបត្រគណនេយ្យ",
            "active", "ម្តាយ៖ ០៩៦ ១១១ ២២២", "គ្រប់គ្រងបញ្ជីចំណូល-ចំណាយ និងរបាយការណ៍ហិរញ្ញវត្ថុឃុំ"
        ),
        (
            "NP-008", "សេង ដារ៉ា", "Seng Dara", "ប្រុស", "1998-12-05", "040332211", "086 456 789",
            "dara.seng@nokorpheas.gov.kh", "កុក", "contract", "មន្ត្រីបច្ចេកវិទ្យា និងច្រកចេញចូលតែមួយ", "IT & One-Window Officer",
            "កិច្ចសន្យា", "2023-05-01", "2026-12-31", 850000, 80000, 40000, "បរិញ្ញាបត្រវិទ្យាសាស្ត្រកុំព្យូទ័រ",
            "active", "បងប្រុស៖ ០៨៦ ០០០ ១១១", "ទទួលបន្ទុកប្រព័ន្ធទិន្នន័យឃុំ និងបម្រើសេវាសាធារណៈ"
        ),
        (
            "NP-009", "ចាន់ ធារ៉ា", "Chan Theara", "ស្រី", "2000-05-18", "040667788", "087 654 321",
            "theara.chan@nokorpheas.gov.kh", "ពង្រ", "contract", "ជំនួយការរដ្ឋបាល និងកត់ត្រា", "Admin Assistant",
            "កិច្ចសន្យា", "2024-02-01", "2026-12-31", 800000, 60000, 40000, "បរិញ្ញាបត្ររងរដ្ឋបាល",
            "active", "ឪពុក៖ ០៨៧ ៣៣៣ ៤៤៤", "ទទួលបន្ទុកកិច្ចការលិខិតស្នាម និងប័ណ្ណសារ"
        ),

        # 4. មន្ត្រីភូមិ (Village Chiefs of all 10 Villages)
        (
            "NP-010", "ព្រំ សុខា", "Prom Sokha", "ប្រុស", "1965-01-10", "040111222", "011 223 344",
            "sokha.prom@nokorpheas.gov.kh", "រមៀត", "village", "មេភូមិរមៀត", "Romeat Village Chief",
            "ថ្នាក់ភូមិ", "2017-06-01", None, 500000, 50000, 30000, "បឋមភូមិ",
            "active", "កូនប្រុស៖ ០១១ ៩៩៩ ៨៨៨", "គ្រប់គ្រងសន្តិសុខ និងកិច្ចការអភិវឌ្ឍន៍ភូមិរមៀត"
        ),
        (
            "NP-011", "ស៊្រុន ម៉ៅ", "Srun Mao", "ប្រុស", "1970-07-14", "040222333", "012 334 999",
            "mao.srun@nokorpheas.gov.kh", "ល្បើក", "village", "មេភូមិល្បើក", "Lbeuk Village Chief",
            "ថ្នាក់ភូមិ", "2017-06-01", None, 500000, 50000, 30000, "បឋមភូមិ",
            "active", "ភរិយា៖ ០១២ ៧៧៧ ៦៦៦", "គ្រប់គ្រងសន្តិសុខ និងកិច្ចការអភិវឌ្ឍន៍ភូមិល្បើក"
        ),
        (
            "NP-012", "យន់ វ៉ាន់នី", "Yorn Vanny", "ស្រី", "1976-10-30", "040333444", "097 445 6677",
            "vanny.yorn@nokorpheas.gov.kh", "សំបួរ", "village", "មេភូមិសំបួរ", "Sambuor Village Chief",
            "ថ្នាក់ភូមិ", "2019-02-15", None, 500000, 50000, 30000, "ទុតិយភូមិ",
            "active", "ស្វាមី៖ ០៩៧ ៨៨៨ ៩៩៩", "គ្រប់គ្រងសន្តិសុខ និងកិច្ចការអភិវឌ្ឍន៍ភូមិសំបួរ"
        ),
        (
            "NP-013", "តន់ វិជ្ជា", "Ton Vichea", "ប្រុស", "1982-04-05", "040444555", "088 112 2334",
            "vichea.ton@nokorpheas.gov.kh", "គោកថ្មី", "village", "មេភូមិគោកថ្មី", "Kouk Thmei Village Chief",
            "ថ្នាក់ភូមិ", "2020-08-01", None, 500000, 50000, 30000, "បឋមភូមិ",
            "active", "ភរិយា៖ ០៨៨ ៣៣៣ ២២២", "គ្រប់គ្រងសន្តិសុខ និងកិច្ចការអភិវឌ្ឍន៍ភូមិគោកថ្មី"
        ),
        (
            "NP-014", "ឌៀប វណ្ណារ៉ា", "Diep Vannara", "ប្រុស", "1973-12-19", "040555666", "078 990 011",
            "vannara.diep@nokorpheas.gov.kh", "ទន្លេស", "village", "មេភូមិទន្លេស", "Tonle Sa Village Chief",
            "ថ្នាក់ភូមិ", "2018-05-10", None, 500000, 50000, 30000, "បឋមភូមិ",
            "active", "ភរិយា៖ ០៧៨ ៥៥៥ ៤៤៤", "គ្រប់គ្រងសន្តិសុខ និងកិច្ចការអភិវឌ្ឍន៍ភូមិទន្លេស"
        ),
        (
            "NP-015", "ប៉ូច សារ៉េត", "Pouch Sareth", "ប្រុស", "1979-09-02", "040666777", "092 110 022",
            "sareth.pouch@nokorpheas.gov.kh", "កុក", "village", "មេភូមិកុក", "Kok Village Chief",
            "ថ្នាក់ភូមិ", "2019-11-20", None, 500000, 50000, 30000, "បឋមភូមិ",
            "active", "ភរិយា៖ ០៩២ ៦៦៦ ៧៧៧", "គ្រប់គ្រងសន្តិសុខ និងកិច្ចការអភិវឌ្ឍន៍ភូមិកុក"
        ),
        (
            "NP-016", "ម៉ៅ គឹមឡុង", "Mao Kimlong", "ប្រុស", "1984-02-28", "040777888", "096 332 2110",
            "kimlong.mao@nokorpheas.gov.kh", "ពង្រ", "village", "មេភូមិពង្រ", "Pongro Village Chief",
            "ថ្នាក់ភូមិ", "2021-03-01", None, 500000, 50000, 30000, "ទុតិយភូមិ",
            "active", "ភរិយា៖ ០៩៦ ៧៧៧ ៨៨៨", "គ្រប់គ្រងសន្តិសុខ និងកិច្ចការអភិវឌ្ឍន៍ភូមិពង្រ"
        ),
        (
            "NP-017", "ឈិន សុខន", "Chhin Sokhon", "ប្រុស", "1975-08-15", "040888999", "087 221 100",
            "sokhon.chhin@nokorpheas.gov.kh", "នគរភាស១", "village", "មេភូមិនគរភាស១", "Nokor Pheas 1 Village Chief",
            "ថ្នាក់ភូមិ", "2018-09-12", None, 500000, 50000, 30000, "បឋមភូមិ",
            "active", "ភរិយា៖ ០៨៧ ៤៤៤ ៥៥៥", "គ្រប់គ្រងសន្តិសុខ និងកិច្ចការអភិវឌ្ឍន៍ភូមិនគរភាស១"
        ),
        (
            "NP-018", "សោម ចិន្តា", "Som Chenda", "ស្រី", "1981-05-12", "040999000", "097 665 4321",
            "chenda.som@nokorpheas.gov.kh", "នគរភាស២", "village", "មេភូមិនគរភាស២", "Nokor Pheas 2 Village Chief",
            "ថ្នាក់ភូមិ", "2020-01-10", None, 500000, 50000, 30000, "ទុតិយភូមិ",
            "active", "ស្វាមី៖ ០៩៧ ៩៩៨ ៨៧៧", "គ្រប់គ្រងសន្តិសុខ និងកិច្ចការអភិវឌ្ឍន៍ភូមិនគរភាស២"
        ),
        (
            "NP-019", "អ៊ុំ សារ៉េន", "Oum Saren", "ប្រុស", "1977-11-25", "040333222", "088 554 4332",
            "saren.oum@nokorpheas.gov.kh", "ជំពូង", "village", "មេភូមិជំពូង", "Chumpoang Village Chief",
            "ថ្នាក់ភូមិ", "2019-07-15", None, 500000, 50000, 30000, "បឋមភូមិ",
            "active", "ភរិយា៖ ០៨៨ ១១២ ៣៣៤", "គ្រប់គ្រងសន្តិសុខ និងកិច្ចការអភិវឌ្ឍន៍ភូមិជំពូង"
        )
    ]

    cursor.executemany("""
    INSERT INTO staff (
        officer_code, name_kh, name_en, gender, dob, national_id, phone, email,
        village, category, position_title_kh, position_title_en, cadre_level,
        appointment_date, contract_end_date, base_salary, position_allowance,
        family_allowance, education_level, status, emergency_contact, notes
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, staff_members)

    # Fetch inserted staff for mapping
    cursor.execute("SELECT id, officer_code, name_kh, category FROM staff")
    staff_rows = cursor.fetchall()
    staff_map = {row["officer_code"]: row["id"] for row in staff_rows}

    # Seed User Accounts
    users_data = [
        ("admin", generate_password_hash("admin123"), "ស៊ូ វណ្ណា (មេឃុំ)", "admin", staff_map.get("NP-001")),
        ("clerk", generate_password_hash("clerk123"), "ហេង ចាន់រិទ្ធ (ស្មៀនឃុំ)", "clerk", staff_map.get("NP-006")),
        ("it_admin", generate_password_hash("it123"), "សេង ដារ៉ា (មន្ត្រី IT)", "admin", staff_map.get("NP-008")),
        ("staff", generate_password_hash("staff123"), "លាង ស្រីម៉ៅ (ជំនួយការឃុំ)", "staff", staff_map.get("NP-007")),
        ("village_chief", generate_password_hash("village123"), "ព្រំ សុខា (មេភូមិរមៀត)", "staff", staff_map.get("NP-010")),
    ]
    cursor.executemany("""
    INSERT INTO users (username, password_hash, full_name, role, staff_id)
    VALUES (?, ?, ?, ?, ?)
    """, users_data)

    # Seed Sample Documents for Staff
    sample_docs = [
        (staff_map["NP-001"], "appointment_deka", "ដីកាស្ដីពីការទទួលស្គាល់សមាសភាពក្រុមប្រឹក្សាឃុំនគរភាស", "deika_np_001.pdf", "/static/uploads/deika_np_001.pdf", 524288, "ចេញដោយក្រសួងមហាផ្ទៃ"),
        (staff_map["NP-001"], "cv", "ជីវប្រវត្តិសង្ខេបលោក ស៊ូ វណ្ណា", "cv_sou_vanna.pdf", "/static/uploads/cv_sou_vanna.pdf", 262144, "ប្រវត្តិរូបសង្ខេបផ្លូវការ"),
        (staff_map["NP-006"], "appointment_deka", "ប្រកាសស្ដីពីការតែងតាំងស្មៀនឃុំនគរភាស", "prakas_clerk_heng.pdf", "/static/uploads/prakas_clerk_heng.pdf", 450000, "ចេញដោយក្រសួងមហាផ្ទៃ"),
        (staff_map["NP-006"], "degree_certificate", "សញ្ញាបត្របរិញ្ញាបត្រនីតិសាស្ត្រ", "degree_law_heng.pdf", "/static/uploads/degree_law_heng.pdf", 780000, "សាកលវិទ្យាល័យភូមិន្ទនីតិសាស្ត្រ និងវិទ្យាសាស្ត្រសេដ្ឋកិច្ច"),
        (staff_map["NP-007"], "contract", "កិច្ចសន្យាការងារមន្ត្រីជំនួយការហិរញ្ញវត្ថុ ឆ្នាំ២០២៦", "contract_finance_2026.pdf", "/static/uploads/contract_finance_2026.pdf", 320000, "កិច្ចសន្យាការងារប្រចាំឆ្នាំ"),
        (staff_map["NP-008"], "contract", "កិច្ចសន្យាការងារមន្ត្រីព័ត៌មានវិទ្យា និងច្រកចេញចូលតែមួយ", "contract_it_2026.pdf", "/static/uploads/contract_it_2026.pdf", 310000, "កិច្ចសន្យាការងារប្រចាំឆ្នាំ"),
    ]
    cursor.executemany("""
    INSERT INTO documents (staff_id, doc_type, title, filename, file_path, file_size, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, sample_docs)

    # Seed Sample Attendance (Current Month: 2026-08)
    today = date.today()
    for i in range(1, 15):
        day_date = date(today.year, today.month, min(i, 28))
        if day_date.weekday() >= 5:  # Skip weekends
            continue
        date_str = day_date.strftime("%Y-%m-%d")

        for s_code, s_id in staff_map.items():
            if s_code in ["NP-001", "NP-002", "NP-003", "NP-006", "NP-007", "NP-008", "NP-009"]:
                # Commune hall daily officers
                status = "present"
                check_in = "07:45"
                check_out = "17:05"
                if i == 5 and s_code == "NP-008":
                    status = "late"
                    check_in = "08:15"
                elif i == 8 and s_code == "NP-007":
                    status = "on_leave"
                    check_in = None
                    check_out = None

                cursor.execute("""
                INSERT OR IGNORE INTO attendance (staff_id, date, check_in_time, check_out_time, status, remarks)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (s_id, date_str, check_in, check_out, status, "វត្តមានធម្មតា" if status == "present" else "មកយឺតដោយសារភ្លៀង" if status == "late" else "ច្បាប់ឈឺ"))

    # Seed Sample Leave Requests
    leave_data = [
        (staff_map["NP-007"], "sick", "2026-08-08", "2026-08-09", 2, "មានអាការៈក្តៅខ្លួន និងផ្តាសាយធ្ងន់ធ្ងរ", "approved", staff_map["NP-001"], "អនុញ្ញាតច្បាប់ឈឺ ២ ថ្ងៃ", "2026-08-07 16:00:00"),
        (staff_map["NP-008"], "personal", "2026-08-25", "2026-08-26", 2, "ចូលរួមពិធីអាពាហ៍ពិពាហ៍បងប្អូនជីដូនមួយនៅខេត្តបាត់ដំបង", "pending", None, None, None),
        (staff_map["NP-004"], "annual", "2026-09-01", "2026-09-05", 5, "សម្រាកលំហែកាយប្រចាំឆ្នាំជាមួយគ្រួសារ", "pending", None, None, None),
    ]
    cursor.executemany("""
    INSERT INTO leave_requests (staff_id, leave_type, start_date, end_date, total_days, reason, status, approved_by, approval_remarks, approved_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, leave_data)

    # Seed Sample Missions (បេសកកម្ម)
    mission_data = [
        (
            "MS-2026-001", "ចុះផ្សព្វផ្សាយការចុះបញ្ជីអត្រានុកូលដ្ឋាន និងអត្តសញ្ញាណប័ណ្ណ",
            "ភូមិរមៀត និង ភូមិគោកថ្មី", "2026-08-04", "2026-08-05", 2, "លប.០១២/២៦",
            "ចុះជំរុញការចុះបញ្ជីសំបុត្រកំណើត និងអត្តសញ្ញាណប័ណ្ណជូនប្រជាពលរដ្ឋ", 50000, 100000, "completed", 1
        ),
        (
            "MS-2026-002", "ចូលរួមសិក្ខាសាលាពិគ្រោះយោបល់ថ្នាក់ស្រុកស្ដីពីផែនការវិនិយោគឃុំ",
            "សាលាស្រុកអង្គរជុំ ខេត្តសៀមរាប", "2026-08-11", "2026-08-11", 1, "លប.០១៥/២៦",
            "ចូលរួមប្រជុំពិភាក្សាលើគម្រោងអភិវឌ្ឍន៍ផ្លូវលំជនបទ និងប្រព័ន្ធធារាសាស្ត្រ", 60000, 60000, "completed", 1
        ),
        (
            "MS-2026-003", "ចុះត្រួតពិនិត្យការដ្ឋានសាងសង់ទំនប់ទឹក និងប្រឡាយមេ",
            "ភូមិទន្លេស និង ភូមិសំបួរ", "2026-08-18", "2026-08-19", 2, "លប.០១៨/២៦",
            "ពិនិត្យគុណភាព និងវឌ្ឍនភាពការស្ថាបនាទំនប់ទឹកតាមផែនការឃុំ", 50000, 100000, "completed", 1
        )
    ]
    cursor.executemany("""
    INSERT INTO missions (mission_code, title, destination, start_date, end_date, total_days, mission_order_no, purpose, allowance_per_day, total_allowance, status, created_by)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, mission_data)

    # Mission participants
    cursor.execute("SELECT id, mission_code FROM missions")
    mission_rows = cursor.fetchall()
    m_map = {row["mission_code"]: row["id"] for row in mission_rows}

    mission_parts = [
        (m_map["MS-2026-001"], staff_map["NP-001"], "ប្រធានក្រុមការងារ", 50000),
        (m_map["MS-2026-001"], staff_map["NP-006"], "សមាជិក/កត់ត្រា", 50000),
        (m_map["MS-2026-002"], staff_map["NP-001"], "តំណាងរដ្ឋបាលឃុំ", 60000),
        (m_map["MS-2026-002"], staff_map["NP-002"], "សមាជិកចូលរួម", 60000),
        (m_map["MS-2026-002"], staff_map["NP-006"], "សមាជិកចូលរួម", 60000),
        (m_map["MS-2026-003"], staff_map["NP-003"], "ប្រធានក្រុមចុះពិនិត្យ", 50000),
        (m_map["MS-2026-003"], staff_map["NP-008"], "ជំនួយការបច្ចេកទេស", 50000),
    ]
    cursor.executemany("""
    INSERT INTO mission_participants (mission_id, staff_id, role_in_mission, allowance)
    VALUES (?, ?, ?, ?)
    """, mission_parts)

    # Seed Sample Payroll for months 2026-04 (ចូលឆ្នាំ), 2026-08 (ធម្មតា), 2026-10 (ភ្ជុំបិណ្ឌ)
    for m_str in ["2026-04", "2026-08", "2026-10"]:
        m_num = m_str.split("-")[1]
        for s_code, s_id in staff_map.items():
            cursor.execute("SELECT base_salary, position_allowance, family_allowance FROM staff WHERE id = ?", (s_id,))
            staff_info = cursor.fetchone()
            base = staff_info["base_salary"] or 0
            
            # ប្រាក់ឧបត្ថម្ភចូលឆ្នាំ៖ បើកតែខែមេសា (04)
            pos_all = (staff_info["position_allowance"] or 0) if m_num == "04" else 0
            
            # ប្រាក់ឧបត្ថម្ភភ្ជុំបិណ្ឌ៖ បើកតែខែតុលា (10)
            fam_all = (staff_info["family_allowance"] or 0) if m_num == "10" else 0

            gross = base + pos_all + fam_all
            nssf = round(base * 0.02)  # 2% NSSF
            net = gross - nssf

            remark_text = f"ទូទាត់ប្រាក់បៀវត្សរ៍ខែ {m_str}"
            if m_num == "04":
                remark_text = f"ទូទាត់ប្រាក់បៀវត្សរ៍ និងប្រាក់ឧបត្ថម្ភចូលឆ្នាំ ({m_str})"
            elif m_num == "10":
                remark_text = f"ទូទាត់ប្រាក់បៀវត្សរ៍ និងប្រាក់ឧបត្ថម្ភភ្ជុំបិណ្ឌ ({m_str})"

            cursor.execute("""
            INSERT OR IGNORE INTO payroll (
                staff_id, month_year, base_salary, position_allowance, mission_allowance,
                meeting_allowance, incentive_allowance, family_allowance, gross_salary,
                nssf_deduction, attendance_deduction, tax_deduction, net_salary,
                payment_status, paid_date, payment_method, remarks
            ) VALUES (?, ?, ?, ?, 0, 0, 0, ?, ?, ?, 0, 0, ?, 'paid', ?, 'Wing', ?)
            """, (
                s_id, m_str, base, pos_all, fam_all,
                gross, nssf, net, f"{m_str}-25", remark_text
            ))

    # Seed Trainings (វគ្គបណ្តុះបណ្តាល)
    trainings_data = [
        (staff_map["NP-006"], "ការគ្រប់គ្រងរដ្ឋបាល និងអត្រានុកូលដ្ឋានតាមប្រព័ន្ធឌីជីថល (CRVS)", "ក្រសួងមហាផ្ទៃ សហការជាមួយ NCDD", "2025-06-10", "2025-06-14", 5, "សាលាខេត្តសៀមរាប", "វិញ្ញាបនបត្របញ្ជាក់ការសិក្សា", "completed", "វគ្គបំប៉នសមត្ថភាពស្មៀនឃុំ"),
        (staff_map["NP-008"], "ប្រព័ន្ធគ្រប់គ្រងទិន្នន័យភូមិ-ឃុំ និងច្រកចេញចូលតែមួយ (OWSO)", "គណៈកម្មាធិការជាតិសម្រាប់ការអភិវឌ្ឍតាមបែបប្រជាធិបតេយ្យនៅថ្នាក់ក្រោមជាតិ (NCDD)", "2025-09-01", "2025-09-03", 3, "សាលាស្រុកអង្គរជុំ", "លិខិតបញ្ជាក់ការចូលរួម", "completed", "ទទួលបានចំណេះដឹងផ្នែករដ្ឋបាលឌីជីថល"),
        (staff_map["NP-007"], "ការរៀបចំថវិកាកម្មវិធី និងគណនេយ្យភាពហិរញ្ញវត្ថុឃុំ", "មន្ទីរសេដ្ឋកិច្ច និងហិរញ្ញវត្ថុខេត្តសៀមរាប", "2025-11-05", "2025-11-07", 3, "សាលាខេត្តសៀមរាប", "វិញ្ញាបនបត្រគណនេយ្យរដ្ឋបាល", "completed", "វគ្គពង្រឹងជំនាញគណនេយ្យឃុំ"),
        (staff_map["NP-001"], "ភាពជាអ្នកដឹកនាំ និងអភិបាលកិច្ចមូលដ្ឋានល្អ", "វិទ្យាស្ថានជាតិរដ្ឋបាល (NAS)", "2024-08-15", "2024-08-19", 5, "រាជធានីភ្នំពេញ", "វិញ្ញាបនបត្រភាពជាអ្នកដឹកនាំរដ្ឋបាល", "completed", "សម្រាប់ថ្នាក់ដឹកនាំក្រុមប្រឹក្សាឃុំ-សង្កាត់")
    ]
    cursor.executemany("""
    INSERT INTO trainings (staff_id, course_title, organizer, start_date, end_date, duration_days, location, certificate_title, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, trainings_data)

    # Seed Achievements & Medals (ស្នាដៃ និងគ្រឿងឥស្សរិយយស)
    achievements_data = [
        (staff_map["NP-001"], "royal_order", "មេដាយប្រាក់ការងារ", "រាជរដ្ឋាភិបាលកម្ពុជា", "ព្រះរាជក្រឹត្យលេខ នស/រកត/១២២២/១០៨", "2023-01-15", "ស្នាដៃឆ្នើមក្នុងការដឹកនាំ និងកសាងសមិទ្ធផលក្នុងឃុំនគរភាស"),
        (staff_map["NP-006"], "certificate_of_appreciation", "ប័ណ្ណសរសើរការងាររដ្ឋបាលគំរូ", "អភិបាលនៃគណៈអភិបាលខេត្តសៀមរាប", "លិខិតលេខ ៤៥២/២៣ លស.សរ", "2024-03-20", "បំពេញការងារស្មៀនឃុំបានល្អប្រសើរ គ្មានភាពយឺតយ៉ាវជូនប្រជាពលរដ្ឋ"),
        (staff_map["NP-010"], "letter_of_praise", "លិខិតសរសើរភូមិគំរូលើការងារសន្តិសុខ-សណ្តាប់ធ្នាប់", "អភិបាលនៃគណៈអភិបាលស្រុកអង្គរជុំ", "លិខិតលេខ ០៨៩/២៤ សស.អជ", "2024-07-10", "ដឹកនាំភូមិរមៀតអនុវត្តគោលនយោបាយភូមិ-ឃុំមានសុវត្ថិភាពជាប់ចំណាត់ថ្នាក់លេខ១")
    ]
    cursor.executemany("""
    INSERT INTO achievements (staff_id, honor_type, title, awarded_by, decree_prakas_no, award_date, description)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, achievements_data)

    conn.commit()
    conn.close()
    print("Database successfully initialized and seeded with Nokor Pheas Commune 10 villages data!")


if __name__ == "__main__":
    reset_and_seed_data()
