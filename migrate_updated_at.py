import sqlite3

DB_PATH = "app.db"

def add_column_if_not_exists(cur, table, column_def):
    """
    يضيف عمود لو مش موجود بالفعل.
    table: اسم الجدول
    column_def: تعريف العمود مثل "updated_at DATETIME"
    """
    col_name = column_def.split()[0]
    cur.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cur.fetchall()]
    if col_name not in cols:
        print(f"➕ Adding column {col_name} to {table}")
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column_def}")
    else:
        print(f"✅ Column {col_name} already exists in {table}")


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Albums
    add_column_if_not_exists(cur, "albums", "updated_at DATETIME")
    cur.execute("UPDATE albums SET updated_at = created_at WHERE updated_at IS NULL")

    # Share links
    add_column_if_not_exists(cur, "share_links", "updated_at DATETIME")
    cur.execute("UPDATE share_links SET updated_at = created_at WHERE updated_at IS NULL")

    # Likes
    add_column_if_not_exists(cur, "likes", "updated_at DATETIME")
    cur.execute("UPDATE likes SET updated_at = created_at WHERE updated_at IS NULL")

    conn.commit()
    conn.close()
    print("✅ Migration finished successfully.")


if __name__ == "__main__":
    main()
