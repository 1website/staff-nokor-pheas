"""
Helper functions for Khmer formatting, dates, currency, and authentication
"""

import os
from functools import wraps
from datetime import datetime, date
from flask import session, redirect, url_for, flash, abort

KHMER_DIGITS = {
    '0': '០', '1': '១', '2': '២', '3': '៣', '4': '៤',
    '5': '៥', '6': '៦', '7': '៧', '8': '៨', '9': '៩'
}

KHMER_MONTHS = [
    "", "មករា", "កុម្ភៈ", "មីនា", "មេសា", "ឧសភា", "មិថុនា",
    "កក្កដា", "សីហា", "កញ្ញា", "តុលា", "វិច្ឆិកា", "ធ្នូ"
]

KHMER_DAYS = [
    "ថ្ងៃចន្ទ", "ថ្ងៃអង្គារ", "ថ្ងៃពុធ", "ថ្ងៃព្រហស្បតិ៍",
    "ថ្ងៃសុក្រ", "ថ្ងៃសៅរ៍", "ថ្ងៃអាទិត្យ"
]

def to_khmer_num(number_or_str):
    """Convert Arabic numbers to Khmer numerals safely"""
    if number_or_str is None:
        return ""
    if callable(number_or_str):
        try:
            val = number_or_str()
            return to_khmer_num(val)
        except Exception:
            return "០"
    s = str(number_or_str)
    # Guard against accidental stringification of built-in method or object representations
    if s.startswith("<built-in") or s.startswith("<function") or s.startswith("<method"):
        return "០"
    return "".join(KHMER_DIGITS.get(ch, ch) for ch in s)

def format_khmer_date(date_val, include_day_name=True):
    """Format date to Khmer string: ថ្ងៃអាទិត្យ ទី២៣ ខែសីហា ឆ្នាំ២០២៦"""
    if not date_val:
        return ""
    if isinstance(date_val, str):
        try:
            date_val = datetime.strptime(date_val[:10], "%Y-%m-%d").date()
        except Exception:
            return date_val

    day_name = KHMER_DAYS[date_val.weekday()] if include_day_name else ""
    day_num = to_khmer_num(date_val.day)
    month_name = KHMER_MONTHS[date_val.month]
    year_num = to_khmer_num(date_val.year)

    if include_day_name:
        return f"{day_name} ទី{day_num} ខែ{month_name} ឆ្នាំ{year_num}"
    return f"ថ្ងៃទី{day_num} ខែ{month_name} ឆ្នាំ{year_num}"

def calculate_age(dob_val):
    """Calculate age in years from date of birth (YYYY-MM-DD or date/datetime object)"""
    if not dob_val:
        return None
    try:
        if isinstance(dob_val, str):
            dob_date = datetime.strptime(str(dob_val).strip()[:10], "%Y-%m-%d").date()
        elif isinstance(dob_val, datetime):
            dob_date = dob_val.date()
        elif isinstance(dob_val, date):
            dob_date = dob_val
        else:
            return None

        today = date.today()
        age = today.year - dob_date.year - ((today.month, today.day) < (dob_date.month, dob_date.day))
        return max(0, age)
    except Exception:
        return None

def format_khmer_age(dob_val, suffix=True):
    """Format age in Khmer numerals: e.g. '៤១ ឆ្នាំ' or '៤១'"""
    age = calculate_age(dob_val)
    if age is None:
        return "-"
    kh_num = to_khmer_num(age)
    return f"{kh_num} ឆ្នាំ" if suffix else kh_num

def format_currency(amount, currency="រៀល"):
    """Format numeric currency with commas and currency symbol"""
    if amount is None:
        return "0 " + currency
    try:
        val = int(round(float(amount)))
        formatted = f"{val:,}"
        return f"{formatted} {currency}"
    except Exception:
        return f"{amount} {currency}"

# Category translations and badges
STAFF_CATEGORIES = {
    'council': {
        'name_kh': 'ក្រុមប្រឹក្សាឃុំ',
        'name_en': 'Commune Council',
        'badge_class': 'badge-council',
        'color': '#0284c7'
    },
    'clerk': {
        'name_kh': 'ស្មៀនឃុំ',
        'name_en': 'Commune Clerk',
        'badge_class': 'badge-clerk',
        'color': '#0d9488'
    },
    'contract': {
        'name_kh': 'ជំនួយការឃុំ',
        'name_en': 'Commune Assistants',
        'badge_class': 'badge-contract',
        'color': '#8b5cf6'
    },
    'village': {
        'name_kh': 'មន្ត្រីភូមិ',
        'name_en': 'Village Officials',
        'badge_class': 'badge-village',
        'color': '#ea580c'
    }
}

ATTENDANCE_STATUSES = {
    'present': {'label_kh': 'វត្តមាន', 'label_en': 'Present', 'badge': 'badge-success'},
    'late': {'label_kh': 'មកយឺត', 'label_en': 'Late', 'badge': 'badge-warning'},
    'early_leave': {'label_kh': 'ចេញមុន', 'label_en': 'Early Leave', 'badge': 'badge-warning'},
    'absent': {'label_kh': 'អវត្តមាន', 'label_en': 'Absent', 'badge': 'badge-danger'},
    'on_leave': {'label_kh': 'ច្បាប់', 'label_en': 'On Leave', 'badge': 'badge-info'},
    'mission': {'label_kh': 'បេសកកម្ម', 'label_en': 'Mission', 'badge': 'badge-purple'}
}

LEAVE_TYPES = {
    'annual': 'ច្បាប់ប្រចាំឆ្នាំ (Annual Leave)',
    'sick': 'ច្បាប់ឈឺ (Sick Leave)',
    'personal': 'ធុរៈផ្ទាល់ខ្លួន (Personal Leave)',
    'maternity': 'ច្បាប់លំហែមាតុភាព (Maternity Leave)',
    'special': 'ច្បាប់ពិសេស (Special Leave)'
}

DOCUMENT_TYPES = {
    'appointment_deka': 'ដីកា/ប្រកាសតែងតាំង',
    'contract': 'កិច្ចសន្យាការងារ',
    'degree_certificate': 'សញ្ញាបត្រ/វិញ្ញាបនបត្រ',
    'cv': 'ប្រវត្តិរូបសង្ខេប (CV)',
    'other': 'ឯកសារផ្សេងៗ'
}

HONOR_TYPES = {
    'letter_of_praise': 'លិខិតសរសើរ',
    'certificate_of_appreciation': 'ប័ណ្ណសរសើរ',
    'work_medal': 'មេដាយការងារ',
    'royal_order': 'គ្រឿងឥស្សរិយយស'
}

# Finance & Cash Book Constants (ចំណូល-ចំណាយ និងសៀវភៅសាច់ប្រាក់)
FINANCE_INCOME_CATEGORIES = {
    'commune_fund': {
        'title_kh': 'ថវិកាមូលនិធិឃុំពីរដ្ឋ',
        'title_en': 'Commune Fund / State Subsidy',
        'badge_class': 'badge-success',
        'icon': 'fa-solid fa-landmark-dome',
        'color': '#059669'
    },
    'imprest_fund': {
        'title_kh': 'រជ្ជទេយ្យបុរេប្រទាន',
        'title_en': 'Imprest Fund / Advance',
        'badge_class': 'badge-income-imprest',
        'icon': 'fa-solid fa-hand-holding-dollar',
        'color': '#0891b2'
    },
    'other_income': {
        'title_kh': 'ចំណូលផ្សេងៗ',
        'title_en': 'Other Income',
        'badge_class': 'badge-secondary',
        'icon': 'fa-solid fa-circle-dollar-to-slot',
        'color': '#64748b'
    }
}

FINANCE_EXPENSE_CATEGORIES = {
    'administrative': {
        'title_kh': 'ចំណាយរដ្ឋបាល & សម្ភារៈការិយាល័យ',
        'title_en': 'Administrative & Office Supplies',
        'badge_class': 'badge-info',
        'icon': 'fa-solid fa-boxes-packing',
        'color': '#0284c7'
    },
    'social_service': {
        'title_kh': 'ចំណាយសេវាសង្គម',
        'title_en': 'Social Services & Welfare',
        'badge_class': 'badge-success',
        'icon': 'fa-solid fa-hand-holding-heart',
        'color': '#059669'
    },
    'utility': {
        'title_kh': 'ថ្លៃអគ្គិសនី ទឹក & អ៊ីនធឺណិត',
        'title_en': 'Utilities (Electricity/Water/Net)',
        'badge_class': 'badge-warning',
        'icon': 'fa-solid fa-bolt',
        'color': '#ea580c'
    },
    'maintenance': {
        'title_kh': 'ជួសជុល & ថែទាំអគារ/បរិក្ខារ',
        'title_en': 'Repairs & Maintenance',
        'badge_class': 'badge-warning',
        'icon': 'fa-solid fa-screwdriver-wrench',
        'color': '#d97706'
    },
    'reception_event': {
        'title_kh': 'បដិសណ្ឋារកិច្ច & កិច្ចប្រជុំ/ពិធី',
        'title_en': 'Hospitality & Events/Meetings',
        'badge_class': 'badge-pink',
        'icon': 'fa-solid fa-champagne-glasses',
        'color': '#ec4899'
    },
    'mission_travel': {
        'title_kh': 'ចំណាយបេសកកម្ម & ធ្វើដំណើរ',
        'title_en': 'Missions & Travel',
        'badge_class': 'badge-purple',
        'icon': 'fa-solid fa-map-location-dot',
        'color': '#7c3aed'
    },
    'other_expense': {
        'title_kh': 'ចំណាយប្រតិបត្តិការផ្សេងៗ',
        'title_en': 'Other Expenses',
        'badge_class': 'badge-secondary',
        'icon': 'fa-solid fa-money-bill-transfer',
        'color': '#64748b'
    }
}

PAYMENT_METHODS = {
    'cash': {'title_kh': 'សាច់ប្រាក់សុទ្ធ', 'title_en': 'Cash', 'icon': 'fa-solid fa-money-bill-1-wave', 'badge': 'badge-cash'},
    'aba': {'title_kh': 'ABA Bank', 'title_en': 'ABA Bank', 'icon': 'fa-solid fa-building-columns', 'badge': 'badge-aba'},
    'wing': {'title_kh': 'វីង (Wing Bank)', 'title_en': 'Wing Bank', 'icon': 'fa-solid fa-mobile-screen-button', 'badge': 'badge-wing'},
    'acleda': {'title_kh': 'អេស៊ីលីដា (ACLEDA)', 'title_en': 'ACLEDA Bank', 'icon': 'fa-solid fa-landmark', 'badge': 'badge-acleda'},
    'canadia': {'title_kh': 'កាណាឌីយ៉ា (Canadia)', 'title_en': 'Canadia Bank', 'icon': 'fa-solid fa-building-columns', 'badge': 'badge-canadia'},
    'bank_transfer': {'title_kh': 'ផ្ទេរប្រាក់ធនាគារ/រតនាគារ', 'title_en': 'Bank / Treasury Transfer', 'icon': 'fa-solid fa-arrow-right-arrow-left', 'badge': 'badge-bank'}
}

FINANCE_STATUSES = {
    'completed': {'title_kh': 'បានទូទាត់រួចរាល់', 'badge': 'badge-success'},
    'pending': {'title_kh': 'រង់ចាំទូទាត់', 'badge': 'badge-warning'},
    'cancelled': {'title_kh': 'បានលុបចោល', 'badge': 'badge-danger'}
}

# State Asset Management Constants
ASSET_CATEGORIES = {
    'building': {
        'title_kh': 'អគារ និងសំណង់រដ្ឋបាល',
        'title_en': 'Administrative Buildings',
        'icon': 'fa-solid fa-building-flag',
        'badge_class': 'badge-primary',
        'color': '#2563eb'
    },
    'land': {
        'title_kh': 'ដីធ្លី និងបរិវេណ',
        'title_en': 'Land & Compounds',
        'icon': 'fa-solid fa-map-location-dot',
        'badge_class': 'badge-success',
        'color': '#059669'
    },
    'vehicle': {
        'title_kh': 'មធ្យោបាយធ្វើដំណើរ',
        'title_en': 'Vehicles & Transport',
        'icon': 'fa-solid fa-car-side',
        'badge_class': 'badge-info',
        'color': '#0284c7'
    },
    'it_equipment': {
        'title_kh': 'កុំព្យូទ័រ & អេឡិចត្រូនិក',
        'title_en': 'IT & Electronics',
        'icon': 'fa-solid fa-laptop',
        'badge_class': 'badge-purple',
        'color': '#7c3aed'
    },
    'office_furniture': {
        'title_kh': 'គ្រឿងសង្ហារិម & បរិក្ខារការិយាល័យ',
        'title_en': 'Office Furniture',
        'icon': 'fa-solid fa-couch',
        'badge_class': 'badge-warning',
        'color': '#d97706'
    },
    'infrastructure': {
        'title_kh': 'ហេដ្ឋារចនាសម្ព័ន្ធសាធារណៈ',
        'title_en': 'Public Infrastructure',
        'icon': 'fa-solid fa-bridge-water',
        'badge_class': 'badge-clerk',
        'color': '#0d9488'
    },
    'machinery': {
        'title_kh': 'គ្រឿងចក្រ & ឧបករណ៍បច្ចេកទេស',
        'title_en': 'Machinery & Tools',
        'icon': 'fa-solid fa-gears',
        'badge_class': 'badge-dark',
        'color': '#475569'
    },
    'other': {
        'title_kh': 'សម្ភារៈផ្សេងៗ',
        'title_en': 'Other Assets',
        'icon': 'fa-solid fa-box-open',
        'badge_class': 'badge-secondary',
        'color': '#64748b'
    }
}

ASSET_CONDITIONS = {
    'good': {
        'title_kh': 'ល្អ / កំពុងប្រើប្រាស់',
        'title_en': 'In Use / Good',
        'badge_class': 'badge-success',
        'icon': 'fa-solid fa-circle-check',
        'color': '#059669'
    },
    'fair': {
        'title_kh': 'មធ្យម / នៅប្រើកើត',
        'title_en': 'Fair Condition',
        'badge_class': 'badge-info',
        'icon': 'fa-solid fa-circle-info',
        'color': '#0284c7'
    },
    'needs_repair': {
        'title_kh': 'ត្រូវការជួសជុល',
        'title_en': 'Needs Repair',
        'badge_class': 'badge-warning',
        'icon': 'fa-solid fa-triangle-exclamation',
        'color': '#d97706'
    },
    'damaged': {
        'title_kh': 'ខូចលែងប្រើកើត',
        'title_en': 'Damaged / Broken',
        'badge_class': 'badge-danger',
        'icon': 'fa-solid fa-circle-xmark',
        'color': '#dc2626'
    },
    'disposed': {
        'title_kh': 'បានរំលាយចោល',
        'title_en': 'Disposed / Written-off',
        'badge_class': 'badge-secondary',
        'icon': 'fa-solid fa-ban',
        'color': '#64748b'
    }
}

ASSET_ACQUISITIONS = {
    'commune_fund': {'title_kh': 'ថវិកាឃុំផ្ទាល់', 'title_en': 'Commune Fund'},
    'national_grant': {'title_kh': 'ថ្នាក់ជាតិផ្តល់ជូន', 'title_en': 'National Grant'},
    'donation': {'title_kh': 'ជំនួយសប្បុរសជន / អង្គការ', 'title_en': 'Donation / NGO'},
    'other': {'title_kh': 'ផ្សេងៗ', 'title_en': 'Other'}
}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("សូមចូលប្រើប្រាស់ប្រព័ន្ធជាមុនសិន!", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("សូមចូលប្រើប្រាស់ប្រព័ន្ធជាមុនសិន!", "warning")
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash("លោកអ្នកមិនមានសិទ្ធិគ្រប់គ្រងផ្នែកនេះទេ (សម្រាប់តែ Admin / មេឃុំ)!", "danger")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def clerk_or_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("សូមចូលប្រើប្រាស់ប្រព័ន្ធជាមុនសិន!", "warning")
            return redirect(url_for('login'))
        if session.get('role') not in ['admin', 'clerk']:
            flash("លោកអ្នកមិនមានសិទ្ធិអនុវត្តមុខងារនេះទេ (សម្រាប់តែស្មៀន ឬ Admin)!", "danger")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def generate_qr_base64(data_str):
    """Generate base64 encoded PNG data URI for QR code"""
    import qrcode
    import io
    import base64
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=1,
    )
    qr.add_data(data_str)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0b192c", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffered.getvalue()).decode("utf-8")


def staff_photo_url(photo):
    """
    Format staff photo URL supporting:
    - Base64 Data URLs (data:image/...)
    - Full URLs (http:// or https://)
    - Relative paths (/static/...)
    - Uploaded filenames (photo_NP_001_....jpg -> /static/uploads/photo_NP_001_....jpg)
    """
    if not photo:
        return ""
    photo = str(photo).strip()
    if not photo:
        return ""
    if photo.startswith("data:") or photo.startswith("http://") or photo.startswith("https://") or photo.startswith("/static/"):
        return photo
    if photo.startswith("uploads/"):
        return f"/static/{photo}"
    return f"/static/uploads/{photo}"


def process_and_save_photo(file_or_bytes, officer_code="NP", upload_folder=None, max_size=(800, 1000), quality=82):
    """
    Process, optimize, and encode staff photo.
    Returns (data_uri, saved_filename).
    - Auto-rotates using EXIF orientation tags (fixes mobile phone uploads)
    - Resizes to fit within max_size preserving aspect ratio
    - Compresses to high-quality JPEG
    - Generates self-contained Base64 Data URL (data:image/jpeg;base64,...)
    - Optionally writes to disk if upload_folder is accessible
    """
    import io
    import base64
    from PIL import Image, ImageOps
    from werkzeug.utils import secure_filename

    raw_bytes = None
    if hasattr(file_or_bytes, "read"):
        raw_bytes = file_or_bytes.read()
    elif isinstance(file_or_bytes, bytes):
        raw_bytes = file_or_bytes
    elif isinstance(file_or_bytes, str):
        if file_or_bytes.startswith("data:image"):
            # Already a data URL
            header, encoded = file_or_bytes.split(",", 1)
            raw_bytes = base64.b64decode(encoded)
        elif os.path.exists(file_or_bytes):
            try:
                with open(file_or_bytes, "rb") as f:
                    raw_bytes = f.read()
            except Exception:
                pass

    if not raw_bytes:
        return None, None

    try:
        img = Image.open(io.BytesIO(raw_bytes))
        # Handle EXIF rotation (mobile portrait/landscape)
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass

        # Convert to RGB (dropping alpha or palette)
        if img.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            bg.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # Resize smoothly
        img.thumbnail(max_size, Image.Resampling.LANCZOS)

        # Encode to JPEG
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        compressed_bytes = buf.getvalue()

        b64_str = base64.b64encode(compressed_bytes).decode("utf-8")
        data_uri = f"data:image/jpeg;base64,{b64_str}"

        # Generate standard filename
        safe_code = secure_filename(str(officer_code)).replace('-', '_')
        filename = f"photo_{safe_code}_{int(datetime.now().timestamp())}.jpg"

        # Save to disk if upload_folder is provided
        if upload_folder:
            try:
                os.makedirs(upload_folder, exist_ok=True)
                file_path = os.path.join(upload_folder, filename)
                with open(file_path, "wb") as f:
                    f.write(compressed_bytes)
            except Exception:
                pass

        return data_uri, filename
    except Exception as e:
        print(f"[Photo Processing Warning] {e}")
        return None, None

