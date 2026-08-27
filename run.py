"""
Server Launcher for Nokor Pheas Commune Staff Management System
(កម្មវិធីដំណើរការប្រព័ន្ធគ្រប់គ្រងបុគ្គលិករដ្ឋបាលឃុំនគរភាស)
"""

import sys
import os

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from database import init_db, seed_data
from app import app

if __name__ == "__main__":
    print("=" * 60)
    print(" [Nokor Pheas Commune Staff Management System]")
    print(" [ប្រព័ន្ធគ្រប់គ្រងបុគ្គលិក រដ្ឋបាលឃុំនគរភាស]")
    print("=" * 60)
    print(" Server running on: http://localhost:5000")
    print(" Admin account: admin / admin123")
    print(" Clerk account: clerk / clerk123")
    print(" Staff account: staff / staff123")
    print("=" * 60)
    
    init_db()
    seed_data()
    app.run(host="0.0.0.0", port=5000, debug=False)
