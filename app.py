"""
Main Flask Application for Nokor Pheas Commune Staff Management System
(ប្រព័ន្ធគ្រប់គ្រងបុគ្គលិករដ្ឋបាលឃុំនគរភាស ស្រុកអង្គរជុំ ខេត្តសៀមរាប)
"""

import os
import io
import json
import calendar
from datetime import datetime, date, timedelta
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, send_file, jsonify, abort, send_from_directory
)

from database import get_db, init_db, seed_data, close_db_connection, clear_all_demo_data
from utils.helpers import (
    to_khmer_num, format_khmer_date, format_currency,
    calculate_age, format_khmer_age, KHMER_MONTHS,
    STAFF_CATEGORIES, ATTENDANCE_STATUSES, LEAVE_TYPES,
    DOCUMENT_TYPES, HONOR_TYPES, login_required,
    admin_required, clerk_or_admin_required, generate_qr_base64,
    FINANCE_INCOME_CATEGORIES, FINANCE_EXPENSE_CATEGORIES,
    PAYMENT_METHODS, FINANCE_STATUSES,
    ASSET_CATEGORIES, ASSET_CONDITIONS, ASSET_ACQUISITIONS,
    staff_photo_url, process_and_save_photo,
    CAMBODIA_TZ, get_now, get_today, get_today_str, get_now_time_str, get_current_month_str
)
from utils.export_excel import (
    export_monthly_attendance_excel,
    export_daily_attendance_excel,
    export_staff_list_excel,
    export_payroll_excel,
    export_finance_excel,
    export_assets_excel
)

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = "nokor_pheas_commune_secure_secret_key_2026"
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = timedelta(days=365)
if os.environ.get("VERCEL"):
    app.config["UPLOAD_FOLDER"] = os.path.join("/tmp", "uploads")
else:
    app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "static", "uploads")

app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max upload

try:
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
except Exception:
    pass

@app.teardown_appcontext
def teardown_db(exception=None):
    close_db_connection(exception)

@app.after_request
def add_cache_headers(response):
    if request.path.startswith('/static/css') or request.path.startswith('/static/js'):
        response.headers['Cache-Control'] = 'no-cache, must-revalidate'
    elif request.path.startswith('/static') or request.path == '/favicon.ico':
        response.headers['Cache-Control'] = 'public, max-age=86400'
    return response

# Route to serve uploads with fallback and fuzzy matching
@app.route("/static/uploads/<path:filename>")
def serve_static_upload(filename):
    """Serve uploaded files with multi-folder fallback and smart filename matching."""
    upload_folder = app.config.get("UPLOAD_FOLDER")
    if upload_folder and os.path.exists(os.path.join(upload_folder, filename)):
        return send_from_directory(upload_folder, filename)

    static_uploads = os.path.join(os.path.dirname(__file__), "static", "uploads")
    if os.path.exists(os.path.join(static_uploads, filename)):
        return send_from_directory(static_uploads, filename)

    clean_target = filename.replace("-", "_")
    for check_dir in [upload_folder, static_uploads]:
        if check_dir and os.path.exists(check_dir):
            try:
                for f in os.listdir(check_dir):
                    if f.replace("-", "_") == clean_target:
                        return send_from_directory(check_dir, f)
                    prefix = clean_target.rsplit(".", 1)[0].rsplit("_", 1)[0]
                    if prefix and prefix in f.replace("-", "_"):
                        return send_from_directory(check_dir, f)
            except Exception:
                pass

    default_avatar = os.path.join(os.path.dirname(__file__), "static", "img", "default-avatar.svg")
    if os.path.exists(default_avatar):
        return send_from_directory(os.path.join(os.path.dirname(__file__), "static", "img"), "default-avatar.svg")

    abort(404)

# Ultra-fast zero-latency database ready check for serverless
@app.before_request
def ensure_database_ready():
    if request.path.startswith('/static') or request.path == '/favicon.ico':
        return
    if not getattr(app, '_db_ready', False):
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM users LIMIT 1")
            cur.fetchone()
            app._db_ready = True
        except Exception:
            try:
                init_db()
                seed_data()
                app._db_ready = True
            except Exception as e:
                print(f"[Startup Notice] Database initialization: {e}")

# Register Jinja context processors & filters
@app.context_processor
def inject_global_vars():
    today = date.today()
    khmer_today = format_khmer_date(today)
    
    # Unread/pending counts for navbar badges (skip for static files or guest sessions)
    pending_leaves_count = 0
    if session.get("user_id") and not (request.path.startswith('/static') or request.path == '/favicon.ico'):
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM leave_requests WHERE status = 'pending'")
            row = cur.fetchone()
            if row:
                pending_leaves_count = row[0]
        except Exception:
            pass

    return {
        "current_user": session,
        "today_khmer": khmer_today,
        "today_iso": today.strftime("%Y-%m-%d"),
        "current_month_iso": today.strftime("%Y-%m"),
        "STAFF_CATEGORIES": STAFF_CATEGORIES,
        "ATTENDANCE_STATUSES": ATTENDANCE_STATUSES,
        "LEAVE_TYPES": LEAVE_TYPES,
        "DOCUMENT_TYPES": DOCUMENT_TYPES,
        "HONOR_TYPES": HONOR_TYPES,
        "FINANCE_INCOME_CATEGORIES": FINANCE_INCOME_CATEGORIES,
        "FINANCE_EXPENSE_CATEGORIES": FINANCE_EXPENSE_CATEGORIES,
        "PAYMENT_METHODS": PAYMENT_METHODS,
        "FINANCE_STATUSES": FINANCE_STATUSES,
        "ASSET_CATEGORIES": ASSET_CATEGORIES,
        "ASSET_CONDITIONS": ASSET_CONDITIONS,
        "ASSET_ACQUISITIONS": ASSET_ACQUISITIONS,
        "to_khmer_num": to_khmer_num,
        "format_khmer_date": format_khmer_date,
        "format_currency": format_currency,
        "calculate_age": calculate_age,
        "format_khmer_age": format_khmer_age,
        "staff_photo_url": staff_photo_url,
        "pending_leaves_count": pending_leaves_count
    }

@app.template_filter("kh_num")
def kh_num_filter(val):
    return to_khmer_num(val)

@app.template_filter("kh_date")
def kh_date_filter(val, include_day=True):
    return format_khmer_date(val, include_day_name=include_day)

@app.template_filter("currency")
def currency_filter(val, curr="រៀល"):
    return format_currency(val, curr)

@app.template_filter("age")
def age_filter(dob):
    return calculate_age(dob)

@app.template_filter("kh_age")
def kh_age_filter(dob, suffix=True):
    return format_khmer_age(dob, suffix=suffix)

@app.template_filter("photo_url")
def photo_url_filter(val):
    return staff_photo_url(val)



# ==============================================================================
# AUTHENTICATION ROUTES
# ==============================================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    # Lazy-init database tables & seed data if first time connecting to cloud database
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        cursor.fetchone()
        conn.close()
    except Exception:
        try:
            init_db()
            seed_data()
        except Exception:
            pass

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND is_active = 1", (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["full_name"] = user["full_name"]
            session["role"] = user["role"]
            session["staff_id"] = user["staff_id"]
            session["avatar"] = user["avatar"]
            flash(f"សូមស្វាគមន៍មកកាន់ប្រព័ន្ធ, {user['full_name']}!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("ឈ្មោះគណនី ឬពាក្យសម្ងាត់មិនត្រឹមត្រូវទេ!", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("លោកអ្នកបានចាកចេញពីប្រព័ន្ធដោយជោគជ័យ!", "info")
    return redirect(url_for("login"))


# ==============================================================================
# DASHBOARD
# ==============================================================================

@app.route("/")
@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    cursor = conn.cursor()
    today_str = get_today_str()
    current_month_str = get_current_month_str()

    # 1. Staff Statistics (Combined single query)
    cursor.execute("""
        SELECT 
            COUNT(*) as total_staff,
            COUNT(CASE WHEN category = 'council' THEN 1 END) as council_count,
            COUNT(CASE WHEN category = 'clerk' THEN 1 END) as clerk_count,
            COUNT(CASE WHEN category = 'contract' THEN 1 END) as contract_count,
            COUNT(CASE WHEN category = 'village' THEN 1 END) as village_count,
            COUNT(CASE WHEN gender = 'ស្រី' THEN 1 END) as female_staff_count
        FROM staff 
        WHERE status = 'active'
    """)
    staff_stats = cursor.fetchone()
    total_staff = staff_stats["total_staff"] if staff_stats else 0
    council_count = staff_stats["council_count"] if staff_stats else 0
    clerk_count = staff_stats["clerk_count"] if staff_stats else 0
    contract_count = staff_stats["contract_count"] if staff_stats else 0
    village_count = staff_stats["village_count"] if staff_stats else 0
    female_staff_count = staff_stats["female_staff_count"] if staff_stats else 0

    # 2. Today's Attendance Breakdown
    cursor.execute("""
        SELECT status, COUNT(*) as status_count 
        FROM attendance 
        WHERE date = ? 
        GROUP BY status
    """, (today_str,))
    att_rows = cursor.fetchall()
    att_stats = {r["status"]: (r.get("status_count") or r.get("count") or 0) for r in att_rows}

    # 3. Pending Leave Requests
    cursor.execute("""
        SELECT l.*, s.name_kh, s.position_title_kh, s.officer_code, s.category
        FROM leave_requests l
        JOIN staff s ON l.staff_id = s.id
        WHERE l.status = 'pending'
        ORDER BY l.created_at DESC
        LIMIT 5
    """)
    pending_leaves = cursor.fetchall()

    # 4. Recent Active Missions
    cursor.execute("""
        SELECT * FROM missions
        ORDER BY start_date DESC
        LIMIT 4
    """)
    recent_missions = cursor.fetchall()

    # 5. Monthly Payroll Summary
    cursor.execute("""
        SELECT SUM(gross_salary) as total_gross, SUM(net_salary) as total_net, COUNT(*) as total_count
        FROM payroll
        WHERE month_year = ?
    """, (current_month_str,))
    payroll_sum = cursor.fetchone()
    if payroll_sum:
        payroll_sum = dict(payroll_sum)
        payroll_sum["count"] = int(payroll_sum.get("total_count") or 0)

    # 6. Today's recent check-in list
    cursor.execute("""
        SELECT a.*, s.name_kh, s.position_title_kh, s.officer_code, s.category
        FROM attendance a
        JOIN staff s ON a.staff_id = s.id
        WHERE a.date = ?
        ORDER BY a.check_in_time DESC
        LIMIT 8
    """, (today_str,))
    today_checkins = cursor.fetchall()

    # 7. Villages list for stats
    cursor.execute("SELECT * FROM villages ORDER BY id")
    villages = cursor.fetchall()

    # 8. Monthly Finance Summary (ចរន្តសាច់ប្រាក់ ចំណូល-ចំណាយ ប្រចាំខែនេះ)
    cursor.execute("""
        SELECT 
            COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as total_income,
            COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as total_expense,
            COUNT(*) as total_tx
        FROM finance_transactions
        WHERE transaction_date LIKE ?
    """, (f"{current_month_str}%",))
    fin_row = cursor.fetchone()
    finance_summary = {
        "income": (fin_row["total_income"] if fin_row else 0) or 0,
        "expense": (fin_row["total_expense"] if fin_row else 0) or 0,
        "net": ((fin_row["total_income"] or 0) - (fin_row["total_expense"] or 0)) if fin_row else 0,
        "count": (fin_row["total_tx"] if fin_row else 0) or 0
    }

    conn.close()

    return render_template(
        "dashboard.html",
        total_staff=total_staff,
        council_count=council_count,
        clerk_count=clerk_count,
        contract_count=contract_count,
        village_count=village_count,
        female_staff_count=female_staff_count,
        att_stats=att_stats,
        pending_leaves=pending_leaves,
        recent_missions=recent_missions,
        payroll_sum=payroll_sum,
        today_checkins=today_checkins,
        villages=villages,
        finance_summary=finance_summary
    )


# ==============================================================================
# STAFF PROFILE MANAGEMENT (មុខងារទី១)
# ==============================================================================

@app.route("/staff")
@login_required
def staff_list():
    category = request.args.get("category", "").strip()
    village = request.args.get("village", "").strip()
    search = request.args.get("q", "").strip()
    status = request.args.get("status", "active").strip()

    try:
        page = int(request.args.get("page", 1))
        if page < 1:
            page = 1
    except (ValueError, TypeError):
        page = 1
    per_page = 10

    conn = get_db()
    cursor = conn.cursor()

    base_where = " WHERE 1=1"
    params = []

    if status and status != "all":
        base_where += " AND status = ?"
        params.append(status)

    if category and category in STAFF_CATEGORIES:
        base_where += " AND category = ?"
        params.append(category)

    if village:
        base_where += " AND village = ?"
        params.append(village)

    if search:
        base_where += " AND (name_kh LIKE ? OR name_en LIKE ? OR officer_code LIKE ? OR phone LIKE ? OR position_title_kh LIKE ?)"
        pattern = f"%{search}%"
        params.extend([pattern, pattern, pattern, pattern, pattern])

    # Total matching staff for pagination
    count_query = f"SELECT COUNT(*) FROM staff{base_where}"
    cursor.execute(count_query, params)
    total_staff = cursor.fetchone()[0]

    total_pages = max(1, (total_staff + per_page - 1) // per_page)
    if page > total_pages:
        page = total_pages
    offset = (page - 1) * per_page

    order_clause = " ORDER BY CASE category WHEN 'council' THEN 1 WHEN 'clerk' THEN 2 WHEN 'contract' THEN 3 ELSE 4 END, id"
    data_query = f"SELECT * FROM staff{base_where}{order_clause} LIMIT ? OFFSET ?"
    data_params = params + [per_page, offset]

    cursor.execute(data_query, data_params)
    staff_rows = cursor.fetchall()

    # Get villages for filter dropdown
    cursor.execute("SELECT village_name_kh FROM villages ORDER BY id")
    village_list = [r["village_name_kh"] if (hasattr(r, "get") and r.get("village_name_kh")) else (r[0] if len(r) > 0 else "") for r in cursor.fetchall()]

    conn.close()

    return render_template(
        "staff/list.html",
        staff_rows=staff_rows,
        selected_category=category,
        selected_village=village,
        selected_status=status,
        search_query=search,
        village_list=village_list,
        page=page,
        per_page=per_page,
        total_staff=total_staff,
        total_pages=total_pages,
        offset=offset
    )


@app.route("/staff/new", methods=["GET", "POST"])
@clerk_or_admin_required
def staff_create():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":
        officer_code = request.form.get("officer_code", "").strip()
        name_kh = request.form.get("name_kh", "").strip()
        name_en = request.form.get("name_en", "").strip()
        gender = request.form.get("gender", "ប្រុស")
        dob = request.form.get("dob", "")
        national_id = request.form.get("national_id", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        village = request.form.get("village", "").strip()
        category = request.form.get("category", "contract")
        position_title_kh = request.form.get("position_title_kh", "").strip()
        position_title_en = request.form.get("position_title_en", "").strip()
        cadre_level = request.form.get("cadre_level", "").strip()
        appointment_date = request.form.get("appointment_date", "")
        contract_end_date = request.form.get("contract_end_date", "") or None
        if category == "clerk":
            base_salary = 0.0
            position_allowance = 0.0
            family_allowance = 0.0
        else:
            base_salary = float(request.form.get("base_salary", 0) or 0)
            position_allowance = float(request.form.get("position_allowance", 0) or 0)
            family_allowance = float(request.form.get("family_allowance", 0) or 0)
        education_level = request.form.get("education_level", "").strip()
        emergency_contact = request.form.get("emergency_contact", "").strip()
        notes = request.form.get("notes", "").strip()

        # Validate National ID (Must be exactly 9 Latin digits and unique)
        if national_id:
            if len(national_id) != 9 or not national_id.isdigit():
                flash("លេខអត្តសញ្ញាណប័ណ្ណសញ្ជាតិខ្មែរ ត្រូវតែជាលេខឡាតាំង ៩ ខ្ទង់ (0-9 ឧ. 040182910)!", "danger")
                cursor.execute("SELECT MAX(id) FROM staff")
                last_id = cursor.fetchone()[0] or 0
                next_code = f"NP-{str(last_id + 1).zfill(3)}"
                cursor.execute("SELECT village_name_kh FROM villages ORDER BY id")
                village_list = [r[0] for r in cursor.fetchall()]
                conn.close()
                return render_template("staff/form.html", is_edit=False, next_code=next_code, village_list=village_list)

            cursor.execute("SELECT id, officer_code, name_kh FROM staff WHERE national_id = ?", (national_id,))
            existing_staff = cursor.fetchone()
            if existing_staff:
                flash(f"លេខអត្តសញ្ញាណប័ណ្ណ «{national_id}» នេះមានក្នុងប្រព័ន្ធរួចហើយ! (ស្ទួនជាមួយមន្ត្រី {existing_staff['name_kh']} - {existing_staff['officer_code']})", "danger")
                cursor.execute("SELECT MAX(id) FROM staff")
                last_id = cursor.fetchone()[0] or 0
                next_code = f"NP-{str(last_id + 1).zfill(3)}"
                cursor.execute("SELECT village_name_kh FROM villages ORDER BY id")
                village_list = [r[0] for r in cursor.fetchall()]
                conn.close()
                return render_template("staff/form.html", is_edit=False, next_code=next_code, village_list=village_list)

        # Handle Photo Upload
        photo_val = None
        if "photo" in request.files:
            file = request.files["photo"]
            if file and file.filename != "":
                data_uri, filename = process_and_save_photo(
                    file,
                    officer_code=officer_code,
                    upload_folder=app.config["UPLOAD_FOLDER"]
                )
                photo_val = data_uri or filename

        try:
            cursor.execute("""
                INSERT INTO staff (
                    officer_code, name_kh, name_en, gender, dob, national_id, phone, email,
                    village, category, position_title_kh, position_title_en, cadre_level,
                    appointment_date, contract_end_date, base_salary, position_allowance,
                    family_allowance, education_level, photo, emergency_contact, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                officer_code, name_kh, name_en, gender, dob, national_id, phone, email,
                village, category, position_title_kh, position_title_en, cadre_level,
                appointment_date, contract_end_date, base_salary, position_allowance,
                family_allowance, education_level, photo_val, emergency_contact, notes
            ))
            new_id = cursor.lastrowid
            conn.commit()
            conn.close()
            flash(f"បានបន្ថែមមន្ត្រី/បុគ្គលិកថ្មី {name_kh} ដោយជោគជ័យ!", "success")
            return redirect(url_for("staff_detail", staff_id=new_id))
        except Exception as e:
            conn.rollback()
            flash(f"មានបញ្ហាក្នុងការបញ្ចូលទិន្នន័យ៖ {str(e)}", "danger")

    # Generate next Officer Code recommendation
    cursor.execute("SELECT MAX(id) FROM staff")
    last_id = cursor.fetchone()[0] or 0
    next_code = f"NP-{str(last_id + 1).zfill(3)}"

    cursor.execute("SELECT village_name_kh FROM villages ORDER BY id")
    village_list = [r[0] for r in cursor.fetchall()]
    conn.close()

    return render_template("staff/form.html", is_edit=False, next_code=next_code, village_list=village_list)


@app.route("/staff/<int:staff_id>")
@login_required
def staff_detail(staff_id):
    # Staff role can only see their own profile unless admin/clerk
    if session.get("role") == "staff" and session.get("staff_id") != staff_id:
        flash("លោកអ្នកអាចមើលបានត្រឹមតែប្រវត្តិរូបផ្ទាល់ខ្លួនប៉ុណ្ណោះ!", "warning")
        return redirect(url_for("staff_detail", staff_id=session.get("staff_id", staff_id)))

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM staff WHERE id = ?", (staff_id,))
    staff = cursor.fetchone()
    if not staff:
        conn.close()
        abort(404)

    # 1. Documents
    cursor.execute("SELECT * FROM documents WHERE staff_id = ? ORDER BY upload_date DESC", (staff_id,))
    documents = cursor.fetchall()

    # 2. Recent Attendance (Current Month)
    cursor.execute("""
        SELECT * FROM attendance 
        WHERE staff_id = ? 
        ORDER BY date DESC 
        LIMIT 15
    """, (staff_id,))
    recent_attendance = cursor.fetchall()

    # 3. Attendance Summary (Total Days this year)
    cur_year = str(date.today().year)
    cursor.execute("""
        SELECT status, COUNT(*) as status_count 
        FROM attendance 
        WHERE staff_id = ? AND substr(date, 1, 4) = ?
        GROUP BY status
    """, (staff_id, cur_year))
    att_counts = {r["status"]: (r.get("status_count") or r.get("count") or 0) for r in cursor.fetchall()}

    # 4. Leave History
    cursor.execute("SELECT * FROM leave_requests WHERE staff_id = ? ORDER BY created_at DESC", (staff_id,))
    leave_history = cursor.fetchall()

    # 5. Missions
    cursor.execute("""
        SELECT m.*, mp.role_in_mission, mp.allowance
        FROM missions m
        JOIN mission_participants mp ON m.id = mp.mission_id
        WHERE mp.staff_id = ?
        ORDER BY m.start_date DESC
    """, (staff_id,))
    missions = cursor.fetchall()

    # 6. Payroll History
    cursor.execute("SELECT * FROM payroll WHERE staff_id = ? ORDER BY month_year DESC LIMIT 12", (staff_id,))
    payroll_history = cursor.fetchall()

    # 7. Trainings
    cursor.execute("SELECT * FROM trainings WHERE staff_id = ? ORDER BY start_date DESC", (staff_id,))
    trainings = cursor.fetchall()

    # 8. Achievements
    cursor.execute("SELECT * FROM achievements WHERE staff_id = ? ORDER BY award_date DESC", (staff_id,))
    achievements = cursor.fetchall()

    # 9. Assigned State Assets
    cursor.execute("SELECT * FROM assets WHERE custodian_staff_id = ? ORDER BY id DESC", (staff_id,))
    assigned_assets = cursor.fetchall()

    conn.close()

    return render_template(
        "staff/detail.html",
        staff=staff,
        documents=documents,
        recent_attendance=recent_attendance,
        att_counts=att_counts,
        leave_history=leave_history,
        missions=missions,
        payroll_history=payroll_history,
        trainings=trainings,
        achievements=achievements,
        assigned_assets=assigned_assets
    )


@app.route("/staff/<int:staff_id>/edit", methods=["GET", "POST"])
@clerk_or_admin_required
def staff_edit(staff_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM staff WHERE id = ?", (staff_id,))
    staff = cursor.fetchone()
    if not staff:
        conn.close()
        abort(404)

    if request.method == "POST":
        name_kh = request.form.get("name_kh", "").strip()
        name_en = request.form.get("name_en", "").strip()
        gender = request.form.get("gender", "ប្រុស")
        dob = request.form.get("dob", "")
        national_id = request.form.get("national_id", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        village = request.form.get("village", "").strip()
        category = request.form.get("category", "contract")
        position_title_kh = request.form.get("position_title_kh", "").strip()
        position_title_en = request.form.get("position_title_en", "").strip()
        cadre_level = request.form.get("cadre_level", "").strip()
        appointment_date = request.form.get("appointment_date", "")
        contract_end_date = request.form.get("contract_end_date", "") or None
        if category == "clerk":
            base_salary = 0.0
            position_allowance = 0.0
            family_allowance = 0.0
        else:
            base_salary = float(request.form.get("base_salary", 0) or 0)
            position_allowance = float(request.form.get("position_allowance", 0) or 0)
            family_allowance = float(request.form.get("family_allowance", 0) or 0)
        education_level = request.form.get("education_level", "").strip()
        emergency_contact = request.form.get("emergency_contact", "").strip()
        status = request.form.get("status", "active")
        notes = request.form.get("notes", "").strip()

        # Validate National ID (Must be exactly 9 Latin digits and unique)
        if national_id:
            if len(national_id) != 9 or not national_id.isdigit():
                flash("លេខអត្តសញ្ញាណប័ណ្ណសញ្ជាតិខ្មែរ ត្រូវតែជាលេខឡាតាំង ៩ ខ្ទង់ (0-9 ឧ. 040182910)!", "danger")
                cursor.execute("SELECT village_name_kh FROM villages ORDER BY id")
                village_list = [r[0] for r in cursor.fetchall()]
                conn.close()
                return render_template("staff/form.html", is_edit=True, staff=staff, village_list=village_list)

            cursor.execute("SELECT id, officer_code, name_kh FROM staff WHERE national_id = ? AND id != ?", (national_id, staff_id))
            existing_staff = cursor.fetchone()
            if existing_staff:
                flash(f"លេខអត្តសញ្ញាណប័ណ្ណ «{national_id}» នេះមានក្នុងប្រព័ន្ធរួចហើយ! (ស្ទួនជាមួយមន្ត្រី {existing_staff['name_kh']} - {existing_staff['officer_code']})", "danger")
                cursor.execute("SELECT village_name_kh FROM villages ORDER BY id")
                village_list = [r[0] for r in cursor.fetchall()]
                conn.close()
                return render_template("staff/form.html", is_edit=True, staff=staff, village_list=village_list)

        photo_val = staff["photo"]
        if "photo" in request.files:
            file = request.files["photo"]
            if file and file.filename != "":
                data_uri, filename = process_and_save_photo(
                    file,
                    officer_code=staff["officer_code"],
                    upload_folder=app.config["UPLOAD_FOLDER"]
                )
                if data_uri:
                    photo_val = data_uri
                elif filename:
                    photo_val = filename

        cursor.execute("""
            UPDATE staff SET
                name_kh = ?, name_en = ?, gender = ?, dob = ?, national_id = ?,
                phone = ?, email = ?, village = ?, category = ?, position_title_kh = ?,
                position_title_en = ?, cadre_level = ?, appointment_date = ?,
                contract_end_date = ?, base_salary = ?, position_allowance = ?,
                family_allowance = ?, education_level = ?, photo = ?,
                status = ?, emergency_contact = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            name_kh, name_en, gender, dob, national_id, phone, email, village,
            category, position_title_kh, position_title_en, cadre_level,
            appointment_date, contract_end_date, base_salary, position_allowance,
            family_allowance, education_level, photo_val, status,
            emergency_contact, notes, staff_id
        ))
        conn.commit()
        conn.close()
        flash(f"បានកែប្រែព័ត៌មានមន្ត្រី {name_kh} ដោយជោគជ័យ!", "success")
        return redirect(url_for("staff_detail", staff_id=staff_id))

    cursor.execute("SELECT village_name_kh FROM villages ORDER BY id")
    village_list = [r[0] for r in cursor.fetchall()]
    conn.close()

    return render_template("staff/form.html", is_edit=True, staff=staff, village_list=village_list)


@app.route("/staff/<int:staff_id>/photo", methods=["POST"])
@login_required
def staff_update_photo(staff_id):
    """Quick update profile photo from detail page or API modal"""
    if session.get("role") not in ["admin", "clerk"] and session.get("staff_id") != staff_id:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
            return jsonify({"success": False, "message": "លោកអ្នកមិនមានសិទ្ធិផ្លាស់ប្តូររូបថតនេះទេ!"}), 403
        flash("លោកអ្នកមិនមានសិទ្ធិផ្លាស់ប្តូររូបថតនេះទេ!", "danger")
        return redirect(url_for("staff_detail", staff_id=staff_id))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, officer_code, name_kh, photo FROM staff WHERE id = ?", (staff_id,))
    staff = cursor.fetchone()
    if not staff:
        conn.close()
        abort(404)

    data_uri = None
    saved_filename = None

    if request.is_json and request.json.get("photo_data"):
        data_uri, saved_filename = process_and_save_photo(
            request.json["photo_data"],
            officer_code=staff["officer_code"],
            upload_folder=app.config["UPLOAD_FOLDER"]
        )
    elif "photo" in request.files:
        file = request.files["photo"]
        if file and file.filename != "":
            data_uri, saved_filename = process_and_save_photo(
                file,
                officer_code=staff["officer_code"],
                upload_folder=app.config["UPLOAD_FOLDER"]
            )

    if not data_uri:
        conn.close()
        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
            return jsonify({"success": False, "message": "សូមជ្រើសរើសឯកសាររូបភាពត្រឹមត្រូវ (JPG, PNG, WebP)!"}), 400
        flash("សូមជ្រើសរើសឯកសាររូបភាពត្រឹមត្រូវ!", "danger")
        return redirect(url_for("staff_detail", staff_id=staff_id))

    cursor.execute("""
        UPDATE staff
        SET photo = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (data_uri, staff_id))
    conn.commit()
    conn.close()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
        return jsonify({
            "success": True,
            "photo_url": data_uri,
            "message": f"បានផ្លាស់ប្តូររូបថតរបស់ {staff['name_kh']} ដោយជោគជ័យ!"
        })

    flash(f"បានផ្លាស់ប្តូររូបថតរបស់ {staff['name_kh']} ដោយជោគជ័យ!", "success")
    return redirect(url_for("staff_detail", staff_id=staff_id))


@app.route("/staff/<int:staff_id>/delete", methods=["POST"])
@admin_required
def staff_delete(staff_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name_kh FROM staff WHERE id = ?", (staff_id,))
    staff = cursor.fetchone()
    if staff:
        cursor.execute("DELETE FROM staff WHERE id = ?", (staff_id,))
        conn.commit()
        flash(f"បានលុបមន្ត្រី {staff['name_kh']} ចេញពីប្រព័ន្ធរួចរាល់!", "success")
    conn.close()
    return redirect(url_for("staff_list"))


@app.route("/api/check-national-id")
@login_required
def api_check_national_id():
    nid = request.args.get("national_id", "").strip()
    exclude_id = request.args.get("exclude_id", "").strip()

    if not nid:
        return jsonify({"valid": True, "duplicate": False})

    if len(nid) != 9 or not nid.isdigit():
        return jsonify({
            "valid": False,
            "duplicate": False,
            "message": "លេខអត្តសញ្ញាណប័ណ្ណត្រូវតែជាលេខឡាតាំង ៩ ខ្ទង់ (0-9 ឧ. 040182910)!"
        })

    conn = get_db()
    cursor = conn.cursor()
    if exclude_id and exclude_id.isdigit():
        cursor.execute("""
            SELECT id, officer_code, name_kh, name_en, gender, dob, national_id,
                   phone, email, village, category, position_title_kh, position_title_en,
                   cadre_level, appointment_date, photo, status
            FROM staff WHERE national_id = ? AND id != ?
        """, (nid, int(exclude_id)))
    else:
        cursor.execute("""
            SELECT id, officer_code, name_kh, name_en, gender, dob, national_id,
                   phone, email, village, category, position_title_kh, position_title_en,
                   cadre_level, appointment_date, photo, status
            FROM staff WHERE national_id = ?
        """, (nid,))

    existing = cursor.fetchone()
    conn.close()

    if existing:
        category_kh = STAFF_CATEGORIES.get(existing["category"], {}).get("name_kh", existing["category"])
        staff_data = {
            "id": existing["id"],
            "officer_code": existing["officer_code"],
            "name_kh": existing["name_kh"],
            "name_en": existing["name_en"] or "",
            "gender": existing["gender"],
            "dob": existing["dob"],
            "age_kh": format_khmer_age(existing["dob"]) if existing["dob"] else "",
            "national_id": existing["national_id"],
            "phone": existing["phone"] or "មិនមាន",
            "email": existing["email"] or "មិនមាន",
            "village": existing["village"],
            "category": existing["category"],
            "category_kh": category_kh,
            "position_title_kh": existing["position_title_kh"],
            "appointment_date": existing["appointment_date"] or "មិនមាន",
            "photo_url": staff_photo_url(existing["photo"]) if existing["photo"] else None,
            "status": existing["status"]
        }
        return jsonify({
            "valid": False,
            "duplicate": True,
            "message": f"លេខអត្តសញ្ញាណប័ណ្ណ «{nid}» នេះមានក្នុងប្រព័ន្ធរួចហើយ! (ស្ទួនជាមួយមន្ត្រី {existing['name_kh']} - {existing['officer_code']})",
            "staff": staff_data
        })

    return jsonify({
        "valid": True,
        "duplicate": False,
        "message": "លេខអត្តសញ្ញាណប័ណ្ណត្រឹមត្រូវ (៩ ខ្ទង់) អាចប្រើប្រាស់បាន"
    })


@app.route("/staff/<int:staff_id>/print-cv")
@login_required
def staff_print_cv(staff_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM staff WHERE id = ?", (staff_id,))
    staff = cursor.fetchone()
    if not staff:
        conn.close()
        abort(404)

    cursor.execute("SELECT * FROM trainings WHERE staff_id = ? ORDER BY start_date DESC", (staff_id,))
    trainings = cursor.fetchall()

    cursor.execute("SELECT * FROM achievements WHERE staff_id = ? ORDER BY award_date DESC", (staff_id,))
    achievements = cursor.fetchall()

    conn.close()
    return render_template("staff/print_cv.html", staff=staff, trainings=trainings, achievements=achievements)


@app.route("/staff/<int:staff_id>/id-card")
@login_required
def staff_id_card(staff_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM staff WHERE id = ?", (staff_id,))
    staff = cursor.fetchone()
    conn.close()
    if not staff:
        abort(404)

    # Verification QR Code payload
    qr_payload = f"NP-STAFF:{staff['officer_code']}|{staff['name_kh']}|{staff['position_title_kh']}|ឃុំនគរភាស ស្រុកអង្គរជុំ"
    qr_code_b64 = generate_qr_base64(qr_payload)

    # Expiry calculation: 5 years from appointment or today + 5 years
    expiry_year = date.today().year + 5
    expiry_date_kh = f"៣១ ធ្នូ {to_khmer_num(expiry_year)}"

    return render_template(
        "staff/id_card.html",
        staff=staff,
        qr_code=qr_code_b64,
        expiry_date_kh=expiry_date_kh,
        categories=STAFF_CATEGORIES
    )


@app.route("/staff/id-cards")
@login_required
def staff_id_cards_batch():
    category = request.args.get("category", "")
    village = request.args.get("village", "")
    search = request.args.get("search", "").strip()

    conn = get_db()
    cursor = conn.cursor()

    query = "SELECT * FROM staff WHERE status = 'active'"
    params = []

    if category:
        query += " AND category = ?"
        params.append(category)

    if village:
        query += " AND village = ?"
        params.append(village)

    if search:
        query += " AND (name_kh LIKE ? OR name_en LIKE ? OR officer_code LIKE ? OR position_title_kh LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, term, term])

    query += " ORDER BY CASE category WHEN 'council' THEN 1 WHEN 'clerk' THEN 2 WHEN 'contract' THEN 3 ELSE 4 END, id"
    cursor.execute(query, params)
    staff_list = cursor.fetchall()

    cursor.execute("SELECT village_name_kh FROM villages ORDER BY id")
    village_list = [r[0] for r in cursor.fetchall()]
    conn.close()

    # Generate QR codes and expiry for each staff
    expiry_year = date.today().year + 5
    expiry_date_kh = f"៣១ ធ្នូ {to_khmer_num(expiry_year)}"

    staff_cards = []
    for s in staff_list:
        payload = f"NP-STAFF:{s['officer_code']}|{s['name_kh']}|{s['position_title_kh']}|ឃុំនគរភាស ស្រុកអង្គរជុំ"
        qr_b64 = generate_qr_base64(payload)
        staff_cards.append({
            "staff": s,
            "qr_code": qr_b64,
            "expiry_date_kh": expiry_date_kh
        })

    return render_template(
        "staff/id_cards_batch.html",
        staff_cards=staff_cards,
        categories=STAFF_CATEGORIES,
        village_list=village_list,
        selected_category=category,
        selected_village=village,
        search=search,
        total_count=len(staff_cards)
    )


@app.route("/staff/<int:staff_id>/upload-doc", methods=["POST"])
@clerk_or_admin_required
def staff_upload_doc(staff_id):
    doc_type = request.form.get("doc_type", "other")
    title = request.form.get("title", "").strip()
    notes = request.form.get("notes", "").strip()

    if "document_file" not in request.files:
        flash("សូមជ្រើសរើសឯកសារដើម្បី Upload!", "danger")
        return redirect(url_for("staff_detail", staff_id=staff_id))

    file = request.files["document_file"]
    if file.filename == "":
        flash("មិនមានឯកសារត្រូវបានជ្រើសរើស!", "danger")
        return redirect(url_for("staff_detail", staff_id=staff_id))

    filename = f"doc_{staff_id}_{int(datetime.now().timestamp())}_{secure_filename(file.filename)}"
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(file_path)
    file_size = os.path.getsize(file_path)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO documents (staff_id, doc_type, title, filename, file_path, file_size, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (staff_id, doc_type, title or file.filename, filename, f"/static/uploads/{filename}", file_size, notes))
    conn.commit()
    conn.close()

    flash("បាន Upload ឯកសារភ្ជាប់ដោយជោគជ័យ!", "success")
    return redirect(url_for("staff_detail", staff_id=staff_id))


@app.route("/document/<int:doc_id>/delete", methods=["POST"])
@clerk_or_admin_required
def document_delete(doc_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT staff_id, filename FROM documents WHERE id = ?", (doc_id,))
    doc = cursor.fetchone()
    if doc:
        staff_id = doc["staff_id"]
        # Remove file from disk
        try:
            os.remove(os.path.join(app.config["UPLOAD_FOLDER"], doc["filename"]))
        except Exception:
            pass
        cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        conn.commit()
        conn.close()
        flash("បានលុបឯកសារភ្ជាប់រួចរាល់!", "info")
        return redirect(url_for("staff_detail", staff_id=staff_id))
    conn.close()
    return redirect(url_for("staff_list"))


# ==============================================================================
# ATTENDANCE & LEAVE TRACKING (មុខងារទី២)
# ==============================================================================

@app.route("/attendance/daily", methods=["GET", "POST"])
@login_required
def attendance_daily():
    target_date = request.args.get("date", get_today_str())

    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST" and session.get("role") in ["admin", "clerk"]:
        # Save batch attendance
        form_date = request.form.get("attendance_date", target_date)
        
        cursor.execute("SELECT id FROM staff WHERE status = 'active'")
        active_staff = cursor.fetchall()

        for s in active_staff:
            sid = s["id"]
            status = request.form.get(f"status_{sid}")
            check_in = request.form.get(f"check_in_{sid}", "").strip() or None
            check_out = request.form.get(f"check_out_{sid}", "").strip() or None
            remarks = request.form.get(f"remarks_{sid}", "").strip()

            if status:
                cursor.execute("""
                    INSERT INTO attendance (staff_id, date, check_in_time, check_out_time, status, remarks, recorded_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(staff_id, date) DO UPDATE SET
                        check_in_time = excluded.check_in_time,
                        check_out_time = excluded.check_out_time,
                        status = excluded.status,
                        remarks = excluded.remarks,
                        recorded_by = excluded.recorded_by
                """, (sid, form_date, check_in, check_out, status, remarks, session.get("user_id")))

        conn.commit()
        flash(f"បានកត់ត្រាវត្តមានសម្រាប់កាលបរិច្ឆេទ {format_khmer_date(form_date)} ដោយជោគជ័យ!", "success")
        return redirect(url_for("attendance_daily", date=form_date))

    # Fetch staff with attendance record on target_date
    cursor.execute("""
        SELECT s.id, s.officer_code, s.name_kh, s.photo, s.gender, s.position_title_kh, s.category, s.village,
               a.check_in_time, a.check_out_time, a.status as att_status, a.remarks
        FROM staff s
        LEFT JOIN attendance a ON s.id = a.staff_id AND a.date = ?
        WHERE s.status = 'active'
        ORDER BY CASE s.category WHEN 'council' THEN 1 WHEN 'clerk' THEN 2 WHEN 'contract' THEN 3 ELSE 4 END, s.id
    """, (target_date,))
    staff_attendance = cursor.fetchall()
    conn.close()

    return render_template(
        "attendance/daily.html",
        target_date=target_date,
        staff_attendance=staff_attendance
    )


@app.route("/attendance/quick-checkin", methods=["POST"])
@login_required
def quick_checkin():
    user_staff_id = session.get("staff_id")
    if not user_staff_id:
        return jsonify({"success": False, "message": "គណនីនេះមិនបានភ្ជាប់ជាមួយមន្ត្រីណាមួយទេ!"})

    today_dt = get_today()
    # Reject on weekends (Saturday = 5, Sunday = 6)
    if today_dt.weekday() in [5, 6]:
        day_kh = "ថ្ងៃសៅរ៍" if today_dt.weekday() == 5 else "ថ្ងៃអាទិត្យ"
        return jsonify({
            "success": False,
            "is_weekend": True,
            "message": f"មិនអាចកត់ត្រាវត្តមានបានទេ! ថ្ងៃនេះជា{day_kh} (ថ្ងៃឈប់សម្រាកចុងសប្តាហ៍)"
        })

    today_str = get_today_str()
    now_time = get_now_time_str()

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM attendance WHERE staff_id = ? AND date = ?", (user_staff_id, today_str))
    record = cursor.fetchone()

    if not record:
        # Check-in
        if now_time <= "12:00":
            status = "late" if now_time > "07:30" else "present"
            shift_text = "ពេលព្រឹក"
        else:
            status = "late" if now_time > "14:15" else "present"
            shift_text = "ពេលរសៀល"

        status_kh = " (មកយឺត)" if status == "late" else ""
        cursor.execute("""
            INSERT INTO attendance (staff_id, date, check_in_time, status, remarks, recorded_by)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_staff_id, today_str, now_time, status, f"កត់ត្រាចូល{shift_text}", session.get("user_id")))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "action": "check_in", "time": now_time, "status": status, "message": f"បានចូលធ្វើការ{shift_text}{status_kh} នៅម៉ោង {to_khmer_num(now_time)}"})
    else:
        # Check-out
        shift_text = "ពេលព្រឹក" if now_time <= "13:00" else "ពេលល្ងាច"
        cursor.execute("""
            UPDATE attendance 
            SET check_out_time = ?, remarks = remarks || ' (ចេញ' || ? || ')'
            WHERE id = ?
        """, (now_time, shift_text, record["id"]))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "action": "check_out", "time": now_time, "message": f"បានចេញពីធ្វើការ{shift_text} នៅម៉ោង {to_khmer_num(now_time)}"})


@app.route("/attendance/monthly")
@login_required
def attendance_monthly():
    month_year = request.args.get("month", get_current_month_str())
    year, month = map(int, month_year.split("-"))
    num_days = calendar.monthrange(year, month)[1]

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, officer_code, name_kh, gender, position_title_kh, category
        FROM staff
        WHERE status = 'active'
        ORDER BY CASE category WHEN 'council' THEN 1 WHEN 'clerk' THEN 2 WHEN 'contract' THEN 3 ELSE 4 END, id
    """)
    staff_list = cursor.fetchall()

    cursor.execute("""
        SELECT staff_id, date, status, check_in_time
        FROM attendance
        WHERE substr(date, 1, 7) = ?
    """, (month_year,))
    att_records = cursor.fetchall()
    conn.close()

    # Map attendance: att_grid[staff_id][day_num] = status
    att_grid = {}
    for r in att_records:
        sid = r["staff_id"]
        day_num = int(r["date"].split("-")[2])
        if sid not in att_grid:
            att_grid[sid] = {}
        att_grid[sid][day_num] = r["status"]

    days_info = []
    for d in range(1, num_days + 1):
        cur_d = date(year, month, d)
        days_info.append({
            "day": d,
            "dow_kh": ["ចន្ទ", "អង្គារ", "ពុធ", "ព្រហ", "សុក្រ", "សៅរ៍", "អាទិត្យ"][cur_d.weekday()],
            "is_weekend": cur_d.weekday() >= 5,
            "date_iso": cur_d.strftime("%Y-%m-%d")
        })

    return render_template(
        "attendance/monthly.html",
        month_year=month_year,
        year=year,
        month=month,
        num_days=num_days,
        days_info=days_info,
        staff_list=staff_list,
        att_grid=att_grid
    )


@app.route("/attendance/scan")
@login_required
def attendance_scan():
    today_dt = get_today()
    today_str = get_today_str()
    conn = get_db()
    cursor = conn.cursor()

    # Total active staff
    cursor.execute("SELECT COUNT(*) FROM staff WHERE status = 'active'")
    total_staff = cursor.fetchone()[0]

    # Total present today
    cursor.execute("SELECT COUNT(*) FROM attendance WHERE date = ?", (today_str,))
    today_present = cursor.fetchone()[0]

    # Today's scan list
    cursor.execute("""
        SELECT a.id, a.check_in_time, a.check_out_time, a.status, a.remarks,
               s.id as staff_id, s.officer_code, s.name_kh, s.name_en, s.photo, s.position_title_kh, s.village, s.category
        FROM attendance a
        JOIN staff s ON a.staff_id = s.id
        WHERE a.date = ?
        ORDER BY a.id DESC
    """, (today_str,))
    today_records = cursor.fetchall()

    # All active staff for search combobox
    cursor.execute("""
        SELECT id, officer_code, name_kh, name_en, photo, position_title_kh, village, category
        FROM staff
        WHERE status = 'active'
        ORDER BY CASE category WHEN 'council' THEN 1 WHEN 'clerk' THEN 2 WHEN 'contract' THEN 3 ELSE 4 END, id ASC
    """)
    all_active_staff = cursor.fetchall()
    conn.close()

    is_weekend = today_dt.weekday() in [5, 6]
    day_name_kh = "ថ្ងៃសៅរ៍" if today_dt.weekday() == 5 else ("ថ្ងៃអាទិត្យ" if today_dt.weekday() == 6 else "")

    return render_template(
        "attendance/scan.html",
        today_str=today_str,
        today_kh=format_khmer_date(today_dt),
        is_weekend=is_weekend,
        day_name_kh=day_name_kh,
        total_staff=total_staff,
        today_present=today_present,
        today_records=today_records,
        all_active_staff=all_active_staff,
        categories=STAFF_CATEGORIES,
        statuses=ATTENDANCE_STATUSES
    )


@app.route("/api/attendance/scan", methods=["POST"])
@login_required
def api_attendance_scan():
    data = request.get_json() or {}
    raw_code = data.get("code", "").strip()
    scan_date = data.get("date", get_today_str())

    # Check if scan date is weekend (Saturday = 5, Sunday = 6)
    try:
        scan_dt = datetime.strptime(scan_date, "%Y-%m-%d").date()
    except Exception:
        scan_dt = get_today()

    if scan_dt.weekday() in [5, 6]:
        day_kh = "ថ្ងៃសៅរ៍" if scan_dt.weekday() == 5 else "ថ្ងៃអាទិត្យ"
        return jsonify({
            "success": False,
            "is_weekend": True,
            "message": f"មិនអាចកត់ត្រាវត្តមានបានទេ! ថ្ងៃនេះជា{day_kh} (ថ្ងៃឈប់សម្រាកចុងសប្តាហ៍)"
        }), 400

    if not raw_code:
        return jsonify({"success": False, "message": "មិនមានទិន្នន័យ QR Code ឬឈ្មោះមន្ត្រីត្រូវបានបញ្ជូនមកទេ!"}), 400

    # Parse QR payload (e.g. NP-STAFF:NP-001|... or "មី គន់ (NP-001)" or NP-001 or integer ID)
    officer_code = ""
    if raw_code.startswith("NP-STAFF:"):
        parts = raw_code.replace("NP-STAFF:", "").split("|")
        officer_code = parts[0].strip()
    elif "(" in raw_code and ")" in raw_code:
        code_inside = raw_code[raw_code.find("(") + 1:raw_code.find(")")].strip()
        if code_inside.startswith("NP-") or code_inside.startswith("np-") or code_inside.isdigit():
            officer_code = code_inside.upper()
        else:
            officer_code = raw_code.strip()
    elif raw_code.startswith("NP-") or raw_code.startswith("np-"):
        officer_code = raw_code.upper()
    else:
        officer_code = raw_code.strip()

    conn = get_db()
    cursor = conn.cursor()

    # Look up staff by officer_code, id, name_kh, or name_en
    cursor.execute("""
        SELECT * FROM staff 
        WHERE (UPPER(officer_code) = UPPER(?) 
               OR id = ? 
               OR UPPER(name_kh) = UPPER(?) 
               OR (name_en IS NOT NULL AND UPPER(name_en) = UPPER(?))) 
          AND status = 'active'
    """, (officer_code, officer_code if officer_code.isdigit() else -1, officer_code, officer_code))
    staff = cursor.fetchone()

    if not staff:
        conn.close()
        return jsonify({"success": False, "message": f"រកមិនឃើញមន្ត្រី '{officer_code}' ក្នុងប្រព័ន្ធទេ!"}), 404

    staff_id = staff["id"]
    now_time = get_now_time_str()

    # Check today's attendance record for this staff
    cursor.execute("SELECT * FROM attendance WHERE staff_id = ? AND date = ?", (staff_id, scan_date))
    record = cursor.fetchone()

    action_type = ""
    status = "present"
    message = ""

    if not record:
        # First scan of the day -> Check-In
        if now_time <= "12:00":
            # Morning Shift: 07:00 - 11:30 (Late if > 07:30)
            if now_time > "07:30":
                status = "late"
                message = f"កត់ត្រាវត្តមានចូលពេលព្រឹក (មកយឺត) ជោគជ័យ នៅម៉ោង {to_khmer_num(now_time)}"
            else:
                status = "present"
                message = f"កត់ត្រាវត្តមានចូលពេលព្រឹកជោគជ័យ នៅម៉ោង {to_khmer_num(now_time)}"
            remarks = "ស្កេន QR Code ចូលព្រឹក"
        else:
            # Afternoon Shift: 14:00 - 17:30 (Late if > 14:15)
            if now_time > "14:15":
                status = "late"
                message = f"កត់ត្រាវត្តមានចូលពេលរសៀល (មកយឺត) ជោគជ័យ នៅម៉ោង {to_khmer_num(now_time)}"
            else:
                status = "present"
                message = f"កត់ត្រាវត្តមានចូលពេលរសៀលជោគជ័យ នៅម៉ោង {to_khmer_num(now_time)}"
            remarks = "ស្កេន QR Code ចូលរសៀល"

        action_type = "check_in"
        cursor.execute("""
            INSERT INTO attendance (staff_id, date, check_in_time, status, remarks, recorded_by)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (staff_id, scan_date, now_time, status, remarks, session.get("user_id")))
    else:
        # Already checked in -> Record check_out
        action_type = "check_out"
        status = record["status"] or "present"
        remarks = record["remarks"] or ""
        shift_text = "ពេលព្រឹក" if now_time <= "13:00" else "ពេលល្ងាច"

        if f"ស្កេន QR Code ចេញ{shift_text}" not in remarks:
            remarks += f" | ស្កេន QR Code ចេញ{shift_text}"

        cursor.execute("""
            UPDATE attendance 
            SET check_out_time = ?, remarks = ?
            WHERE id = ?
        """, (now_time, remarks, record["id"]))
        message = f"កត់ត្រាម៉ោងចេញពីធ្វើការ{shift_text}ជោគជ័យ នៅម៉ោង {to_khmer_num(now_time)}"

    conn.commit()

    # Get updated counts
    cursor.execute("SELECT COUNT(*) FROM attendance WHERE date = ?", (scan_date,))
    today_count = cursor.fetchone()[0]

    # Get full updated record
    cursor.execute("""
        SELECT a.check_in_time, a.check_out_time, a.status, a.remarks
        FROM attendance a WHERE a.staff_id = ? AND a.date = ?
    """, (staff_id, scan_date))
    updated_rec = cursor.fetchone()

    conn.close()

    return jsonify({
        "success": True,
        "action": action_type,
        "time": now_time,
        "time_kh": to_khmer_num(now_time),
        "check_in_time": updated_rec["check_in_time"] or now_time,
        "check_out_time": updated_rec["check_out_time"] or "-",
        "status": status,
        "status_label": ATTENDANCE_STATUSES.get(status, {}).get("label_kh", status),
        "message": message,
        "staff": {
            "id": staff["id"],
            "officer_code": staff["officer_code"],
            "name_kh": staff["name_kh"],
            "name_en": staff["name_en"] or "",
            "position": staff["position_title_kh"],
            "village": staff["village"],
            "category": staff["category"],
            "photo": staff_photo_url(staff["photo"]) if staff["photo"] else None
        },
        "today_count": today_count,
        "today_count_kh": to_khmer_num(today_count)
    })


@app.route("/attendance/kiosk-qr")
@login_required
def attendance_kiosk_qr():
    # Generate Commune QR code for general kiosk check-in
    today_dt = get_today()
    today_str = get_today_str()
    kiosk_payload = f"NP-KIOSK:NOKOR_PHEAS|{today_str}"
    kiosk_qr_b64 = generate_qr_base64(kiosk_payload)
    today_kh = format_khmer_date(today_dt)

    return render_template(
        "attendance/kiosk_qr.html",
        kiosk_qr=kiosk_qr_b64,
        today_kh=today_kh
    )


@app.route("/leave")
@login_required
def leave_list():
    status_filter = request.args.get("status", "all")

    conn = get_db()
    cursor = conn.cursor()

    query = """
        SELECT l.*, s.officer_code, s.name_kh, s.position_title_kh, s.category,
               u.full_name as approver_name
        FROM leave_requests l
        JOIN staff s ON l.staff_id = s.id
        LEFT JOIN users u ON l.approved_by = u.id
        WHERE 1=1
    """
    params = []

    # If general staff, only show own leave requests
    if session.get("role") == "staff":
        query += " AND l.staff_id = ?"
        params.append(session.get("staff_id", 0))

    if status_filter in ["pending", "approved", "rejected"]:
        query += " AND l.status = ?"
        params.append(status_filter)

    query += " ORDER BY l.created_at DESC"
    cursor.execute(query, params)
    leave_requests = cursor.fetchall()
    conn.close()

    return render_template(
        "leave/list.html",
        leave_requests=leave_requests,
        status_filter=status_filter
    )


@app.route("/leave/request", methods=["GET", "POST"])
@login_required
def leave_request_create():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":
        staff_id = request.form.get("staff_id") if session.get("role") in ["admin", "clerk"] else session.get("staff_id")
        leave_type = request.form.get("leave_type")
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")
        reason = request.form.get("reason", "").strip()

        # Calculate days
        try:
            d1 = datetime.strptime(start_date, "%Y-%m-%d")
            d2 = datetime.strptime(end_date, "%Y-%m-%d")
            total_days = max(1, (d2 - d1).days + 1)
        except Exception:
            total_days = 1

        cursor.execute("""
            INSERT INTO leave_requests (staff_id, leave_type, start_date, end_date, total_days, reason, status)
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
        """, (staff_id, leave_type, start_date, end_date, total_days, reason))
        conn.commit()
        conn.close()
        flash("ពាក្យស្នើសុំច្បាប់ត្រូវបានដាក់ជូនដោយជោគជ័យ! សូមរង់ចាំការពិនិត្យ និងអនុម័តពីមេឃុំ/ស្មៀន។", "success")
        return redirect(url_for("leave_list"))

    # Get staff list for dropdown if admin/clerk
    staff_list = []
    if session.get("role") in ["admin", "clerk"]:
        cursor.execute("SELECT id, officer_code, name_kh, position_title_kh FROM staff WHERE status = 'active' ORDER BY name_kh")
        staff_list = cursor.fetchall()
    conn.close()

    return render_template("leave/request.html", staff_list=staff_list)


@app.route("/leave/<int:leave_id>/action", methods=["POST"])
@clerk_or_admin_required
def leave_action(leave_id):
    action = request.form.get("action")  # 'approve' or 'reject'
    remarks = request.form.get("remarks", "").strip()
    status = "approved" if action == "approve" else "rejected"

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE leave_requests
        SET status = ?, approved_by = ?, approval_remarks = ?, approved_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (status, session.get("user_id"), remarks, leave_id))

    # If approved, update attendance table for that date range
    if status == "approved":
        cursor.execute("SELECT staff_id, start_date, end_date FROM leave_requests WHERE id = ?", (leave_id,))
        lr = cursor.fetchone()
        if lr:
            d_start = datetime.strptime(lr["start_date"], "%Y-%m-%d").date()
            d_end = datetime.strptime(lr["end_date"], "%Y-%m-%d").date()
            cur = d_start
            while cur <= d_end:
                if cur.weekday() < 5:
                    cursor.execute("""
                        INSERT INTO attendance (staff_id, date, status, remarks, recorded_by)
                        VALUES (?, ?, 'on_leave', 'អនុញ្ញាតច្បាប់ឈប់សម្រាក', ?)
                        ON CONFLICT(staff_id, date) DO UPDATE SET
                            status = 'on_leave',
                            remarks = 'អនុញ្ញាតច្បាប់ឈប់សម្រាក'
                    """, (lr["staff_id"], cur.strftime("%Y-%m-%d"), session.get("user_id")))
                cur += timedelta(days=1)

    conn.commit()
    conn.close()
    flash(f"បាន{'អនុម័ត' if status == 'approved' else 'បដិសេធ'}សំណើសុំច្បាប់ដោយជោគជ័យ!", "success")
    return redirect(url_for("leave_list"))


@app.route("/leave/<int:leave_id>/print")
@login_required
def leave_print_slip(leave_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT l.*, s.officer_code, s.name_kh, s.position_title_kh, s.category, s.village,
               u.full_name as approver_name
        FROM leave_requests l
        JOIN staff s ON l.staff_id = s.id
        LEFT JOIN users u ON l.approved_by = u.id
        WHERE l.id = ?
    """, (leave_id,))
    leave_req = cursor.fetchone()
    conn.close()
    if not leave_req:
        abort(404)

    return render_template("leave/print_slip.html", leave=leave_req)


# ==============================================================================
# MISSIONS & FIELDWORK TRACKING
# ==============================================================================

@app.route("/missions")
@login_required
def mission_list():
    period = request.args.get("period", "all")  # all, week, month, year
    selected_year = request.args.get("year", type=int)
    selected_month = request.args.get("month", type=int)
    selected_week = request.args.get("week", "this_week")  # this_week, last_week
    status_filter = request.args.get("status", "all")
    search_query = request.args.get("q", "").strip()

    today = date.today()
    if not selected_year:
        selected_year = today.year
    if not selected_month:
        selected_month = today.month

    conn = get_db()
    cursor = conn.cursor()

    query = """
        SELECT m.*, COUNT(mp.id) as participant_count
        FROM missions m
        LEFT JOIN mission_participants mp ON m.id = mp.mission_id
        WHERE 1=1
    """
    params = []

    filter_label = ""

    # 1. Period Filtering
    if period == "week":
        if selected_week == "last_week":
            start_week = today - timedelta(days=today.weekday() + 7)
            end_week = start_week + timedelta(days=6)
            filter_label = f"សប្តាហ៍មុន ({start_week.strftime('%d/%m')} - {end_week.strftime('%d/%m/%Y')})"
        else:
            selected_week = "this_week"
            start_week = today - timedelta(days=today.weekday())
            end_week = start_week + timedelta(days=6)
            filter_label = f"សប្តាហ៍នេះ ({start_week.strftime('%d/%m')} - {end_week.strftime('%d/%m/%Y')})"

        query += " AND (m.start_date <= ? AND m.end_date >= ?)"
        params.extend([end_week.strftime("%Y-%m-%d"), start_week.strftime("%Y-%m-%d")])

    elif period == "month":
        _, last_day = calendar.monthrange(selected_year, selected_month)
        start_m = f"{selected_year:04d}-{selected_month:02d}-01"
        end_m = f"{selected_year:04d}-{selected_month:02d}-{last_day:02d}"
        query += " AND (m.start_date <= ? AND m.end_date >= ?)"
        params.extend([end_m, start_m])
        m_name = KHMER_MONTHS[selected_month] if 1 <= selected_month <= 12 else str(selected_month)
        filter_label = f"ខែ{m_name} ឆ្នាំ{to_khmer_num(selected_year)}"

    elif period == "year":
        start_y = f"{selected_year:04d}-01-01"
        end_y = f"{selected_year:04d}-12-31"
        query += " AND (m.start_date <= ? AND m.end_date >= ?)"
        params.extend([end_y, start_y])
        filter_label = f"ឆ្នាំ{to_khmer_num(selected_year)}"

    # 2. Status Filter
    if status_filter and status_filter != "all":
        query += " AND m.status = ?"
        params.append(status_filter)

    # 3. Search Query (Not applied when filtering by month)
    if search_query and period != "month":
        query += " AND (m.mission_code LIKE ? OR m.title LIKE ? OR m.destination LIKE ? OR m.purpose LIKE ? OR m.mission_order_no LIKE ?)"
        term = f"%{search_query}%"
        params.extend([term, term, term, term, term])

    query += " GROUP BY m.id ORDER BY m.start_date DESC, m.id DESC"
    cursor.execute(query, params)
    missions = cursor.fetchall()

    # Get available years from missions in database
    cursor.execute("SELECT DISTINCT CAST(substr(start_date, 1, 4) AS INTEGER) as yr FROM missions WHERE start_date IS NOT NULL AND start_date != '' ORDER BY yr DESC")
    available_years = [r[0] for r in cursor.fetchall() if r[0]]
    if today.year not in available_years:
        available_years.insert(0, today.year)
    available_years = sorted(list(set(available_years)), reverse=True)

    conn.close()

    return render_template(
        "mission/list.html",
        missions=missions,
        period=period,
        selected_year=selected_year,
        selected_month=selected_month,
        selected_week=selected_week,
        status_filter=status_filter,
        search_query=search_query,
        available_years=available_years,
        khmer_months=KHMER_MONTHS,
        filter_label=filter_label
    )


@app.route("/missions/new", methods=["GET", "POST"])
@clerk_or_admin_required
def mission_create():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        destination = request.form.get("destination", "").strip()
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")
        mission_order_no = request.form.get("mission_order_no", "").strip()
        purpose = request.form.get("purpose", "").strip()
        allowance_per_day = float(request.form.get("allowance_per_day", 0) or 0)
        selected_staff_ids = request.form.getlist("staff_ids")

        # Calculate days
        try:
            d1 = datetime.strptime(start_date, "%Y-%m-%d")
            d2 = datetime.strptime(end_date, "%Y-%m-%d")
            total_days = max(1, (d2 - d1).days + 1)
        except Exception:
            total_days = 1

        total_allowance = allowance_per_day * total_days * len(selected_staff_ids)

        cursor.execute("SELECT MAX(id) FROM missions")
        last_id = cursor.fetchone()[0] or 0
        mission_code = f"MS-2026-{str(last_id + 1).zfill(3)}"

        # Handle reference document upload (File រូបភាព ឬ PDF)
        attachment_filename = None
        if "attachment" in request.files:
            file = request.files["attachment"]
            if file and file.filename != "":
                orig_filename = secure_filename(file.filename)
                ext = os.path.splitext(orig_filename)[1].lower()
                if ext in [".pdf", ".png", ".jpg", ".jpeg", ".webp"]:
                    timestamp = int(datetime.now().timestamp())
                    safe_code = mission_code.replace("-", "_")
                    attachment_filename = f"mission_{safe_code}_{timestamp}{ext}"
                    filepath = os.path.join(app.config["UPLOAD_FOLDER"], attachment_filename)
                    file.save(filepath)

        cursor.execute("""
            INSERT INTO missions (
                mission_code, title, destination, start_date, end_date, total_days,
                mission_order_no, purpose, allowance_per_day, total_allowance, attachment, status, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'in_progress', ?)
        """, (
            mission_code, title, destination, start_date, end_date, total_days,
            mission_order_no, purpose, allowance_per_day, total_allowance, attachment_filename, session.get("user_id")
        ))
        new_mission_id = cursor.lastrowid

        # Insert participants & update attendance
        for sid in selected_staff_ids:
            cursor.execute("""
                INSERT INTO mission_participants (mission_id, staff_id, role_in_mission, allowance)
                VALUES (?, ?, 'សមាជិកបេសកកម្ម', ?)
            """, (new_mission_id, sid, allowance_per_day * total_days))

            # Mark attendance as mission
            cur_d = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_d = datetime.strptime(end_date, "%Y-%m-%d").date()
            while cur_d <= end_d:
                if cur_d.weekday() < 5:
                    cursor.execute("""
                        INSERT INTO attendance (staff_id, date, status, remarks, recorded_by)
                        VALUES (?, ?, 'mission', ?, ?)
                        ON CONFLICT(staff_id, date) DO UPDATE SET
                            status = 'mission',
                            remarks = excluded.remarks
                    """, (sid, cur_d.strftime("%Y-%m-%d"), f"បេសកកម្ម៖ {title}", session.get("user_id")))
                cur_d += timedelta(days=1)

        conn.commit()
        conn.close()
        flash(f"បានបង្កើតបេសកកម្ម {title} ដោយជោគជ័យ!", "success")
        return redirect(url_for("mission_list"))

    cursor.execute("SELECT id, officer_code, name_kh, position_title_kh, category FROM staff WHERE status = 'active' ORDER BY name_kh")
    active_staff = cursor.fetchall()
    conn.close()

    return render_template("mission/form.html", active_staff=active_staff)


@app.route("/missions/<int:mission_id>/print-order")
@login_required
def mission_print_order(mission_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM missions WHERE id = ?", (mission_id,))
    mission = cursor.fetchone()
    if not mission:
        conn.close()
        abort(404)

    cursor.execute("""
        SELECT mp.*, s.officer_code, s.name_kh, s.gender, s.position_title_kh, s.category
        FROM mission_participants mp
        JOIN staff s ON mp.staff_id = s.id
        WHERE mp.mission_id = ?
    """, (mission_id,))
    participants = cursor.fetchall()
    conn.close()

    return render_template("mission/print_order.html", mission=mission, participants=participants)


# ==============================================================================
# PAYROLL & ALLOWANCES (មុខងារទី៣)
# ==============================================================================

@app.route("/payroll")
@login_required
def payroll_list():
    month_year = request.args.get("month", date.today().strftime("%Y-%m"))

    conn = get_db()
    cursor = conn.cursor()

    # If general staff, only show own payroll
    query = """
        SELECT p.*, s.officer_code, s.name_kh, s.position_title_kh, s.category, s.village
        FROM payroll p
        JOIN staff s ON p.staff_id = s.id
        WHERE p.month_year = ?
    """
    params = [month_year]

    if session.get("role") == "staff":
        query += " AND p.staff_id = ?"
        params.append(session.get("staff_id", 0))

    query += " ORDER BY CASE s.category WHEN 'council' THEN 1 WHEN 'clerk' THEN 2 WHEN 'contract' THEN 3 ELSE 4 END, s.id"

    cursor.execute(query, params)
    payroll_records = cursor.fetchall()

    # Totals
    cursor.execute("""
        SELECT COALESCE(SUM(base_salary), 0) as tot_base,
               COALESCE(SUM(position_allowance), 0) as tot_pos,
               COALESCE(SUM(mission_allowance), 0) as tot_miss,
               COALESCE(SUM(meeting_allowance), 0) as tot_meet,
               COALESCE(SUM(incentive_allowance), 0) as tot_inc,
               COALESCE(SUM(family_allowance), 0) as tot_fam,
               COALESCE(SUM(gross_salary), 0) as tot_gross,
               COALESCE(SUM(nssf_deduction), 0) as tot_nssf,
               COALESCE(SUM(attendance_deduction), 0) as tot_att_ded,
               COALESCE(SUM(tax_deduction), 0) as tot_tax_ded,
               COALESCE(SUM(nssf_deduction + attendance_deduction + tax_deduction), 0) as tot_ded,
               COALESCE(SUM(net_salary), 0) as tot_net,
               COUNT(*) as total_count
        FROM payroll
        WHERE month_year = ?
    """, (month_year,))
    totals_row = cursor.fetchone()
    if totals_row and totals_row["tot_base"] is not None:
        totals = dict(totals_row)
        totals["total_count"] = int(totals.get("total_count") or 0)
        totals["count"] = totals["total_count"]
        totals["tot_ded"] = float(totals.get("tot_ded") or (totals.get("tot_nssf", 0) + totals.get("tot_att_ded", 0) + totals.get("tot_tax_ded", 0)))
    else:
        totals = {
            "tot_base": 0, "tot_pos": 0, "tot_miss": 0, "tot_meet": 0,
            "tot_inc": 0, "tot_fam": 0, "tot_gross": 0, "tot_nssf": 0,
            "tot_att_ded": 0, "tot_tax_ded": 0, "tot_ded": 0,
            "tot_net": 0, "count": 0, "total_count": 0
        }

    conn.close()

    return render_template(
        "payroll/list.html",
        month_year=month_year,
        payroll_records=payroll_records,
        totals=totals
    )


@app.route("/payroll/generate", methods=["POST"])
@clerk_or_admin_required
def payroll_generate():
    month_year = request.form.get("month_year", date.today().strftime("%Y-%m"))

    # Extract month number (e.g. '04' for April, '10' for October)
    month_num = month_year.split("-")[1] if "-" in month_year else ""

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM staff WHERE status = 'active'")
    staff_list = cursor.fetchall()

    for s in staff_list:
        sid = s["id"]
        base = s["base_salary"] or 0

        # ប្រាក់ឧបត្ថម្ភចូលឆ្នាំ (Khmer New Year Allowance): បើកតែក្នុងខែមេសា (Month 04) ប៉ុណ្ណោះ
        pos_all = (s["position_allowance"] or 0) if month_num == "04" else 0

        # ប្រាក់ឧបត្ថម្ភភ្ជុំបិណ្ឌ (Pchum Ben Allowance): បើកតែក្នុងខែតុលា (Month 10) ប៉ុណ្ណោះ
        fam_all = (s["family_allowance"] or 0) if month_num == "10" else 0

        gross = base + pos_all + fam_all
        # មិនកាត់ ប.ស.ស ឬប្រាក់កាត់ណាមួយស្វ័យប្រវត្តិទេ (ទុក 0៛ សម្រាប់អ្នកប្រើប្រាស់កំណត់ដោយដៃតាមជាក់ស្តែង)
        nssf = 0
        net = gross

        remarks = "ទូទាត់ប្រាក់បៀវត្សរ៍ប្រចាំខែ"
        if month_num == "04":
            remarks = "ទូទាត់ប្រាក់បៀវត្សរ៍ និងប្រាក់ឧបត្ថម្ភចូលឆ្នាំ"
        elif month_num == "10":
            remarks = "ទូទាត់ប្រាក់បៀវត្សរ៍ និងប្រាក់ឧបត្ថម្ភភ្ជុំបិណ្ឌ"

        cursor.execute("""
            INSERT INTO payroll (
                staff_id, month_year, base_salary, position_allowance, mission_allowance,
                meeting_allowance, incentive_allowance, family_allowance, gross_salary,
                nssf_deduction, attendance_deduction, tax_deduction, net_salary,
                payment_status, paid_date, payment_method, remarks
            ) VALUES (?, ?, ?, ?, 0, 0, 0, ?, ?, 0, 0, 0, ?, 'paid', ?, 'Wing', ?)
            ON CONFLICT(staff_id, month_year) DO UPDATE SET
                base_salary = excluded.base_salary,
                position_allowance = excluded.position_allowance,
                mission_allowance = excluded.mission_allowance,
                meeting_allowance = excluded.meeting_allowance,
                incentive_allowance = excluded.incentive_allowance,
                family_allowance = excluded.family_allowance,
                gross_salary = excluded.gross_salary,
                net_salary = excluded.gross_salary - (payroll.nssf_deduction + payroll.attendance_deduction + payroll.tax_deduction),
                remarks = excluded.remarks
        """, (
            sid, month_year, base, pos_all,
            fam_all, gross, net, date.today().strftime("%Y-%m-%d"), remarks
        ))

    conn.commit()
    conn.close()

    flash(f"បានគណនា និងបង្កើតតារាងប្រាក់បៀវត្សរ៍សម្រាប់ខែ {month_year} រួចរាល់ (មិនកាត់ប្រាក់ស្វ័យប្រវត្តិ)!", "success")
    return redirect(url_for("payroll_list", month=month_year))


@app.route("/payroll/<int:payroll_id>/deductions", methods=["POST"])
@clerk_or_admin_required
def payroll_update_deductions(payroll_id):
    """Update custom deduction components (NSSF, Attendance, Tax/Other) for a payroll record."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT p.*, s.name_kh, s.officer_code
        FROM payroll p
        JOIN staff s ON p.staff_id = s.id
        WHERE p.id = ?
    """, (payroll_id,))
    record = cursor.fetchone()

    if not record:
        conn.close()
        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
            return jsonify({"success": False, "message": "រកមិនឃើញទិន្នន័យប្រាក់បៀវត្សរ៍នេះទេ"}), 404
        flash("រកមិនឃើញទិន្នន័យប្រាក់បៀវត្សរ៍នេះទេ!", "danger")
        return redirect(url_for("payroll_list"))

    try:
        nssf_deduction = float(request.form.get("nssf_deduction", 0) or 0)
    except (ValueError, TypeError):
        nssf_deduction = float(record["nssf_deduction"] or 0)

    try:
        attendance_deduction = float(request.form.get("attendance_deduction", 0) or 0)
    except (ValueError, TypeError):
        attendance_deduction = float(record["attendance_deduction"] or 0)

    try:
        tax_deduction = float(request.form.get("tax_deduction", 0) or 0)
    except (ValueError, TypeError):
        tax_deduction = float(record["tax_deduction"] or 0)

    remarks = request.form.get("remarks", "").strip() or record["remarks"]

    gross = float(record["gross_salary"] or 0)
    total_deductions = nssf_deduction + attendance_deduction + tax_deduction
    net_salary = max(0, gross - total_deductions)

    cursor.execute("""
        UPDATE payroll SET
            nssf_deduction = ?,
            attendance_deduction = ?,
            tax_deduction = ?,
            net_salary = ?,
            remarks = ?
        WHERE id = ?
    """, (nssf_deduction, attendance_deduction, tax_deduction, net_salary, remarks, payroll_id))

    conn.commit()
    conn.close()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
        return jsonify({
            "success": True,
            "message": f"បានរក្សាទុកប្រាក់កាត់សម្រាប់មន្ត្រី {record['name_kh']} ដោយជោគជ័យ!",
            "payroll_id": payroll_id,
            "nssf_deduction": nssf_deduction,
            "attendance_deduction": attendance_deduction,
            "tax_deduction": tax_deduction,
            "total_deductions": total_deductions,
            "net_salary": net_salary,
            "formatted_deductions": f"-{total_deductions:,.0f} រៀល",
            "formatted_net_salary": f"{net_salary:,.0f} រៀល"
        })

    flash(f"បានរក្សាទុកប្រាក់កាត់សម្រាប់មន្ត្រី {record['name_kh']} រួចរាល់!", "success")
    return redirect(url_for("payroll_list", month=record["month_year"]))


@app.route("/payroll/<int:payroll_id>/payslip")
@login_required
def payroll_payslip(payroll_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.*, s.officer_code, s.name_kh, s.name_en, s.gender, s.position_title_kh,
               s.category, s.village, s.phone, s.national_id, s.cadre_level
        FROM payroll p
        JOIN staff s ON p.staff_id = s.id
        WHERE p.id = ?
    """, (payroll_id,))
    payslip = cursor.fetchone()
    conn.close()

    if not payslip:
        abort(404)

    # Permission check for general staff
    if session.get("role") == "staff" and session.get("staff_id") != payslip["staff_id"]:
        flash("លោកអ្នកមិនមានសិទ្ធិមើលប័ណ្ណបើកប្រាក់បៀវត្សរ៍របស់អ្នកដទៃទេ!", "danger")
        return redirect(url_for("payroll_list"))

    return render_template("payroll/payslip.html", p=payslip)


# ==============================================================================
# EVALUATION & ACHIEVEMENTS (មុខងារទី៤)
# ==============================================================================

@app.route("/evaluation/trainings", methods=["GET", "POST"])
@login_required
def evaluation_trainings():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST" and session.get("role") in ["admin", "clerk"]:
        staff_id = request.form.get("staff_id")
        course_title = request.form.get("course_title", "").strip()
        organizer = request.form.get("organizer", "").strip()
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")
        duration_days = int(request.form.get("duration_days", 1) or 1)
        location = request.form.get("location", "").strip()
        certificate_title = request.form.get("certificate_title", "").strip()
        notes = request.form.get("notes", "").strip()

        cursor.execute("""
            INSERT INTO trainings (
                staff_id, course_title, organizer, start_date, end_date,
                duration_days, location, certificate_title, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (staff_id, course_title, organizer, start_date, end_date, duration_days, location, certificate_title, notes))
        conn.commit()
        flash(f"បានកត់ត្រាវគ្គបណ្តុះបណ្តាល «{course_title}» ដោយជោគជ័យ!", "success")
        return redirect(url_for("evaluation_trainings"))

    cursor.execute("""
        SELECT t.*, s.officer_code, s.name_kh, s.position_title_kh, s.category
        FROM trainings t
        JOIN staff s ON t.staff_id = s.id
        ORDER BY t.start_date DESC
    """)
    trainings = cursor.fetchall()

    cursor.execute("SELECT id, officer_code, name_kh, position_title_kh FROM staff WHERE status = 'active' ORDER BY name_kh")
    active_staff = cursor.fetchall()
    conn.close()

    return render_template("evaluation/trainings.html", trainings=trainings, active_staff=active_staff)


@app.route("/evaluation/achievements", methods=["GET", "POST"])
@login_required
def evaluation_achievements():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST" and session.get("role") in ["admin", "clerk"]:
        staff_id = request.form.get("staff_id")
        honor_type = request.form.get("honor_type", "letter_of_praise")
        title = request.form.get("title", "").strip()
        awarded_by = request.form.get("awarded_by", "").strip()
        decree_prakas_no = request.form.get("decree_prakas_no", "").strip()
        award_date = request.form.get("award_date")
        description = request.form.get("description", "").strip()

        cursor.execute("""
            INSERT INTO achievements (
                staff_id, honor_type, title, awarded_by, decree_prakas_no, award_date, description
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (staff_id, honor_type, title, awarded_by, decree_prakas_no, award_date, description))
        conn.commit()
        flash(f"បានកត់ត្រាស្នាដៃ/គ្រឿងឥស្សរិយយស «{title}» ដោយជោគជ័យ!", "success")
        return redirect(url_for("evaluation_achievements"))

    cursor.execute("""
        SELECT a.*, s.officer_code, s.name_kh, s.position_title_kh, s.category
        FROM achievements a
        JOIN staff s ON a.staff_id = s.id
        ORDER BY a.award_date DESC
    """)
    achievements = cursor.fetchall()

    cursor.execute("SELECT id, officer_code, name_kh, position_title_kh FROM staff WHERE status = 'active' ORDER BY name_kh")
    active_staff = cursor.fetchall()
    conn.close()

    return render_template("evaluation/achievements.html", achievements=achievements, active_staff=active_staff)


# ==============================================================================
# REPORTING & EXPORTS (មុខងារទី៥)
# ==============================================================================

@app.route("/reports")
@login_required
def reports_hub():
    conn = get_db()
    cursor = conn.cursor()

    # Demographic breakdown by Category & Gender
    cursor.execute("""
        SELECT category, gender, COUNT(*) as staff_count
        FROM staff
        WHERE status = 'active'
        GROUP BY category, gender
    """)
    cat_gender_rows = cursor.fetchall()

    # Village distribution
    cursor.execute("""
        SELECT village, COUNT(*) as staff_count
        FROM staff
        WHERE status = 'active'
        GROUP BY village
    """)
    village_dist = cursor.fetchall()

    # Total salary by category
    cursor.execute("""
        SELECT category, SUM(base_salary) as tot_base
        FROM staff
        WHERE status = 'active'
        GROUP BY category
    """)
    salary_by_cat = cursor.fetchall()

    conn.close()

    return render_template(
        "reports/index.html",
        cat_gender_rows=cat_gender_rows,
        village_dist=village_dist,
        salary_by_cat=salary_by_cat
    )


@app.route("/reports/export/attendance-daily-excel")
@login_required
def export_daily_attendance_excel_route():
    target_date = request.args.get("date", get_today_str())
    excel_stream = export_daily_attendance_excel(target_date)
    filename = f"Daily_Attendance_NokorPheas_{target_date}.xlsx"
    return send_file(
        excel_stream,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )


@app.route("/attendance/daily-print")
@login_required
def attendance_daily_print():
    target_date = request.args.get("date", get_today_str())
    try:
        target_dt = datetime.strptime(target_date, "%Y-%m-%d").date()
    except Exception:
        target_dt = get_today()
        target_date = get_today_str()

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.id, s.officer_code, s.name_kh, s.name_en, s.gender, s.position_title_kh, s.category, s.village,
               a.check_in_time, a.check_out_time, a.status, a.remarks
        FROM staff s
        LEFT JOIN attendance a ON s.id = a.staff_id AND a.date = ?
        WHERE s.status = 'active'
        ORDER BY 
            CASE s.category 
                WHEN 'council' THEN 1 
                WHEN 'clerk' THEN 2 
                WHEN 'contract' THEN 3 
                ELSE 4 
            END, s.id ASC
    """, (target_date,))
    records = cursor.fetchall()
    conn.close()

    total_staff = len(records)
    cnt_present = sum(1 for r in records if r["status"] == "present")
    cnt_late = sum(1 for r in records if r["status"] == "late")
    cnt_leave = sum(1 for r in records if r["status"] == "leave")
    cnt_mission = sum(1 for r in records if r["status"] == "mission")
    cnt_absent = sum(1 for r in records if r["status"] == "absent")
    cnt_unrecorded = sum(1 for r in records if not r["status"])

    return render_template(
        "attendance/daily_print.html",
        target_date=target_date,
        target_date_kh=format_khmer_date(target_dt),
        records=records,
        total_staff=total_staff,
        cnt_present=cnt_present,
        cnt_late=cnt_late,
        cnt_leave=cnt_leave,
        cnt_mission=cnt_mission,
        cnt_absent=cnt_absent,
        cnt_unrecorded=cnt_unrecorded,
        categories=STAFF_CATEGORIES,
        statuses=ATTENDANCE_STATUSES
    )


@app.route("/reports/export/attendance-excel")
@login_required
def export_attendance_excel_route():
    month = request.args.get("month", date.today().strftime("%Y-%m"))
    excel_stream = export_monthly_attendance_excel(month)
    filename = f"Attendance_Report_NokorPheas_{month}.xlsx"
    return send_file(
        excel_stream,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )


@app.route("/reports/export/staff-excel")
@login_required
def export_staff_excel_route():
    category = request.args.get("category", "")
    excel_stream = export_staff_list_excel(category if category else None)
    cat_suffix = f"_{category}" if category else "_All"
    filename = f"Staff_Census_NokorPheas{cat_suffix}.xlsx"
    return send_file(
        excel_stream,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )


@app.route("/reports/export/payroll-excel")
@login_required
def export_payroll_excel_route():
    month = request.args.get("month", date.today().strftime("%Y-%m"))
    excel_stream = export_payroll_excel(month)
    filename = f"Payroll_Sheet_NokorPheas_{month}.xlsx"
    return send_file(
        excel_stream,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )


# ==============================================================================
# USER MANAGEMENT & ROLES (មុខងារទី៦)
# ==============================================================================

@app.route("/settings/users", methods=["GET", "POST"])
@admin_required
def settings_users():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":
        action = request.form.get("action")
        if action == "create":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()
            full_name = request.form.get("full_name", "").strip()
            role = request.form.get("role", "staff")
            staff_id = request.form.get("staff_id") or None

            if not username or not password or not full_name:
                flash("សូមបំពេញព័ត៌មានចាំបាច់ទាំងអស់ (ឈ្មោះគណនី, ពាក្យសម្ងាត់, ឈ្មោះពេញ)!", "warning")
            else:
                # Check for existing username (case-insensitive)
                cursor.execute("SELECT id FROM users WHERE LOWER(username) = LOWER(?)", (username,))
                existing_user = cursor.fetchone()
                if existing_user:
                    flash(f"ឈ្មោះគណនី '{username}' មានរួចហើយក្នុងប្រព័ន្ធ! សូមជ្រើសរើសឈ្មោះគណនីផ្សេង។", "danger")
                else:
                    try:
                        cursor.execute("""
                            INSERT INTO users (username, password_hash, full_name, role, staff_id)
                            VALUES (?, ?, ?, ?, ?)
                        """, (username, generate_password_hash(password), full_name, role, staff_id))
                        conn.commit()
                        flash(f"បានបង្កើតគណនី '{username}' ដោយជោគជ័យ!", "success")
                    except Exception as e:
                        conn.rollback()
                        flash(f"មានបញ្ហាក្នុងការបង្កើតគណនី៖ {str(e)}", "danger")

        elif action == "edit":
            uid = request.form.get("user_id")
            full_name = request.form.get("full_name", "").strip()
            role = request.form.get("role", "staff")
            staff_id = request.form.get("staff_id") or None
            new_password = request.form.get("password", "").strip()

            if not uid or not full_name:
                flash("សូមបំពេញព័ត៌មានឈ្មោះពេញ!", "warning")
            else:
                try:
                    if new_password:
                        cursor.execute("""
                            UPDATE users SET full_name = ?, role = ?, staff_id = ?, password_hash = ?
                            WHERE id = ?
                        """, (full_name, role, staff_id, generate_password_hash(new_password), uid))
                    else:
                        cursor.execute("""
                            UPDATE users SET full_name = ?, role = ?, staff_id = ?
                            WHERE id = ?
                        """, (full_name, role, staff_id, uid))
                    conn.commit()
                    flash("បានកែប្រែព័ត៌មានគណនីដោយជោគជ័យ!", "success")
                except Exception as e:
                    conn.rollback()
                    flash(f"មានបញ្ហាក្នុងការកែប្រែព័ត៌មានគណនី៖ {str(e)}", "danger")

        elif action == "toggle_status":
            uid = request.form.get("user_id")
            if uid:
                if str(uid) == str(session.get("user_id")):
                    flash("មិនអាចបិទ/ផ្អាកគណនីដែលលោកអ្នកកំពុងប្រើប្រាស់បានទេ!", "warning")
                else:
                    try:
                        cursor.execute("UPDATE users SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id = ?", (uid,))
                        conn.commit()
                        flash("បានផ្លាស់ប្តូរស្ថានភាពគណនីរួចរាល់!", "info")
                    except Exception as e:
                        conn.rollback()
                        flash(f"មិនអាចផ្លាស់ប្តូរស្ថានភាពគណនីបានទេ៖ {str(e)}", "danger")

        elif action == "reset_password":
            uid = request.form.get("user_id")
            new_password = request.form.get("new_password", "").strip()
            if not uid or not new_password:
                flash("សូមបញ្ចូលពាក្យសម្ងាត់ថ្មី!", "warning")
            else:
                try:
                    cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(new_password), uid))
                    conn.commit()
                    flash("បានកំណត់ពាក្យសម្ងាត់ថ្មីដោយជោគជ័យ!", "success")
                except Exception as e:
                    conn.rollback()
                    flash(f"មានបញ្ហាក្នុងការកំណត់ពាក្យសម្ងាត់៖ {str(e)}", "danger")

        elif action == "delete":
            uid = request.form.get("user_id")
            if uid:
                if str(uid) == str(session.get("user_id")):
                    flash("មិនអាចលុបគណនីដែលកំពុងប្រើប្រាស់បានទេ!", "danger")
                else:
                    try:
                        cursor.execute("DELETE FROM users WHERE id = ?", (uid,))
                        conn.commit()
                        flash("បានលុបគណនីដោយជោគជ័យ!", "success")
                    except Exception as e:
                        conn.rollback()
                        flash(f"មានបញ្ហាក្នុងការលុបគណនី៖ {str(e)}", "danger")

        conn.close()
        return redirect(url_for("settings_users"))

    cursor.execute("""
        SELECT u.*, s.name_kh as linked_staff_name, s.officer_code
        FROM users u
        LEFT JOIN staff s ON u.staff_id = s.id
        ORDER BY u.id
    """)
    users = cursor.fetchall()

    cursor.execute("SELECT id, officer_code, name_kh, position_title_kh FROM staff WHERE status = 'active' ORDER BY name_kh")
    active_staff = cursor.fetchall()
    conn.close()

    return render_template("settings/users.html", users=users, active_staff=active_staff)


@app.route("/settings/profile", methods=["GET", "POST"])
@login_required
def user_profile():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        new_password = request.form.get("new_password", "").strip()

        if new_password:
            cursor.execute("""
                UPDATE users SET full_name = ?, password_hash = ? WHERE id = ?
            """, (full_name, generate_password_hash(new_password), session.get("user_id")))
        else:
            cursor.execute("""
                UPDATE users SET full_name = ? WHERE id = ?
            """, (full_name, session.get("user_id")))

        session["full_name"] = full_name
        conn.commit()
        conn.close()
        flash("បានកែប្រែព័ត៌មានគណនីដោយជោគជ័យ!", "success")
        return redirect(url_for("user_profile"))

    cursor.execute("""
        SELECT u.*, s.name_kh, s.officer_code, s.position_title_kh, s.category, s.village, s.phone, s.email
        FROM users u
        LEFT JOIN staff s ON u.staff_id = s.id
        WHERE u.id = ?
    """, (session.get("user_id"),))
    user = cursor.fetchone()
    conn.close()

    return render_template("settings/profile.html", user=user)


@app.route("/settings/villages")
@login_required
def settings_villages():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM villages ORDER BY id")
    villages = cursor.fetchall()

    total_villages = len(villages)
    total_families = sum(v["total_families"] or 0 for v in villages)
    total_population = sum(v["total_population"] or 0 for v in villages)
    total_female = sum(v["female_population"] or 0 for v in villages)
    total_male = total_population - total_female
    female_pct = round((total_female / total_population * 100), 1) if total_population > 0 else 0
    conn.close()

    return render_template(
        "settings/villages.html",
        villages=villages,
        total_villages=total_villages,
        total_families=total_families,
        total_population=total_population,
        total_female=total_female,
        total_male=total_male,
        female_pct=female_pct
    )


@app.route("/settings/villages/<int:village_id>/edit", methods=["POST"])
@clerk_or_admin_required
def village_edit(village_id):
    total_families = int(request.form.get("total_families", 0) or 0)
    total_population = int(request.form.get("total_population", 0) or 0)
    female_population = int(request.form.get("female_population", 0) or 0)
    village_name_kh = request.form.get("village_name_kh", "").strip()
    village_name_en = request.form.get("village_name_en", "").strip()

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE villages 
        SET total_families = ?, total_population = ?, female_population = ?,
            village_name_kh = COALESCE(NULLIF(?, ''), village_name_kh),
            village_name_en = COALESCE(NULLIF(?, ''), village_name_en)
        WHERE id = ?
    """, (total_families, total_population, female_population, village_name_kh, village_name_en, village_id))
    conn.commit()
    conn.close()

    flash(f"បានកែប្រែទិន្នន័យស្ថិតិភូមិ {village_name_kh or ''} ដោយជោគជ័យ!", "success")
    return redirect(url_for("settings_villages"))


# ==============================================================================
# COMMUNE ADMINISTRATIVE CALENDAR ROUTES (ប្រតិទិនកិច្ចការ និងកិច្ចប្រជុំរដ្ឋបាលឃុំ)
# ==============================================================================

EVENT_TYPES = {
    "ordinary_meeting": {
        "title_kh": "ប្រជុំសាមញ្ញក្រុមប្រឹក្សាឃុំ",
        "badge_class": "badge-info",
        "color": "#3b82f6",
        "icon": "fa-users-line"
    },
    "extraordinary_meeting": {
        "title_kh": "ប្រជុំវិសាមញ្ញក្រុមប្រឹក្សាឃុំ",
        "badge_class": "badge-purple",
        "color": "#8b5cf6",
        "icon": "fa-user-group"
    },
    "public_forum": {
        "title_kh": "វេទិកាសាធារណៈ",
        "badge_class": "badge-success",
        "color": "#10b981",
        "icon": "fa-bullhorn"
    },
    "ceremony": {
        "title_kh": "ពិធីបុណ្យជាតិ / ទិវាផ្សេងៗ",
        "badge_class": "badge-warning",
        "color": "#f59e0b",
        "icon": "fa-landmark-flag"
    },
    "urgent": {
        "title_kh": "កិច្ចការបន្ទាន់ / ពិសេស",
        "badge_class": "badge-danger",
        "color": "#ef4444",
        "icon": "fa-triangle-exclamation"
    },
    "training": {
        "title_kh": "វគ្គបណ្តុះបណ្តាល",
        "badge_class": "badge-clerk",
        "color": "#06b6d4",
        "icon": "fa-graduation-cap"
    },
    "other": {
        "title_kh": "កិច្ចការរដ្ឋបាលផ្សេងៗ",
        "badge_class": "badge-contract",
        "color": "#64748b",
        "icon": "fa-calendar-check"
    }
}

EVENT_STATUSES = {
    "scheduled": {"title_kh": "គ្រោងទុក", "badge_class": "badge-info"},
    "completed": {"title_kh": "បានបញ្ចប់", "badge_class": "badge-success"},
    "postponed": {"title_kh": "លើកពេល", "badge_class": "badge-warning"},
    "cancelled": {"title_kh": "លុបចោល", "badge_class": "badge-danger"},
}


@app.route("/calendar")
@login_required
def calendar_index():
    import calendar
    month_param = request.args.get("month", "").strip()
    selected_type = request.args.get("type", "").strip()
    search_query = request.args.get("search", "").strip()

    today = date.today()
    if month_param:
        try:
            year, month = map(int, month_param.split("-"))
        except ValueError:
            year, month = today.year, today.month
    else:
        year, month = today.year, today.month

    # Current month string (YYYY-MM)
    current_month_str = f"{year:04d}-{month:02d}"
    today_iso = today.strftime("%Y-%m-%d")

    # Previous and Next Month calculations
    if month == 1:
        prev_month_str = f"{year - 1:04d}-12"
    else:
        prev_month_str = f"{year:04d}-{month - 1:02d}"

    if month == 12:
        next_month_str = f"{year + 1:04d}-01"
    else:
        next_month_str = f"{year:04d}-{month + 1:02d}"

    conn = get_db()
    cursor = conn.cursor()

    # Query all events in this month
    query = """
        SELECT e.*, u.full_name as creator_name
        FROM commune_events e
        LEFT JOIN users u ON e.created_by = u.id
        WHERE e.event_date LIKE ?
    """
    params = [f"{current_month_str}%"]

    if selected_type and selected_type in EVENT_TYPES:
        query += " AND e.event_type = ?"
        params.append(selected_type)

    if search_query:
        query += " AND (e.title LIKE ? OR e.location LIKE ? OR e.chairperson LIKE ? OR e.description LIKE ?)"
        like_search = f"%{search_query}%"
        params.extend([like_search, like_search, like_search, like_search])

    query += " ORDER BY e.event_date ASC, e.start_time ASC"
    cursor.execute(query, params)
    month_events = cursor.fetchall()

    # Organize events by date
    events_by_date = {}
    for ev in month_events:
        d_str = ev["event_date"]
        if d_str not in events_by_date:
            events_by_date[d_str] = []
        events_by_date[d_str].append(dict(ev))

    # Query upcoming events from today onward (up to 6 events)
    cursor.execute("""
        SELECT e.*, u.full_name as creator_name
        FROM commune_events e
        LEFT JOIN users u ON e.created_by = u.id
        WHERE e.event_date >= ?
        ORDER BY e.event_date ASC, e.start_time ASC
        LIMIT 6
    """, (today_iso,))
    upcoming_events = cursor.fetchall()

    # Build Calendar Days Grid (Monday = 0 to Sunday = 6)
    first_date = date(year, month, 1)
    first_weekday = first_date.weekday()
    num_days = calendar.monthrange(year, month)[1]

    khmer_dow_short = ["ច័ន្ទ", "អង្គារ", "ពុធ", "ព្រហស្បតិ៍", "សុក្រ", "សៅរ៍", "អាទិត្យ"]
    
    calendar_days = []
    # Empty leading padding slots
    for _ in range(first_weekday):
        calendar_days.append({"is_empty": True})

    for day_num in range(1, num_days + 1):
        day_date = date(year, month, day_num)
        d_iso = day_date.strftime("%Y-%m-%d")
        dow_idx = day_date.weekday()
        calendar_days.append({
            "is_empty": False,
            "day": day_num,
            "date_iso": d_iso,
            "dow_kh": khmer_dow_short[dow_idx],
            "is_today": (d_iso == today_iso),
            "is_weekend": (dow_idx in (5, 6)),
            "events": events_by_date.get(d_iso, [])
        })

    # Stats for current month
    total_month_events = len(month_events)
    completed_month_events = sum(1 for e in month_events if e["status"] == "completed")
    scheduled_month_events = sum(1 for e in month_events if e["status"] == "scheduled")

    conn.close()

    return render_template(
        "calendar/index.html",
        year=year,
        month=month,
        current_month_str=current_month_str,
        prev_month_str=prev_month_str,
        next_month_str=next_month_str,
        today_iso=today_iso,
        calendar_days=calendar_days,
        khmer_dow_short=khmer_dow_short,
        month_events=month_events,
        upcoming_events=upcoming_events,
        events_by_date=events_by_date,
        total_month_events=total_month_events,
        completed_month_events=completed_month_events,
        scheduled_month_events=scheduled_month_events,
        EVENT_TYPES=EVENT_TYPES,
        EVENT_STATUSES=EVENT_STATUSES,
        selected_type=selected_type,
        search_query=search_query
    )


@app.route("/calendar/events/create", methods=["POST"])
@clerk_or_admin_required
def calendar_event_create():
    title = request.form.get("title", "").strip()
    event_type = request.form.get("event_type", "ordinary_meeting").strip()
    event_date = request.form.get("event_date", "").strip()
    start_time = request.form.get("start_time", "").strip()
    end_time = request.form.get("end_time", "").strip()
    location = request.form.get("location", "សាលាឃុំនគរភាស").strip()
    chairperson = request.form.get("chairperson", "").strip()
    participants = request.form.get("participants", "").strip()
    description = request.form.get("description", "").strip()
    status = request.form.get("status", "scheduled").strip()

    if not title or not event_date:
        flash("សូមបញ្ចូលចំណងជើង និងកាលបរិច្ឆេទនៃកិច្ចការ ឬអង្គប្រជុំ!", "danger")
        return redirect(url_for("calendar_index"))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO commune_events (
            title, event_type, event_date, start_time, end_time, location,
            chairperson, participants, description, status, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        title, event_type, event_date, start_time, end_time, location,
        chairperson, participants, description, status, session.get("user_id")
    ))
    conn.commit()
    conn.close()

    flash(f"បានបង្កើតកិច្ចការ «{title}» ក្នុងប្រតិទិនដោយជោគជ័យ!", "success")
    return redirect(url_for("calendar_index", month=event_date[:7]))


@app.route("/calendar/events/<int:event_id>")
@login_required
def calendar_event_detail(event_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.*, u.full_name as creator_name
        FROM commune_events e
        LEFT JOIN users u ON e.created_by = u.id
        WHERE e.id = ?
    """, (event_id,))
    ev = cursor.fetchone()
    conn.close()

    if not ev:
        return jsonify({"error": "Event not found"}), 404

    ev_dict = dict(ev)
    ev_type_info = EVENT_TYPES.get(ev_dict["event_type"], {})
    ev_dict["event_type_kh"] = ev_type_info.get("title_kh", ev_dict["event_type"])
    ev_dict["badge_class"] = ev_type_info.get("badge_class", "badge-info")
    ev_dict["icon"] = ev_type_info.get("icon", "fa-calendar")

    status_info = EVENT_STATUSES.get(ev_dict["status"], {})
    ev_dict["status_kh"] = status_info.get("title_kh", ev_dict["status"])
    ev_dict["status_badge"] = status_info.get("badge_class", "badge-info")

    return jsonify(ev_dict)


@app.route("/calendar/events/<int:event_id>/edit", methods=["POST"])
@clerk_or_admin_required
def calendar_event_edit(event_id):
    title = request.form.get("title", "").strip()
    event_type = request.form.get("event_type", "ordinary_meeting").strip()
    event_date = request.form.get("event_date", "").strip()
    start_time = request.form.get("start_time", "").strip()
    end_time = request.form.get("end_time", "").strip()
    location = request.form.get("location", "សាលាឃុំនគរភាស").strip()
    chairperson = request.form.get("chairperson", "").strip()
    participants = request.form.get("participants", "").strip()
    description = request.form.get("description", "").strip()
    status = request.form.get("status", "scheduled").strip()

    if not title or not event_date:
        flash("សូមបញ្ចូលចំណងជើង និងកាលបរិច្ឆេទនៃកិច្ចការ!", "danger")
        return redirect(url_for("calendar_index"))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE commune_events
        SET title = ?, event_type = ?, event_date = ?, start_time = ?, end_time = ?,
            location = ?, chairperson = ?, participants = ?, description = ?,
            status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (
        title, event_type, event_date, start_time, end_time, location,
        chairperson, participants, description, status, event_id
    ))
    conn.commit()
    conn.close()

    flash(f"បានកែប្រែព័ត៌មានកិច្ចការ «{title}» ដោយជោគជ័យ!", "success")
    return redirect(url_for("calendar_index", month=event_date[:7]))


@app.route("/calendar/events/<int:event_id>/delete", methods=["POST"])
@clerk_or_admin_required
def calendar_event_delete(event_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT title, event_date FROM commune_events WHERE id = ?", (event_id,))
    row = cursor.fetchone()
    title = row["title"] if row else "ព្រឹត្តិការណ៍"
    m_str = row["event_date"][:7] if row and row["event_date"] else ""

    cursor.execute("DELETE FROM commune_events WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()

    flash(f"បានលុបកិច្ចការ «{title}» ចេញពីប្រតិទិនដោយជោគជ័យ!", "info")
    return redirect(url_for("calendar_index", month=m_str))



# ==============================================================================
# FINANCE & CASH BOOK ROUTES (គ្រប់គ្រងហិរញ្ញវត្ថុ និងចំណូល-ចំណាយ)
# ==============================================================================

@app.route("/finance")
@login_required
def finance_list():
    conn = get_db()
    cursor = conn.cursor()

    current_year = date.today().year
    current_month_str = date.today().strftime("%Y-%m")

    # Range filter: from_month to to_month
    from_month = request.args.get("from_month", "").strip()
    to_month = request.args.get("to_month", "").strip()
    single_month = request.args.get("month", "").strip()

    if single_month and not from_month and not to_month:
        if single_month == "all":
            from_month = ""
            to_month = ""
        else:
            from_month = single_month
            to_month = single_month
    elif not from_month and not to_month and "from_month" not in request.args and "to_month" not in request.args:
        # Default: full current year from January to current month
        from_month = f"{current_year:04d}-01"
        to_month = current_month_str

    if from_month and to_month and from_month > to_month:
        from_month, to_month = to_month, from_month

    selected_type = request.args.get("type", "").strip()
    selected_category = request.args.get("category", "").strip()
    search_q = request.args.get("q", "").strip()

    page = request.args.get("page", 1, type=int)
    if not page or page < 1:
        page = 1
    per_page = 20

    # Base query for table
    query = "SELECT * FROM finance_transactions WHERE 1=1"
    params = []

    if from_month and to_month:
        query += " AND substr(transaction_date, 1, 7) >= ? AND substr(transaction_date, 1, 7) <= ?"
        params.extend([from_month, to_month])
    elif from_month:
        query += " AND substr(transaction_date, 1, 7) >= ?"
        params.append(from_month)
    elif to_month:
        query += " AND substr(transaction_date, 1, 7) <= ?"
        params.append(to_month)

    if selected_type in ["income", "expense"]:
        query += " AND type = ?"
        params.append(selected_type)
    if selected_category:
        query += " AND category = ?"
        params.append(selected_category)
    if search_q:
        query += " AND (title LIKE ? OR transaction_code LIKE ? OR payer_payee LIKE ? OR receipt_voucher_no LIKE ?)"
        term = f"%{search_q}%"
        params.extend([term, term, term, term])

    # Count total transactions matching filters
    count_query = query.replace("SELECT * FROM", "SELECT COUNT(*) as cnt FROM", 1)
    cursor.execute(count_query, tuple(params))
    cnt_row = cursor.fetchone()
    total_transactions = cnt_row["cnt"] if cnt_row else 0
    total_pages = max(1, (total_transactions + per_page - 1) // per_page)
    if page > total_pages:
        page = total_pages
    offset = (page - 1) * per_page

    query += " ORDER BY transaction_date DESC, id DESC LIMIT ? OFFSET ?"
    paginated_params = list(params) + [per_page, offset]
    cursor.execute(query, tuple(paginated_params))
    transactions = cursor.fetchall()

    # Calculate Period Totals (for filtered range)
    tot_query = """
        SELECT 
            COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as total_income,
            COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as total_expense,
            COUNT(*) as total_count
        FROM finance_transactions WHERE 1=1
    """
    tot_params = []
    if from_month and to_month:
        tot_query += " AND substr(transaction_date, 1, 7) >= ? AND substr(transaction_date, 1, 7) <= ?"
        tot_params.extend([from_month, to_month])
    elif from_month:
        tot_query += " AND substr(transaction_date, 1, 7) >= ?"
        tot_params.append(from_month)
    elif to_month:
        tot_query += " AND substr(transaction_date, 1, 7) <= ?"
        tot_params.append(to_month)

    cursor.execute(tot_query, tuple(tot_params))
    tot_row = cursor.fetchone()
    period_income = tot_row["total_income"] or 0
    period_expense = tot_row["total_expense"] or 0
    period_net = period_income - period_expense
    period_count = tot_row["total_count"] or 0

    # Calculate 6-month historical trend for Chart.js
    today = date.today()
    trend_labels = []
    trend_incomes = []
    trend_expenses = []
    for i in range(5, -1, -1):
        m_calc = today.month - i
        y_calc = today.year
        while m_calc <= 0:
            m_calc += 12
            y_calc -= 1
        m_str = f"{y_calc:04d}-{m_calc:02d}"
        kh_m_name = KHMER_MONTHS[m_calc]
        trend_labels.append(f"ខែ{kh_m_name}")

        cursor.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as inc,
                COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as exp
            FROM finance_transactions
            WHERE transaction_date LIKE ?
        """, (f"{m_str}%",))
        tr_row = cursor.fetchone()
        trend_incomes.append(tr_row["inc"] or 0)
        trend_expenses.append(tr_row["exp"] or 0)

    # Calculate Category Breakdowns for the selected period
    cat_inc_query = """
        SELECT category, SUM(amount) as cat_total
        FROM finance_transactions
        WHERE type = 'income'
    """
    cat_inc_params = []
    if from_month and to_month:
        cat_inc_query += " AND substr(transaction_date, 1, 7) >= ? AND substr(transaction_date, 1, 7) <= ?"
        cat_inc_params.extend([from_month, to_month])
    elif from_month:
        cat_inc_query += " AND substr(transaction_date, 1, 7) >= ?"
        cat_inc_params.append(from_month)
    elif to_month:
        cat_inc_query += " AND substr(transaction_date, 1, 7) <= ?"
        cat_inc_params.append(to_month)
    cat_inc_query += " GROUP BY category"
    cursor.execute(cat_inc_query, tuple(cat_inc_params))
    inc_cat_rows = cursor.fetchall()
    
    income_categories_breakdown = []
    for r in inc_cat_rows:
        c_info = FINANCE_INCOME_CATEGORIES.get(r["category"], {})
        income_categories_breakdown.append({
            "category": r["category"],
            "title_kh": c_info.get("title_kh", r["category"]),
            "color": c_info.get("color", "#0284c7"),
            "amount": r["cat_total"]
        })

    cat_exp_query = """
        SELECT category, SUM(amount) as cat_total
        FROM finance_transactions
        WHERE type = 'expense'
    """
    cat_exp_params = []
    if from_month and to_month:
        cat_exp_query += " AND substr(transaction_date, 1, 7) >= ? AND substr(transaction_date, 1, 7) <= ?"
        cat_exp_params.extend([from_month, to_month])
    elif from_month:
        cat_exp_query += " AND substr(transaction_date, 1, 7) >= ?"
        cat_exp_params.append(from_month)
    elif to_month:
        cat_exp_query += " AND substr(transaction_date, 1, 7) <= ?"
        cat_exp_params.append(to_month)
    cat_exp_query += " GROUP BY category"
    cursor.execute(cat_exp_query, tuple(cat_exp_params))
    exp_cat_rows = cursor.fetchall()
    
    expense_categories_breakdown = []
    for r in exp_cat_rows:
        c_info = FINANCE_EXPENSE_CATEGORIES.get(r["category"], {})
        expense_categories_breakdown.append({
            "category": r["category"],
            "title_kh": c_info.get("title_kh", r["category"]),
            "color": c_info.get("color", "#ea580c"),
            "amount": r["cat_total"]
        })

    conn.close()

    return render_template(
        "finance/index.html",
        transactions=transactions,
        from_month=from_month,
        to_month=to_month,
        selected_month=from_month,
        selected_type=selected_type,
        selected_category=selected_category,
        search_q=search_q,
        today_iso=today.strftime("%Y-%m-%d"),
        period_income=period_income,
        period_expense=period_expense,
        period_net=period_net,
        period_count=period_count,
        trend_labels=trend_labels,
        trend_incomes=trend_incomes,
        trend_expenses=trend_expenses,
        income_categories_breakdown=income_categories_breakdown,
        expense_categories_breakdown=expense_categories_breakdown,
        page=page,
        total_pages=total_pages,
        total_transactions=total_transactions,
        per_page=per_page,
        offset=offset,
        FINANCE_INCOME_CATEGORIES=FINANCE_INCOME_CATEGORIES,
        FINANCE_EXPENSE_CATEGORIES=FINANCE_EXPENSE_CATEGORIES,
        PAYMENT_METHODS=PAYMENT_METHODS,
        FINANCE_STATUSES=FINANCE_STATUSES
    )


@app.route("/finance/new", methods=["GET", "POST"])
@clerk_or_admin_required
def finance_create():
    if request.method == "POST":
        tx_type = request.form.get("type", "income").strip()
        category = request.form.get("category", "").strip()
        title = request.form.get("title", "").strip()
        amount_raw = request.form.get("amount", "0").strip().replace(",", "")
        transaction_date = request.form.get("transaction_date", "").strip()
        payer_payee = request.form.get("payer_payee", "").strip()
        receipt_voucher_no = request.form.get("receipt_voucher_no", "").strip()
        payment_method = request.form.get("payment_method", "cash").strip()
        notes = request.form.get("notes", "").strip()

        try:
            amount = float(amount_raw)
        except ValueError:
            amount = 0.0

        if not title or amount <= 0 or not transaction_date:
            flash("សូមបញ្ចូលព័ត៌មានប្រតិបត្តិការឱ្យបានត្រឹមត្រូវ (បរិយាយ ចំនួនទឹកប្រាក់ និងកាលបរិច្ឆេទ)!", "danger")
            return redirect(url_for("finance_list", month=transaction_date[:7] if transaction_date else None))

        # Handle attachment upload
        attachment_filename = None
        if "attachment" in request.files:
            file = request.files["attachment"]
            if file and file.filename != "":
                filename = secure_filename(file.filename)
                ts = datetime.now().strftime("%Y%m%d%H%M%S")
                safe_name = f"receipt_{ts}_{filename}"
                file_path = os.path.join(app.config["UPLOAD_FOLDER"], safe_name)
                file.save(file_path)
                attachment_filename = safe_name

        # Auto-generate unique transaction code
        conn = get_db()
        cursor = conn.cursor()
        
        d_clean = transaction_date.replace("-", "")[:6]
        prefix = "INC" if tx_type == "income" else "EXP"
        
        cursor.execute("SELECT transaction_code FROM finance_transactions WHERE transaction_code LIKE ?", (f"{prefix}-{d_clean}%",))
        existing_codes = set(row[0] for row in cursor.fetchall())
        seq = 1
        while f"{prefix}-{d_clean}-{seq:03d}" in existing_codes:
            seq += 1
        transaction_code = f"{prefix}-{d_clean}-{seq:03d}"

        cursor.execute("""
            INSERT INTO finance_transactions (
                transaction_code, type, category, title, amount, transaction_date,
                payer_payee, receipt_voucher_no, payment_method, attachment, notes,
                status, recorded_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?)
        """, (
            transaction_code, tx_type, category, title, amount, transaction_date,
            payer_payee, receipt_voucher_no, payment_method, attachment_filename, notes,
            session.get("user_id")
        ))
        conn.commit()
        conn.close()

        type_kh = "ចំណូល" if tx_type == "income" else "ចំណាយ"
        flash(f"បានកត់ត្រាប្រតិបត្តិការ{type_kh} «{title}» កូដ #{transaction_code} ដោយជោគជ័យ!", "success")
        return redirect(url_for("finance_list", month=transaction_date[:7]))

    preset_type = request.args.get("type", "income")
    today_iso = date.today().strftime("%Y-%m-%d")
    return render_template(
        "finance/form.html",
        is_edit=False,
        preset_type=preset_type,
        today_iso=today_iso,
        FINANCE_INCOME_CATEGORIES=FINANCE_INCOME_CATEGORIES,
        FINANCE_EXPENSE_CATEGORIES=FINANCE_EXPENSE_CATEGORIES,
        PAYMENT_METHODS=PAYMENT_METHODS
    )


@app.route("/finance/<int:tx_id>/edit", methods=["GET", "POST"])
@clerk_or_admin_required
def finance_edit(tx_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM finance_transactions WHERE id = ?", (tx_id,))
    tx = cursor.fetchone()

    if not tx:
        conn.close()
        flash("មិនមានប្រតិបត្តិការនេះក្នុងប្រព័ន្ធទេ!", "danger")
        return redirect(url_for("finance_list"))

    if request.method == "POST":
        tx_type = request.form.get("type", tx["type"]).strip()
        category = request.form.get("category", tx["category"]).strip()
        title = request.form.get("title", "").strip()
        amount_raw = request.form.get("amount", "0").strip().replace(",", "")
        transaction_date = request.form.get("transaction_date", "").strip()
        payer_payee = request.form.get("payer_payee", "").strip()
        receipt_voucher_no = request.form.get("receipt_voucher_no", "").strip()
        payment_method = request.form.get("payment_method", "cash").strip()
        notes = request.form.get("notes", "").strip()
        status = request.form.get("status", tx["status"]).strip()

        try:
            amount = float(amount_raw)
        except ValueError:
            amount = 0.0

        if not title or amount <= 0 or not transaction_date:
            flash("សូមបញ្ចូលព័ត៌មានប្រតិបត្តិការឱ្យបានត្រឹមត្រូវ!", "danger")
            conn.close()
            return redirect(url_for("finance_edit", tx_id=tx_id))

        attachment_filename = tx["attachment"]
        if "attachment" in request.files:
            file = request.files["attachment"]
            if file and file.filename != "":
                filename = secure_filename(file.filename)
                ts = datetime.now().strftime("%Y%m%d%H%M%S")
                safe_name = f"receipt_{ts}_{filename}"
                file_path = os.path.join(app.config["UPLOAD_FOLDER"], safe_name)
                file.save(file_path)
                attachment_filename = safe_name

        cursor.execute("""
            UPDATE finance_transactions
            SET type = ?, category = ?, title = ?, amount = ?, transaction_date = ?,
                payer_payee = ?, receipt_voucher_no = ?, payment_method = ?,
                attachment = ?, notes = ?, status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            tx_type, category, title, amount, transaction_date,
            payer_payee, receipt_voucher_no, payment_method,
            attachment_filename, notes, status, tx_id
        ))
        conn.commit()
        conn.close()

        flash(f"បានកែប្រែព័ត៌មានប្រតិបត្តិការ «{title}» ដោយជោគជ័យ!", "success")
        return redirect(url_for("finance_list", month=transaction_date[:7]))

    conn.close()
    return render_template(
        "finance/form.html",
        is_edit=True,
        tx=tx,
        FINANCE_INCOME_CATEGORIES=FINANCE_INCOME_CATEGORIES,
        FINANCE_EXPENSE_CATEGORIES=FINANCE_EXPENSE_CATEGORIES,
        PAYMENT_METHODS=PAYMENT_METHODS,
        FINANCE_STATUSES=FINANCE_STATUSES
    )


@app.route("/finance/<int:tx_id>/delete", methods=["POST"])
@clerk_or_admin_required
def finance_delete(tx_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT title, transaction_date, transaction_code FROM finance_transactions WHERE id = ?", (tx_id,))
    row = cursor.fetchone()
    title = row["title"] if row else "ប្រតិបត្តិការ"
    m_str = row["transaction_date"][:7] if row and row["transaction_date"] else ""

    cursor.execute("DELETE FROM finance_transactions WHERE id = ?", (tx_id,))
    conn.commit()
    conn.close()

    flash(f"បានលុបប្រតិបត្តិការ «{title}» (#{row['transaction_code'] if row else ''}) ចេញដោយជោគជ័យ!", "info")
    return redirect(url_for("finance_list", month=m_str))


@app.route("/finance/<int:tx_id>/receipt")
@login_required
def finance_receipt(tx_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.*, u.full_name as creator_name
        FROM finance_transactions t
        LEFT JOIN users u ON t.recorded_by = u.id
        WHERE t.id = ?
    """, (tx_id,))
    tx = cursor.fetchone()
    conn.close()

    if not tx:
        flash("មិនមានប្រតិបត្តិការនេះទេ!", "danger")
        return redirect(url_for("finance_list"))

    is_income = (tx["type"] == "income")
    if is_income:
        cat_info = FINANCE_INCOME_CATEGORIES.get(tx["category"], {})
    else:
        cat_info = FINANCE_EXPENSE_CATEGORIES.get(tx["category"], {})

    pay_method_info = PAYMENT_METHODS.get(tx["payment_method"], {})

    return render_template(
        "finance/receipt.html",
        tx=tx,
        is_income=is_income,
        category_title=cat_info.get("title_kh", tx["category"]),
        pay_method_title=pay_method_info.get("title_kh", tx["payment_method"] or "សាច់ប្រាក់សុទ្ធ")
    )


@app.route("/finance/export/excel")
@login_required
def export_finance_excel_route():
    from_month = request.args.get("from_month", "").strip()
    to_month = request.args.get("to_month", "").strip()
    month = request.args.get("month", "").strip()
    tx_type = request.args.get("type", "").strip()
    category = request.args.get("category", "").strip()

    if month and not from_month and not to_month:
        from_month = month
        to_month = month

    stream = export_finance_excel(from_month=from_month, to_month=to_month, tx_type=tx_type, category=category)
    
    if from_month and to_month:
        period_tag = from_month if from_month == to_month else f"{from_month}_to_{to_month}"
    elif from_month:
        period_tag = f"from_{from_month}"
    elif to_month:
        period_tag = f"to_{to_month}"
    else:
        period_tag = "All"
        
    filename = f"Nokor_Pheas_CashBook_{period_tag}.xlsx"

    return send_file(
        stream,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.route('/manifest.json')
def manifest():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'manifest.json', mimetype='application/manifest+json')


@app.route('/sw.js')
def service_worker():
    response = send_from_directory(os.path.join(app.root_path, 'static'), 'sw.js', mimetype='application/javascript')
    response.headers['Service-Worker-Allowed'] = '/'
    response.headers['Cache-Control'] = 'no-cache'
    return response


@app.route('/status')
def system_status():
    db_mode = "PostgreSQL (Neon)" if os.environ.get("DATABASE_URL") else "SQLite"
    status = {"status": "ok", "db_mode": db_mode, "time": datetime.now().isoformat()}
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        status["users_count"] = cur.fetchone()[0]
        conn.close()
        status["db_connection"] = "connected"
    except Exception as e:
        status["db_connection"] = f"error: {e}"
    return jsonify(status)


# ----------------------------------------------------
# STATE ASSET MANAGEMENT MODULE (គ្រប់គ្រងទ្រព្យសម្បត្តិរដ្ឋ)
# ----------------------------------------------------

@app.route("/assets")
@login_required
def assets_list():
    selected_category = request.args.get("category", "")
    selected_condition = request.args.get("condition", "")
    selected_custodian = request.args.get("custodian", "")
    search_query = request.args.get("q", "").strip()

    conn = get_db()
    cursor = conn.cursor()

    # Query all active staff for custodian filter
    cursor.execute("SELECT id, officer_code, name_kh, position_title_kh FROM staff WHERE status = 'active' ORDER BY officer_code ASC")
    staff_list = cursor.fetchall()

    # Base query for assets
    query = """
        SELECT a.*, s.name_kh as custodian_name, s.officer_code as custodian_code, s.position_title_kh as custodian_position, s.photo as custodian_photo
        FROM assets a
        LEFT JOIN staff s ON a.custodian_staff_id = s.id
        WHERE 1=1
    """
    params = []

    if selected_category:
        query += " AND a.category = ?"
        params.append(selected_category)

    if selected_condition:
        query += " AND a.condition_status = ?"
        params.append(selected_condition)

    if selected_custodian:
        query += " AND a.custodian_staff_id = ?"
        params.append(selected_custodian)

    if search_query:
        s_term = f"%{search_query}%"
        query += " AND (a.name_kh LIKE ? OR a.asset_code LIKE ? OR a.brand_model LIKE ? OR a.serial_number LIKE ? OR a.location LIKE ?)"
        params.extend([s_term, s_term, s_term, s_term, s_term])

    query += " ORDER BY a.id DESC"
    cursor.execute(query, params)
    asset_rows = cursor.fetchall()

    # Summary Statistics
    cursor.execute("SELECT COUNT(*), COALESCE(SUM(original_value), 0) FROM assets")
    stats_all = cursor.fetchone()
    total_count = stats_all[0] if stats_all else 0
    total_value = stats_all[1] if stats_all else 0

    cursor.execute("SELECT COUNT(*) FROM assets WHERE condition_status IN ('good', 'fair')")
    in_use_count = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM assets WHERE condition_status = 'needs_repair'")
    repair_count = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM assets WHERE condition_status = 'damaged'")
    damaged_count = cursor.fetchone()[0] or 0

    conn.close()

    return render_template(
        "assets/index.html",
        assets=asset_rows,
        staff_list=staff_list,
        selected_category=selected_category,
        selected_condition=selected_condition,
        selected_custodian=selected_custodian,
        search_query=search_query,
        stats={
            "total_count": total_count,
            "total_value": total_value,
            "in_use_count": in_use_count,
            "repair_count": repair_count,
            "damaged_count": damaged_count
        }
    )


@app.route("/assets/new", methods=["GET", "POST"])
@clerk_or_admin_required
def assets_new():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":
        name_kh = request.form.get("name_kh", "").strip()
        name_en = request.form.get("name_en", "").strip()
        category = request.form.get("category", "other")
        brand_model = request.form.get("brand_model", "").strip()
        serial_number = request.form.get("serial_number", "").strip()
        acquisition_date = request.form.get("acquisition_date", date.today().strftime("%Y-%m-%d"))
        acquisition_type = request.form.get("acquisition_type", "commune_fund")
        
        try:
            original_value = float(request.form.get("original_value", 0) or 0)
        except (ValueError, TypeError):
            original_value = 0

        condition_status = request.form.get("condition_status", "good")
        location = request.form.get("location", "សាលាឃុំនគរភាស").strip()
        custodian_id = request.form.get("custodian_staff_id") or None
        if custodian_id and custodian_id.isdigit():
            custodian_id = int(custodian_id)
        else:
            custodian_id = None

        notes = request.form.get("notes", "").strip()

        # Generate asset_code if not provided
        asset_code = request.form.get("asset_code", "").strip()
        if not asset_code:
            cursor.execute("SELECT COUNT(*) FROM assets")
            cnt = cursor.fetchone()[0] + 1
            yr = date.today().strftime("%Y")
            asset_code = f"NP-AST-{yr}-{cnt:03d}"

        # Handle Photo Upload
        photo_data_uri = None
        photo_file = request.files.get("photo")
        if photo_file and photo_file.filename != "":
            photo_data_uri, _ = process_and_save_photo(photo_file, officer_code=asset_code)

        # Handle Attachment
        attachment_name = None
        att_file = request.files.get("attachment")
        if att_file and att_file.filename != "":
            fname = secure_filename(f"att_ast_{asset_code}_{int(datetime.now().timestamp())}_{att_file.filename}")
            save_path = os.path.join(app.config["UPLOAD_FOLDER"], fname)
            att_file.save(save_path)
            attachment_name = fname

        try:
            cursor.execute("""
                INSERT INTO assets (
                    asset_code, name_kh, name_en, category, brand_model,
                    serial_number, acquisition_date, acquisition_type, original_value,
                    condition_status, location, custodian_staff_id, photo,
                    attachment, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (
                asset_code, name_kh, name_en, category, brand_model,
                serial_number, acquisition_date, acquisition_type, original_value,
                condition_status, location, custodian_id, photo_data_uri,
                attachment_name, notes
            ))

            cursor.execute("SELECT last_insert_rowid() AS id")
            row = cursor.fetchone()
            asset_id = row["id"] if isinstance(row, dict) or hasattr(row, '__getitem__') else row[0]

            # Initial Creation Log
            performed_by = session.get("full_name") or session.get("username") or "Admin"
            cursor.execute("""
                INSERT INTO asset_logs (
                    asset_id, action_type, action_date, performed_by,
                    to_staff_id, description, cost, created_at
                ) VALUES (?, 'created', ?, ?, ?, 'បានចុះបញ្ជីសារពើភណ្ឌទ្រព្យសម្បត្តិរដ្ឋថ្មី', 0, CURRENT_TIMESTAMP)
            """, (asset_id, acquisition_date, performed_by, custodian_id))

            conn.commit()
            conn.close()

            flash(f"បានចុះបញ្ជីទ្រព្យសម្បត្តិ «{name_kh}» ({asset_code}) ដោយជោគជ័យ!", "success")
            return redirect(url_for("assets_detail", asset_id=asset_id))
        except Exception as e:
            conn.rollback()
            conn.close()
            flash(f"មិនអាចចុះបញ្ជីទ្រព្យសម្បត្តិបានទេ៖ {e}", "danger")
            return redirect(url_for("assets_new"))

    # GET Request
    cursor.execute("SELECT id, officer_code, name_kh, position_title_kh FROM staff WHERE status = 'active' ORDER BY officer_code ASC")
    staff_list = cursor.fetchall()

    # Pre-generate next asset code
    cursor.execute("SELECT COUNT(*) FROM assets")
    cnt = cursor.fetchone()[0] + 1
    yr = date.today().strftime("%Y")
    next_code = f"NP-AST-{yr}-{cnt:03d}"

    conn.close()

    return render_template(
        "assets/form.html",
        is_edit=False,
        staff_list=staff_list,
        next_code=next_code,
        today_iso=date.today().strftime("%Y-%m-%d")
    )


@app.route("/assets/<int:asset_id>")
@login_required
def assets_detail(asset_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT a.*, s.name_kh as custodian_name, s.officer_code as custodian_code,
               s.position_title_kh as custodian_position, s.photo as custodian_photo,
               s.phone as custodian_phone
        FROM assets a
        LEFT JOIN staff s ON a.custodian_staff_id = s.id
        WHERE a.id = ?
    """, (asset_id,))
    asset = cursor.fetchone()

    if not asset:
        conn.close()
        flash("រកមិនឃើញព័ត៌មានទ្រព្យសម្បត្តិនេះទេ!", "danger")
        return redirect(url_for("assets_list"))

    # Fetch logs with staff joins
    cursor.execute("""
        SELECT l.*,
               sf.name_kh as from_staff_name, sf.position_title_kh as from_staff_pos,
               st.name_kh as to_staff_name, st.position_title_kh as to_staff_pos
        FROM asset_logs l
        LEFT JOIN staff sf ON l.from_staff_id = sf.id
        LEFT JOIN staff st ON l.to_staff_id = st.id
        WHERE l.asset_id = ?
        ORDER BY l.id DESC
    """, (asset_id,))
    logs = cursor.fetchall()

    # Fetch active staff for handover modal
    cursor.execute("SELECT id, officer_code, name_kh, position_title_kh FROM staff WHERE status = 'active' ORDER BY officer_code ASC")
    staff_list = cursor.fetchall()

    # Generate QR Code Data (pointing to asset info/code)
    qr_content = f"NOKOR_PHEAS_ASSET:{asset['asset_code']}|{asset['name_kh']}|{asset['condition_status']}"
    qr_code_base64 = generate_qr_base64(qr_content)

    conn.close()

    return render_template(
        "assets/detail.html",
        asset=asset,
        logs=logs,
        staff_list=staff_list,
        qr_code_base64=qr_code_base64
    )


@app.route("/assets/<int:asset_id>/edit", methods=["GET", "POST"])
@clerk_or_admin_required
def assets_edit(asset_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM assets WHERE id = ?", (asset_id,))
    asset = cursor.fetchone()

    if not asset:
        conn.close()
        flash("រកមិនឃើញព័ត៌មានទ្រព្យសម្បត្តិនេះទេ!", "danger")
        return redirect(url_for("assets_list"))

    if request.method == "POST":
        name_kh = request.form.get("name_kh", "").strip()
        name_en = request.form.get("name_en", "").strip()
        category = request.form.get("category", "other")
        brand_model = request.form.get("brand_model", "").strip()
        serial_number = request.form.get("serial_number", "").strip()
        acquisition_date = request.form.get("acquisition_date", asset["acquisition_date"])
        acquisition_type = request.form.get("acquisition_type", "commune_fund")
        
        try:
            original_value = float(request.form.get("original_value", 0) or 0)
        except (ValueError, TypeError):
            original_value = 0

        condition_status = request.form.get("condition_status", "good")
        location = request.form.get("location", "សាលាឃុំនគរភាស").strip()
        custodian_id = request.form.get("custodian_staff_id") or None
        if custodian_id and custodian_id.isdigit():
            custodian_id = int(custodian_id)
        else:
            custodian_id = None

        notes = request.form.get("notes", "").strip()

        # Handle Photo Upload
        photo_data_uri = asset["photo"]
        photo_file = request.files.get("photo")
        if photo_file and photo_file.filename != "":
            photo_data_uri, _ = process_and_save_photo(photo_file, officer_code=asset["asset_code"])

        # Handle Attachment
        attachment_name = asset["attachment"]
        att_file = request.files.get("attachment")
        if att_file and att_file.filename != "":
            fname = secure_filename(f"att_ast_{asset['asset_code']}_{int(datetime.now().timestamp())}_{att_file.filename}")
            save_path = os.path.join(app.config["UPLOAD_FOLDER"], fname)
            att_file.save(save_path)
            attachment_name = fname

        # Log condition change if any
        if condition_status != asset["condition_status"]:
            performed_by = session.get("full_name") or session.get("username") or "Admin"
            cond_label = ASSET_CONDITIONS.get(condition_status, {}).get("title_kh", condition_status)
            cursor.execute("""
                INSERT INTO asset_logs (
                    asset_id, action_type, action_date, performed_by,
                    description, cost, created_at
                ) VALUES (?, 'condition_update', ?, ?, ?, 0, CURRENT_TIMESTAMP)
            """, (asset_id, date.today().strftime("%Y-%m-%d"), performed_by, f"បានកែប្រែស្ថានភាពទ្រព្យទៅជា «{cond_label}»"))

        try:
            cursor.execute("""
                UPDATE assets SET
                    name_kh = ?, name_en = ?, category = ?, brand_model = ?,
                    serial_number = ?, acquisition_date = ?, acquisition_type = ?,
                    original_value = ?, condition_status = ?, location = ?,
                    custodian_staff_id = ?, photo = ?, attachment = ?, notes = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                name_kh, name_en, category, brand_model,
                serial_number, acquisition_date, acquisition_type,
                original_value, condition_status, location,
                custodian_id, photo_data_uri, attachment_name, notes,
                asset_id
            ))

            conn.commit()
            conn.close()

            flash(f"បានកែប្រែព័ត៌មានទ្រព្យសម្បត្តិ «{name_kh}» ដោយជោគជ័យ!", "success")
            return redirect(url_for("assets_detail", asset_id=asset_id))
        except Exception as e:
            conn.rollback()
            conn.close()
            flash(f"មិនអាចកែប្រែព័ត៌មានទ្រព្យសម្បត្តិបានទេ៖ {e}", "danger")
            return redirect(url_for("assets_edit", asset_id=asset_id))

    # GET Request
    cursor.execute("SELECT id, officer_code, name_kh, position_title_kh FROM staff WHERE status = 'active' ORDER BY officer_code ASC")
    staff_list = cursor.fetchall()
    conn.close()

    return render_template(
        "assets/form.html",
        is_edit=True,
        asset=asset,
        staff_list=staff_list
    )


@app.route("/assets/<int:asset_id>/delete", methods=["POST"])
@clerk_or_admin_required
def assets_delete(asset_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT name_kh, asset_code FROM assets WHERE id = ?", (asset_id,))
    asset = cursor.fetchone()

    if not asset:
        conn.close()
        flash("រកមិនឃើញព័ត៌មានទ្រព្យសម្បត្តិនេះទេ!", "danger")
        return redirect(url_for("assets_list"))

    cursor.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
    conn.commit()
    conn.close()

    flash(f"បានលុបទ្រព្យសម្បត្តិ «{asset['name_kh']}» ({asset['asset_code']}) ចេញពីបញ្ជីសារពើភណ្ឌដោយជោគជ័យ!", "success")
    return redirect(url_for("assets_list"))


@app.route("/assets/<int:asset_id>/handover", methods=["POST"])
@clerk_or_admin_required
def assets_handover(asset_id):
    new_custodian_id = request.form.get("to_staff_id") or None
    if new_custodian_id and new_custodian_id.isdigit():
        new_custodian_id = int(new_custodian_id)
    else:
        new_custodian_id = None

    new_location = request.form.get("location", "").strip()
    handover_date = request.form.get("action_date", date.today().strftime("%Y-%m-%d"))
    remarks = request.form.get("description", "").strip() or "បានផ្ទេរការកាន់កាប់ និងគ្រប់គ្រង"

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT custodian_staff_id, location, name_kh FROM assets WHERE id = ?", (asset_id,))
    asset = cursor.fetchone()

    if not asset:
        conn.close()
        flash("រកមិនឃើញព័ត៌មានទ្រព្យសម្បត្តិនេះទេ!", "danger")
        return redirect(url_for("assets_list"))

    old_custodian_id = asset["custodian_staff_id"]
    location_to_save = new_location if new_location else asset["location"]
    performed_by = session.get("full_name") or session.get("username") or "Admin"

    cursor.execute("""
        UPDATE assets SET
            custodian_staff_id = ?,
            location = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (new_custodian_id, location_to_save, asset_id))

    cursor.execute("""
        INSERT INTO asset_logs (
            asset_id, action_type, action_date, performed_by,
            from_staff_id, to_staff_id, description, cost, created_at
        ) VALUES (?, 'handover', ?, ?, ?, ?, ?, 0, CURRENT_TIMESTAMP)
    """, (asset_id, handover_date, performed_by, old_custodian_id, new_custodian_id, remarks))

    conn.commit()
    conn.close()

    flash("បានកត់ត្រាការផ្ទេរ និងប្រគល់-ទទួលសម្ភារៈដោយជោគជ័យ!", "success")
    return redirect(url_for("assets_detail", asset_id=asset_id))


@app.route("/assets/<int:asset_id>/maintenance", methods=["POST"])
@clerk_or_admin_required
def assets_maintenance(asset_id):
    action_date = request.form.get("action_date", date.today().strftime("%Y-%m-%d"))
    new_condition = request.form.get("condition_status", "good")
    description = request.form.get("description", "").strip()
    
    try:
        cost = float(request.form.get("cost", 0) or 0)
    except (ValueError, TypeError):
        cost = 0

    performed_by = session.get("full_name") or session.get("username") or "Admin"

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE assets SET
            condition_status = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (new_condition, asset_id))

    cursor.execute("""
        INSERT INTO asset_logs (
            asset_id, action_type, action_date, performed_by,
            description, cost, created_at
        ) VALUES (?, 'maintenance', ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (asset_id, action_date, performed_by, description or "ថែទាំ និងជួសជុលសម្ភារៈ", cost))

    conn.commit()
    conn.close()

    flash("បានកត់ត្រាការថែទាំ/ជួសជុលសម្ភារៈដោយជោគជ័យ!", "success")
    return redirect(url_for("assets_detail", asset_id=asset_id))


@app.route("/assets/<int:asset_id>/qr_tag")
@login_required
def assets_qr_tag(asset_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT a.*, s.name_kh as custodian_name, s.position_title_kh as custodian_position
        FROM assets a
        LEFT JOIN staff s ON a.custodian_staff_id = s.id
        WHERE a.id = ?
    """, (asset_id,))
    asset = cursor.fetchone()
    conn.close()

    if not asset:
        flash("រកមិនឃើញព័ត៌មានទ្រព្យសម្បត្តិនេះទេ!", "danger")
        return redirect(url_for("assets_list"))

    qr_content = f"NOKOR_PHEAS_ASSET:{asset['asset_code']}|{asset['name_kh']}|{asset['condition_status']}"
    qr_code_base64 = generate_qr_base64(qr_content)

    return render_template(
        "assets/qr_tag.html",
        asset=asset,
        qr_code_base64=qr_code_base64
    )


@app.route("/assets/export_excel")
@login_required
def export_assets_excel_route():
    category = request.args.get("category", "")
    condition = request.args.get("condition", "")
    search = request.args.get("q", "")

    stream = export_assets_excel(category=category, condition=condition, search=search)
    filename = f"បញ្ជីសារពើភណ្ឌទ្រព្យសម្បត្តិរដ្ឋ_ឃុំនគរភាស_{date.today().strftime('%Y%m%d')}.xlsx"

    return send_file(
        stream,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )


@app.route('/settings/clear-demo-data', methods=["POST"])
@login_required
def admin_clear_demo_data():
    if session.get("role") != "admin":
        flash("អ្នកមិនមានសិទ្ធិអនុវត្តសកម្មភាពនេះទេ!", "danger")
        return redirect(url_for("settings_profile"))
    
    conn = get_db()
    clear_all_demo_data(conn)
    flash("បានសម្អាតទិន្នន័យ Demo ទាំងអស់ដោយជោគជ័យ! ប្រព័ន្ធរួចរាល់សម្រាប់ការបញ្ចូលទិន្នន័យជាក់ស្តែង។", "success")
    return redirect(url_for("dashboard"))


@app.errorhandler(500)
def handle_internal_error(e):
    import traceback
    err = traceback.format_exc()
    return f"""
    <div style="font-family: system-ui, -apple-system, sans-serif; padding: 30px; max-width: 800px; margin: 40px auto; background: #fff1f2; border: 1px solid #fda4af; border-radius: 12px; color: #9f1239;">
        <h2 style="margin-top:0;">⚠️ ប្រព័ន្ធបានជួបប្រទះបញ្ហាបច្ចេកទេស (Internal Error)</h2>
        <p>ព័ត៌មានលម្អិតនៃបញ្ហា (Error Traceback)៖</p>
        <pre style="background: #ffffff; padding: 15px; border-radius: 8px; overflow-x: auto; font-size: 12.5px; color: #1e293b; border: 1px solid #e2e8f0;">{err}</pre>
        <a href="/login" style="display: inline-block; margin-top: 15px; padding: 8px 16px; background: #be123c; color: white; border-radius: 6px; text-decoration: none; font-weight: 500;">ត្រឡប់ទៅផ្ទាំង Login</a>
    </div>
    """, 500




# Runner entry point
if __name__ == "__main__":
    init_db()
    seed_data()
    app.run(host="0.0.0.0", port=5000, debug=True)

