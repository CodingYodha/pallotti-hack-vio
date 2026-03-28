import sqlite3
import os

DB_PATH = "./violation_tracking.db"

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Tracked Individuals
    cursor.execute("PRAGMA table_info(tracked_individuals)")
    individual_cols = [col[1] for col in cursor.fetchall()]
    
    migrations_run = 0
    if 'is_fined' not in individual_cols:
        cursor.execute("ALTER TABLE tracked_individuals ADD COLUMN is_fined INTEGER DEFAULT 0")
        migrations_run += 1
    if 'fine_amount' not in individual_cols:
        cursor.execute("ALTER TABLE tracked_individuals ADD COLUMN fine_amount REAL DEFAULT 100.0")
        migrations_run += 1
        
    # Employees
    cursor.execute("PRAGMA table_info(employees)")
    employee_cols = [col[1] for col in cursor.fetchall()]

    if 'email' not in employee_cols:
        cursor.execute("ALTER TABLE employees ADD COLUMN email TEXT")
        migrations_run += 1
    if 'phone' not in employee_cols:
        cursor.execute("ALTER TABLE employees ADD COLUMN phone TEXT")
        migrations_run += 1
    if 'department' not in employee_cols:
        cursor.execute("ALTER TABLE employees ADD COLUMN department TEXT")
        migrations_run += 1
    if 'role' not in employee_cols:
        cursor.execute("ALTER TABLE employees ADD COLUMN role TEXT")
        migrations_run += 1

    conn.commit()
    conn.close()
    
    print(f"✅ Migration complete! Added {migrations_run} new column(s).")

if __name__ == "__main__":
    migrate()
