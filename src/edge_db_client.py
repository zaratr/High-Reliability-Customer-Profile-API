import sqlite3

def init_edge_db():
    print("Connecting to local edge replica (libSQL/Turso)...")
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE profiles (id INT, name TEXT)")
    conn.execute("INSERT INTO profiles VALUES (1, 'Edge User')")
    row = conn.execute("SELECT * FROM profiles").fetchone()
    print(f"Edge DB Query Result: {row}")

if __name__ == '__main__':
    init_edge_db()
