import sqlite3
import os
from datetime import datetime

DB_PATH = "violation_tracking.db"
TARGET_DATE = "2026-03-28"

def delete_old_records():
    if not os.path.exists(DB_PATH):
        print(f"Database {DB_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Get old videos
    cursor.execute("SELECT id, file_path, annotated_video_path FROM videos WHERE uploaded_at < ?", (TARGET_DATE,))
    old_videos = cursor.fetchall()
    print(f"Found {len(old_videos)} old videos.")
    
    for vid, file_path, annotated_path in old_videos:
        if file_path and os.path.exists(file_path):
            try: os.remove(file_path)
            except: pass
        if annotated_path and os.path.exists(annotated_path):
            try: os.remove(annotated_path)
            except: pass

    # 2. Get old violations
    cursor.execute("SELECT id, image_path, snippet_path FROM violations WHERE detected_at < ?", (TARGET_DATE,))
    old_violations = cursor.fetchall()
    print(f"Found {len(old_violations)} old violations.")

    for vid, img_path, snip_path in old_violations:
        if img_path:
            # handle both absolute and relative paths
            if img_path.startswith("/"):
                path = "." + img_path
            else:
                path = img_path
            if os.path.exists(path):
                try: os.remove(path)
                except: pass
        if snip_path:
            if snip_path.startswith("/"):
                path = "." + snip_path
            else:
                path = snip_path
            if os.path.exists(path):
                try: os.remove(path)
                except: pass

    # Delete records from DB. Due to ON DELETE CASCADE, deleting videos or tracked_individuals might cascade,
    # but let's be explicit just in case.
    
    # 3. Delete violations
    cursor.execute("DELETE FROM violations WHERE detected_at < ?", (TARGET_DATE,))
    
    # 4. Delete videos
    cursor.execute("DELETE FROM videos WHERE uploaded_at < ?", (TARGET_DATE,))
    
    # 5. Get tracked individuals without videos (webcam) created before target date
    # Let's check table schema for tracked_individuals first
    cursor.execute("PRAGMA table_info(tracked_individuals)")
    columns = [row[1] for row in cursor.fetchall()]
    if "first_seen_at" in columns:
        cursor.execute("DELETE FROM tracked_individuals WHERE first_seen_at < ?", (TARGET_DATE,))
    elif "created_at" in columns:
        cursor.execute("DELETE FROM tracked_individuals WHERE created_at < ?", (TARGET_DATE,))
    
    # Delete left-over webcam images from violation_images folder
    # They usually start with 'webcam_' or 'p{id}_'
    img_dir = "violation_images"
    if os.path.exists(img_dir):
        deleted_imgs = 0
        for fname in os.listdir(img_dir):
            fpath = os.path.join(img_dir, fname)
            if os.path.isfile(fpath):
                mtime = os.path.getmtime(fpath)
                if datetime.fromtimestamp(mtime).strftime('%Y-%m-%d') < TARGET_DATE:
                    try: 
                        os.remove(fpath)
                        deleted_imgs += 1
                    except: pass
        print(f"Deleted {deleted_imgs} old loose images from {img_dir}.")
        
    conn.commit()
    conn.close()
    print("Cleanup complete.")

if __name__ == "__main__":
    delete_old_records()
