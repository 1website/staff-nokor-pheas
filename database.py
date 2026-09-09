"""
Database Initialization and Seed Data for Nokor Pheas Commune Staff Management System
(ប្រព័ន្ធគ្រប់គ្រងបុគ្គលិករដ្ឋបាលឃុំនគរភាស ស្រុកអង្គរជុំ ខេត្តសៀមរាប)
Optimized for high-concurrency serverless performance and connection reuse.
"""

import os
import re
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

# Precomputed standard password hashes for instant zero-CPU startup
PRECOMPUTED_USER_HASHES = {
    "admin": "scrypt:32768:8:1$GLepOfOiJYkRrfq6$ec4e634a39fda35c2ba257b048af73424bc1dedc01ee242568508b4e18dd42ff9c128883439cc232ffec1b6fac730c6b7665781168c7fa883b618b4bd8582984",  # admin123
    "clerk": "scrypt:32768:8:1$otPMOcvJ6cCzMc8C$40d64a239b3d79d9f2ef2b322b28858102d80d2b697e0c82db168c188217d285fa12e1f8d6c40a5d36f44605ec6ee51d5c373ffe58e3b21e814587b2f5cfa990",  # clerk123
    "it_admin": "scrypt:32768:8:1$c4CqU6v0YCgLAIwL$175599774948f0365bf2c0ea61205ab11dc2a91d8fa661bcb584c13aea71b133642e2af5b5f5ff890ba0d35d49794c73e2711d2c90c6a0bbbc2633ef4923e043",  # it123
    "staff": "scrypt:32768:8:1$wNgB0aaTmDN1hk3H$a34a4deb95f7006962d33199b319b4b319fac2ffbc6c9932b3e4a83b3f876bb26b09e35531ed2193986b54b13c59acaf5535db35bd5d30b4d1d29b722e007367",  # staff123
    "village_chief": "scrypt:32768:8:1$RDWrj5Bqwb3Fwy3V$bfbd35e6fe20ff4fbf2aebcac944ba65e2b516499818a8469deffcfa20a396c987d87941865583b22ca3e312130c79cade5ee88fedb5c010328c4e54e587fd96"  # village123
}


class PgRow(dict):
    """Row wrapper allowing dict key, attribute, and integer index access like sqlite3.Row"""
    def __init__(self, cols, vals):
        vals_list = list(vals) if not isinstance(vals, list) else vals
        super().__init__(zip(cols, vals_list))
        self._vals = vals_list

    def __getitem__(self, key):
        if isinstance(key, int):
            if 0 <= key < len(self._vals):
                return self._vals[key]
            raise IndexError(f"Tuple index out of range: {key} (length is {len(self._vals)})")
        return super().__getitem__(key)

    def __getattr__(self, key):
        if key in self:
            return self[key]
        raise AttributeError(f"'PgRow' object has no attribute '{key}'")

    def get(self, key, default=None):
        if isinstance(key, int):
            if 0 <= key < len(self._vals):
                return self._vals[key]
            return default
        return super().get(key, default)


class PostgresCursorWrapper:
    def __init__(self, raw_cursor, is_pg8000=False):
        self.cur = raw_cursor
        self.is_pg8000 = is_pg8000
        self.lastrowid = None

    def _transform_query(self, query):
        if not self.is_pg8000:
            # psycopg2 treats % as format specifiers, so literal % must be escaped to %% before converting ? to %s
            pg_query = query.replace("%", "%%").replace("?", "%s")
        else:
            pg_query = query.replace("?", "%s")
            
        pg_query = pg_query.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        
        # Translate SQLite "INSERT OR IGNORE INTO ..." to PostgreSQL "INSERT INTO ... ON CONFLICT DO NOTHING"
        if "INSERT OR IGNORE INTO" in pg_query.upper():
            idx = pg_query.upper().find("INSERT OR IGNORE INTO")
            pg_query = pg_query[:idx] + "INSERT INTO" + pg_query[idx + len("INSERT OR IGNORE INTO"):]
            if "ON CONFLICT" not in pg_query.upper():
                pg_query = pg_query.rstrip("; \n\r\t") + " ON CONFLICT DO NOTHING"

        # Translate SQLite last_insert_rowid() to the captured lastrowid
        if "LAST_INSERT_ROWID()" in pg_query.upper():
            last_id = self.lastrowid if self.lastrowid is not None else 0
            pg_query = re.sub(r'(?i)\blast_insert_rowid\(\)', str(last_id), pg_query)

        return pg_query

    def execute(self, query, params=None):
        pg_query = self._transform_query(query)
        
        trimmed = pg_query.strip()
        is_insert = trimmed.upper().startswith("INSERT INTO")
        if is_insert and "RETURNING" not in trimmed.upper() and "ON CONFLICT DO NOTHING" not in trimmed.upper():
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
        pg_query = self._transform_query(query)
        return self.cur.executemany(pg_query, params_seq)

    def _wrap_row(self, row):
        if row is None:
            return None
        if not self.cur.description:
            return row
        if isinstance(row, PgRow):
            return row
        cols = [d[0] for d in self.cur.description]
        if hasattr(row, 'values') and callable(getattr(row, 'values')):
            return PgRow(cols, list(row.values()))
        return PgRow(cols, list(row))

    def fetchone(self):
        row = self.cur.fetchone()
        return self._wrap_row(row)

    def fetchall(self):
        rows = self.cur.fetchall()
        if not rows:
            return []
        if not self.cur.description:
            return rows
        cols = [d[0] for d in self.cur.description]
        result = []
        for r in rows:
            if isinstance(r, PgRow):
                result.append(r)
            elif hasattr(r, 'values') and callable(getattr(r, 'values')):
                result.append(PgRow(cols, list(r.values())))
            else:
                result.append(PgRow(cols, list(r)))
        return result

    def fetchmany(self, size=None):
        rows = self.cur.fetchmany(size) if size else self.cur.fetchmany()
        if not rows:
            return []
        if not self.cur.description:
            return rows
        cols = [d[0] for d in self.cur.description]
        result = []
        for r in rows:
            if isinstance(r, PgRow):
                result.append(r)
            elif hasattr(r, 'values') and callable(getattr(r, 'values')):
                result.append(PgRow(cols, list(r.values())))
            else:
                result.append(PgRow(cols, list(r)))
        return result

    @property
    def rowcount(self):
        return self.cur.rowcount

    @property
    def description(self):
        return self.cur.description

    def close(self):
        try:
            return self.cur.close()
        except Exception:
            pass


class PostgresConnectionWrapper:
    def __init__(self, raw_conn, is_pg8000=False):
        self.conn = raw_conn
        self.is_pg8000 = is_pg8000

    def cursor(self):
        if self.is_pg8000:
            return PostgresCursorWrapper(self.conn.cursor(), is_pg8000=True)
        else:
            import psycopg2.extras
            return PostgresCursorWrapper(self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor), is_pg8000=False)

    def commit(self):
        return self.conn.commit()

    def rollback(self):
        return self.conn.rollback()

    def close(self):
        # In Flask request context, keep connection open until teardown
        try:
            from flask import g, has_request_context
            if has_request_context() and getattr(g, 'db', None) is self:
                return
        except ImportError:
            pass
        self._real_close()

    def _real_close(self):
        try:
            self.conn.close()
        except Exception:
            pass

    def execute(self, query, params=None):
        cur = self.cursor()
        return cur.execute(query, params)


class SqliteConnectionWrapper:
    def __init__(self, raw_conn):
        self._conn = raw_conn

    def cursor(self):
        return self._conn.cursor()

    def execute(self, *args, **kwargs):
        return self._conn.execute(*args, **kwargs)

    def executemany(self, *args, **kwargs):
        return self._conn.executemany(*args, **kwargs)

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        # In Flask request context, keep connection open until teardown
        try:
            from flask import g, has_request_context
            if has_request_context() and getattr(g, 'db', None) is self:
                return
        except ImportError:
            pass
        self._real_close()

    def _real_close(self):
        try:
            self._conn.close()
        except Exception:
            pass

    def __getattr__(self, name):
        return getattr(self._conn, name)


def _raw_create_connection():
    """Create a raw underlying database connection (PostgreSQL or SQLite)."""
    if DATABASE_URL:
        # Priority 1: psycopg2 (5x-10x faster C-extension)
        try:
            import psycopg2
            import psycopg2.extras
            url = DATABASE_URL.strip()
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)
            raw_conn = psycopg2.connect(url, sslmode="require", connect_timeout=5)
            raw_conn.autocommit = True
            return PostgresConnectionWrapper(raw_conn, is_pg8000=False)
        except Exception as e_psycopg:
            # Priority 2: pure Python pg8000 fallback
            try:
                import ssl
                from urllib.parse import urlparse
                import pg8000.dbapi
                
                parsed = urlparse(DATABASE_URL.strip())
                ssl_ctx = ssl.create_default_context()
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl.CERT_NONE
                
                conn = pg8000.dbapi.connect(
                    user=parsed.username,
                    password=parsed.password,
                    host=parsed.hostname,
                    port=parsed.port or 5432,
                    database=parsed.path.lstrip("/"),
                    ssl_context=ssl_ctx,
                    timeout=5
                )
                conn.autocommit = True
                return PostgresConnectionWrapper(conn, is_pg8000=True)
            except Exception as e_pg8000:
                print(f"[DB Warning] Cloud PostgreSQL connect failed: {e_pg8000}. Using SQLite fallback.")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA cache_size = -64000")
    return SqliteConnectionWrapper(conn)


_DB_SCHEMA_INITIALIZED = False

def get_db():
    """Returns request-scoped DB connection if within Flask request, else creates new connection."""
    global _DB_SCHEMA_INITIALIZED
    conn = None
    try:
        from flask import g, has_request_context
        if has_request_context():
            if not hasattr(g, 'db') or g.db is None:
                g.db = _raw_create_connection()
            conn = g.db
    except ImportError:
        pass
    
    if conn is None:
        conn = _raw_create_connection()

    if not _DB_SCHEMA_INITIALIZED:
        _DB_SCHEMA_INITIALIZED = True
        try:
            init_db(conn)
        except Exception as e:
            print(f"[Auto Schema Init Notice] {e}")

    return conn


def close_db_connection(e=None):
    """Closes the request-scoped DB connection during Flask app teardown."""
    try:
        from flask import g, has_request_context
        if has_request_context():
            db = getattr(g, 'db', None)
            if db is not None:
                g.db = None
                db._real_close()
    except ImportError:
        pass


def init_db(conn=None):
    if conn is None:
        conn = get_db()
    cursor = conn.cursor()

    # 1. Villages Table (បញ្ជីភូមិក្នុងឃុំនគរភាស - No Foreign Keys)
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

    # 2. Staff Table (ព័ត៌មានមន្ត្រី និងបុគ្គលិក - Primary entity)
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

    # 3. Users Table (គណនីប្រើប្រាស់ - References staff)
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

    # 4. Documents Table (ឯកសារភ្ជាប់ស្កេន)
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

    # 5. Attendance Table (វត្តមានប្រចាំថ្ងៃ)
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

    # 6. Leave Requests Table (ការសុំច្បាប់)
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

    # 7. Missions Table (កត់ត្រាបេសកកម្ម)
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

    # 8. Mission Participants Table
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

    # 9. Payroll Table (ប្រាក់បៀវត្សរ៍ និងប្រាក់ឧបត្ថម្ភ)
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

    # 10. Trainings Table (វគ្គបណ្តុះបណ្តាល)
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

    # 11. Achievements Table (ស្នាដៃ និងគ្រឿងឥស្សរិយយស)
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

    # 14. State Asset Management Tables (បញ្ជីសារពើភណ្ឌទ្រព្យសម្បត្តិរដ្ឋ)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        asset_code TEXT UNIQUE NOT NULL,
        name_kh TEXT NOT NULL,
        name_en TEXT,
        category TEXT NOT NULL DEFAULT 'other',
        brand_model TEXT,
        serial_number TEXT,
        acquisition_date TEXT,
        acquisition_type TEXT DEFAULT 'commune_fund',
        original_value REAL DEFAULT 0,
        condition_status TEXT DEFAULT 'good',
        location TEXT DEFAULT 'សាលាឃុំនគរភាស',
        custodian_staff_id INTEGER,
        photo TEXT,
        attachment TEXT,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (custodian_staff_id) REFERENCES staff (id) ON DELETE SET NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS asset_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        asset_id INTEGER NOT NULL,
        action_type TEXT NOT NULL,
        action_date TEXT NOT NULL,
        performed_by TEXT,
        from_staff_id INTEGER,
        to_staff_id INTEGER,
        cost REAL DEFAULT 0,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (asset_id) REFERENCES assets (id) ON DELETE CASCADE,
        FOREIGN KEY (from_staff_id) REFERENCES staff (id) ON DELETE SET NULL,
        FOREIGN KEY (to_staff_id) REFERENCES staff (id) ON DELETE SET NULL
    )
    """)

    # 15. Development Projects & Expenses Table (កម្មវិធីវិនិយោគ និងចំណាយអភិវឌ្ឍន៍ឃុំ - CIP)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS development_projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_code TEXT UNIQUE NOT NULL,
        project_year INTEGER NOT NULL,
        sector TEXT NOT NULL, -- 'economic', 'social', 'natural_resources', 'admin_security'
        project_name TEXT NOT NULL,
        village_id INTEGER,
        target_location TEXT,
        planned_budget REAL DEFAULT 0,
        actual_expense REAL DEFAULT 0,
        funding_source TEXT DEFAULT 'commune_fund', -- 'commune_fund', 'community', 'partner_ngo', 'national_budget', 'other'
        contractor_agency TEXT,
        progress_percent INTEGER DEFAULT 0,
        status TEXT DEFAULT 'in_progress', -- 'planning', 'bidding', 'in_progress', 'completed', 'delayed'
        start_date TEXT,
        end_date TEXT,
        beneficiaries_count INTEGER DEFAULT 0,
        attachment TEXT,
        notes TEXT,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (village_id) REFERENCES villages (id) ON DELETE SET NULL,
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE SET NULL
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

    # High-Performance Database Indexes
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_staff_category ON staff(category)",
        "CREATE INDEX IF NOT EXISTS idx_staff_status ON staff(status)",
        "CREATE INDEX IF NOT EXISTS idx_staff_village ON staff(village)",
        "CREATE INDEX IF NOT EXISTS idx_staff_officer_code ON staff(officer_code)",
        "CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(date)",
        "CREATE INDEX IF NOT EXISTS idx_attendance_staff_date ON attendance(staff_id, date)",
        "CREATE INDEX IF NOT EXISTS idx_attendance_status ON attendance(status)",
        "CREATE INDEX IF NOT EXISTS idx_leave_status ON leave_requests(status)",
        "CREATE INDEX IF NOT EXISTS idx_leave_staff ON leave_requests(staff_id)",
        "CREATE INDEX IF NOT EXISTS idx_finance_date ON finance_transactions(transaction_date)",
        "CREATE INDEX IF NOT EXISTS idx_finance_type ON finance_transactions(type)",
        "CREATE INDEX IF NOT EXISTS idx_finance_category ON finance_transactions(category)",
        "CREATE INDEX IF NOT EXISTS idx_assets_category ON assets(category)",
        "CREATE INDEX IF NOT EXISTS idx_assets_condition ON assets(condition_status)",
        "CREATE INDEX IF NOT EXISTS idx_assets_custodian ON assets(custodian_staff_id)",
        "CREATE INDEX IF NOT EXISTS idx_assets_code ON assets(asset_code)",
        "CREATE INDEX IF NOT EXISTS idx_asset_logs_asset ON asset_logs(asset_id)",
        "CREATE INDEX IF NOT EXISTS idx_events_date ON commune_events(event_date)",
        "CREATE INDEX IF NOT EXISTS idx_events_type ON commune_events(event_type)",
        "CREATE INDEX IF NOT EXISTS idx_payroll_month ON payroll(month_year)",
        "CREATE INDEX IF NOT EXISTS idx_payroll_staff_month ON payroll(staff_id, month_year)",
        "CREATE INDEX IF NOT EXISTS idx_documents_staff ON documents(staff_id)",
        "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
        "CREATE INDEX IF NOT EXISTS idx_dev_projects_year ON development_projects(project_year)",
        "CREATE INDEX IF NOT EXISTS idx_dev_projects_sector ON development_projects(sector)",
        "CREATE INDEX IF NOT EXISTS idx_dev_projects_status ON development_projects(status)",
        "CREATE INDEX IF NOT EXISTS idx_dev_projects_village ON development_projects(village_id)"
    ]
    for idx_sql in indexes:
        try:
            cursor.execute(idx_sql)
        except Exception:
            pass

    # Ensure system_settings table exists
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS system_settings (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Ensure baseline administrative data (10 Villages & System Users) exist safely (non-destructive)
    ensure_baseline_data(conn)

    conn.commit()


def ensure_baseline_data(conn=None):
    """
    Ensure baseline system administrative data (10 Villages & System Users) exist.
    Strictly non-destructive: uses INSERT OR IGNORE and checks for existing users.
    Existing user records, passwords, and custom data will NEVER be overwritten.
    """
    if conn is None:
        conn = get_db()
    cursor = conn.cursor()

    # 1. 10 Official Villages of Nokor Pheas Commune (ភូមិទាំង ១០ ក្នុងឃុំនគរភាស ស្រុកអង្គរជុំ ខេត្តសៀមរាប)
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

    # 2. System User Accounts (Admin / Clerk / Staff login roles)
    cursor.execute("SELECT COUNT(*) FROM users")
    users_count = cursor.fetchone()[0]
    if users_count == 0:
        users_data = [
            ("admin", PRECOMPUTED_USER_HASHES["admin"], "មី គន់ (មេឃុំ)", "admin", None),
            ("clerk", PRECOMPUTED_USER_HASHES["clerk"], "ហេង ចាន់រិទ្ធ (ស្មៀនឃុំ)", "clerk", None),
            ("it_admin", PRECOMPUTED_USER_HASHES["it_admin"], "សេង ដារ៉ា (មន្ត្រី IT)", "admin", None),
            ("staff", PRECOMPUTED_USER_HASHES["staff"], "លាង ស្រីម៉ៅ (ជំនួយការឃុំ)", "staff", None),
            ("village_chief", PRECOMPUTED_USER_HASHES["village_chief"], "ព្រុំ សុខា (មេភូមិរមៀត)", "staff", None),
        ]
        cursor.executemany(
            "INSERT INTO users (username, password_hash, full_name, role, staff_id) VALUES (?, ?, ?, ?, ?)",
            users_data
        )
    else:
        # Update admin user name to 'មី គន់ (មេឃុំ)'
        try:
            cursor.execute("UPDATE users SET full_name = 'មី គន់ (មេឃុំ)' WHERE username = 'admin' AND (full_name LIKE '%ស៊ូ វណ្ណា%' OR full_name LIKE '%រដ្ឋបាលឃុំ%')")
        except Exception:
            pass

    # Ensure admin user links to staff NP-001 (មី គន់) if available
    try:
        cursor.execute("UPDATE users SET staff_id = (SELECT id FROM staff WHERE officer_code = 'NP-001' LIMIT 1) WHERE username = 'admin' AND staff_id IS NULL")
    except Exception:
        pass

    # Ensure photo integrity (convert/cache existing uploaded files to base64)
    ensure_photo_integrity(conn)

    # Ensure attendance records are in Cambodia Timezone (UTC+7)
    fix_utc_attendance_records(conn)

    # Ensure baseline development projects (CIP) seed data exists
    ensure_development_seed_data(conn)

    conn.commit()


def ensure_development_seed_data(conn=None):
    """
    Seeds initial realistic commune investment projects (CIP) across 4 sectors for 2025 and 2026.
    Non-destructive: only seeds if development_projects table is currently empty.
    """
    if conn is None:
        conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM development_projects")
        row = cursor.fetchone()
        count = row[0] if row else 0
        if count > 0:
            return

        # Fetch village IDs mapping
        cursor.execute("SELECT id, village_name_kh FROM villages")
        v_rows = cursor.fetchall()
        village_map = {r["village_name_kh"]: r["id"] for r in v_rows}

        projects = [
            # 2026 Projects
            (
                "CIP-2026-001", 2026, "economic",
                "សាងសង់ផ្លូវបេតុងជនបទ ប្រវែង ៨៥០ ម៉ែត្រ",
                village_map.get("រមៀត"), "ផ្លូវតភ្ជាប់ពីសាលាឃុំទៅភូមិរមៀត",
                52000000.0, 41500000.0, "commune_fund", "ក្រុមហ៊ុន សាងសង់ ពិសិដ្ឋ",
                80, "in_progress", "2026-01-15", "2026-05-30", 450,
                None, "គម្រោងមូលនិធិឃុំឆ្នាំ២០២៦ ផ្នែកសេដ្ឋកិច្ចអាទិភាពទី១"
            ),
            (
                "CIP-2026-002", 2026, "social",
                "ជួសជុលអគារមណ្ឌលសុខភាព និងសាងសង់បន្ទប់អនាម័យសហគមន៍",
                village_map.get("នគរភាស១"), "មណ្ឌលសុខភាពឃុំនគរភាស ភូមិ១",
                24000000.0, 24000000.0, "commune_fund", "គណៈកម្មការលទ្ធកម្មឃុំ",
                100, "completed", "2026-02-01", "2026-04-10", 1250,
                None, "គម្រោងលើកកម្ពស់សុខុមាលភាពមាតានិងទារក"
            ),
            (
                "CIP-2026-003", 2026, "natural_resources",
                "ស្តារប្រឡាយមេ និងដាំកូនឈើប្រណិតការពារការហូរច្រោះច្រាំង",
                village_map.get("ទន្លេស"), "ប្រឡាយមេខាងជើងភូមិទន្លេស",
                19500000.0, 13000000.0, "partner_ngo", "សហគមន៍កសិកម្មទន្លេស",
                65, "in_progress", "2026-03-01", "2026-06-20", 380,
                None, "កិច្ចសហការរវាងរដ្ឋបាលឃុំ និងអង្គការដៃគូអភិវឌ្ឍន៍បៃតង"
            ),
            (
                "CIP-2026-004", 2026, "admin_security",
                "ដំឡើងប្រព័ន្ធអំពូលសូឡាបំភ្លឺផ្លូវសាធារណៈ ៣០ បង្គោល",
                village_map.get("ជំពូង"), "ផ្លូវកណ្តាលភូមិ និងចំណុចប្រសព្វជំពូង",
                10500000.0, 10500000.0, "community", "ក្រុមជាងអគ្គិសនីសហគមន៍",
                100, "completed", "2026-01-20", "2026-02-28", 320,
                None, "គម្រោងពង្រឹងសន្តិសុខភូមិ-ឃុំមានសុវត្ថិភាព ដោយមានការចូលរួមពីប្រជាពលរដ្ឋ"
            ),
            (
                "CIP-2026-005", 2026, "economic",
                "សាងសង់ស្ពានបេតុងឆ្លងកាត់អូរធម្មជាតិ",
                village_map.get("គោកថ្មី"), "ផ្លូវលំភូមិគោកថ្មី ឆ្ពោះទៅវាលស្រែ",
                32000000.0, 9600000.0, "commune_fund", "ក្រុមហ៊ុន សំណង់អង្គរ",
                30, "in_progress", "2026-04-01", "2026-08-15", 560,
                None, "សម្រួលដល់ការដឹកជញ្ជូនកសិផលរបស់ប្រជាកសិករ"
            ),
            # 2025 Projects
            (
                "CIP-2025-001", 2025, "economic",
                "ជួសជុលកែលម្អផ្លូវគ្រួសក្រហម ប្រវែង ១,២០០ ម៉ែត្រ",
                village_map.get("សំបួរ"), "ផ្លូវតភ្ជាប់ភូមិសំបួរ និងភូមិល្បើក",
                35000000.0, 35000000.0, "commune_fund", "ក្រុមហ៊ុន វិស្វកម្មភ្នំដី",
                100, "completed", "2025-02-10", "2025-05-15", 680,
                None, "បានបញ្ចប់គម្រោង និងប្រគល់ទទួលជាផ្លូវការ"
            ),
            (
                "CIP-2025-002", 2025, "social",
                "ខួងអណ្តូងស្នប់ និងបំពាក់អាងចម្រោះទឹកស្អាតចំនួន ៣ កន្លែង",
                village_map.get("កុក"), "សាលាបឋមសិក្សា និងវត្តអារាមភូមិកុក",
                15000000.0, 14800000.0, "partner_ngo", "អង្គការទឹកស្អាតកម្ពុជា",
                100, "completed", "2025-03-05", "2025-04-25", 420,
                None, "ផ្តល់ទឹកស្អាតដល់សិស្សានុសិស្ស និងប្រជាជនក្នុងភូមិ"
            ),
            (
                "CIP-2025-003", 2025, "natural_resources",
                "ស្តារស្រះទឹកសហគមន៍សម្រាប់ស្តុកទឹកទុកពេលរាំងស្ងួត",
                village_map.get("ពង្រ"), "ស្រះទឹកកណ្តាលភូមិពង្រ",
                18000000.0, 18000000.0, "commune_fund", "គណៈកម្មការអភិវឌ្ឍន៍ភូមិ",
                100, "completed", "2025-05-01", "2025-07-30", 510,
                None, "ជួយផ្គត់ផ្គង់ទឹកប្រើប្រាស់ក្នុងរដូវប្រាំង"
            ),
            (
                "CIP-2025-004", 2025, "admin_security",
                "បំពាក់ស្លាកសញ្ញាចរាចរណ៍ និងយុទ្ធនាការភូមិ-ឃុំមានសុវត្ថិភាព",
                village_map.get("នគរភាស២"), "គ្រប់ផ្លូវប្រសព្វក្នុងភូមិ និងមុខសាលារៀន",
                6000000.0, 5900000.0, "commune_fund", "ប៉ុស្តិ៍នគរបាលរដ្ឋបាលឃុំ",
                100, "completed", "2025-06-01", "2025-07-15", 850,
                None, "កាត់បន្ថយគ្រោះថ្នាក់ចរាចរណ៍ និងបង្កើនសណ្តាប់ធ្នាប់"
            )
        ]

        sql = """
        INSERT INTO development_projects (
            project_code, project_year, sector, project_name,
            village_id, target_location, planned_budget, actual_expense,
            funding_source, contractor_agency, progress_percent, status,
            start_date, end_date, beneficiaries_count, attachment, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        cursor.executemany(sql, projects)
        conn.commit()
    except Exception as e:
        print(f"[Development Seed Data Notice] {e}")


def fix_utc_attendance_records(conn=None):
    """
    Auto-corrects existing attendance records that were inadvertently recorded
    in UTC timezone (e.g. 00:00 to 05:59 AM) instead of Cambodia local time (UTC+7).
    """
    if conn is None:
        conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, date, check_in_time, check_out_time, status, remarks FROM attendance")
        rows = cursor.fetchall()
        for r in rows:
            rec_id = r["id"]
            cin = r["check_in_time"]
            cout = r["check_out_time"]
            status = r["status"]
            needs_update = False
            new_cin = cin
            new_cout = cout
            new_status = status

            # Check if check_in_time is UTC (00:00 to 05:59)
            if cin and len(cin) >= 5 and cin[:2].isdigit():
                h = int(cin[:2])
                m = cin[3:5]
                # If recorded before 6 AM, it's definitely UTC recorded during daytime in Cambodia
                if 0 <= h < 6:
                    new_h = h + 7
                    new_cin = f"{new_h:02d}:{m}"
                    needs_update = True
                    # Recalculate status based on Cambodia working hours
                    if new_cin <= "12:00":
                        new_status = "late" if new_cin > "07:30" else "present"
                    else:
                        new_status = "late" if new_cin > "14:15" else "present"

            # Check if check_out_time is UTC (00:00 to 05:59)
            if cout and len(cout) >= 5 and cout[:2].isdigit():
                h = int(cout[:2])
                m = cout[3:5]
                if 0 <= h < 6:
                    new_h = h + 7
                    new_cout = f"{new_h:02d}:{m}"
                    needs_update = True

            if needs_update:
                cursor.execute("""
                    UPDATE attendance
                    SET check_in_time = ?, check_out_time = ?, status = ?
                    WHERE id = ?
                """, (new_cin, new_cout, new_status, rec_id))
        conn.commit()
    except Exception as e:
        print(f"[Attendance Timezone Migration Notice] {e}")


def ensure_photo_integrity(conn=None):
    """
    Ensure staff photos are robustly linked and converted to self-contained Base64
    so they work seamlessly across serverless deploys (Vercel) and local SQLite.
    """
    if conn is None:
        conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id, officer_code, photo FROM staff")
        staff_rows = cursor.fetchall()
        if not staff_rows:
            return
        
        static_uploads = os.path.join(os.path.dirname(__file__), "static", "uploads")
        if not os.path.exists(static_uploads):
            return

        from utils.helpers import process_and_save_photo

        for st in staff_rows:
            st_id = st["id"]
            code = st["officer_code"]
            photo_val = st["photo"]
            
            # If photo is already base64 data URL or external http URL, it's fine
            if photo_val and (str(photo_val).startswith("data:image") or str(photo_val).startswith("http")):
                continue

            target_file = None
            if photo_val:
                candidate = os.path.join(static_uploads, photo_val)
                if os.path.exists(candidate):
                    target_file = candidate

            # If not found, try to search for matching photo by officer code (e.g. photo_NP_001_...)
            if not target_file and code:
                clean_code = str(code).replace("-", "_")
                for f in os.listdir(static_uploads):
                    if f.startswith(f"photo_{clean_code}_") or f.startswith(f"photo_{code}_"):
                        target_file = os.path.join(static_uploads, f)
                        break

            if target_file and os.path.exists(target_file):
                data_uri, _ = process_and_save_photo(target_file, officer_code=code)
                if data_uri:
                    cursor.execute("UPDATE staff SET photo = ? WHERE id = ?", (data_uri, st_id))
        conn.commit()
    except Exception as e:
        print(f"[Photo Integrity Notice] {e}")



def clear_all_demo_data(conn=None):
    """
    MANUAL ONLY: Clears demo transactions, attendance, leaves, missions, payroll, events, finance, documents, and staff.
    Keeps system user logins and administrative villages intact for real production data entry.
    This function is NEVER called automatically by the system.
    """
    if conn is None:
        conn = get_db()
    cursor = conn.cursor()

    demo_tables = [
        "development_projects",
        "asset_logs",
        "assets",
        "finance_transactions",
        "commune_events",
        "mission_participants",
        "missions",
        "leave_requests",
        "attendance",
        "documents",
        "payroll",
        "trainings",
        "achievements"
    ]

    for tbl in demo_tables:
        try:
            cursor.execute(f"DELETE FROM {tbl}")
        except Exception as e:
            print(f"[Clear Notice] {tbl}: {e}")

    try:
        cursor.execute("UPDATE users SET staff_id = NULL")
        cursor.execute("DELETE FROM staff")
    except Exception as e:
        print(f"[Clear Notice] staff/users: {e}")

    conn.commit()
    ensure_baseline_data(conn)
    print("[Clean Data] All demo data cleared successfully. System ready for live production entry.")


def seed_data():
    """Seed baseline administrative configurations (villages & users). Non-destructive."""
    conn = get_db()
    ensure_baseline_data(conn)


if __name__ == "__main__":
    init_db()
    print("[Database Ready] Schema and baseline administrative structures verified.")


