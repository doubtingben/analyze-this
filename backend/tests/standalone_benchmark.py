import sqlite3
import time
import uuid

def run_benchmark():
    # Setup
    conn = sqlite3.connect(':memory:')
    c = conn.cursor()
    c.execute('CREATE TABLE shared_items (id TEXT PRIMARY KEY, user_email TEXT, title TEXT)')
    c.execute('CREATE INDEX idx_user_email ON shared_items (user_email)')

    user_email = "test@example.com"
    num_items = 10000
    print(f"Seeding {num_items} items...")
    items = [(str(uuid.uuid4()), user_email, f"Item {i}") for i in range(num_items)]
    c.executemany('INSERT INTO shared_items VALUES (?, ?, ?)', items)
    conn.commit()

    requested_ids = [items[i][0] for i in range(10)]
    print(f"Benchmarking with {len(requested_ids)} requested items out of {num_items} total...")

    # Current logic simulation
    start = time.time()
    c.execute('SELECT id FROM shared_items WHERE user_email = ?', (user_email,))
    all_ids = {row[0] for row in c.fetchall()}
    authorized = [rid for rid in requested_ids if rid in all_ids]
    current_duration = time.time() - start
    print(f"Current logic (fetch all): {current_duration:.6f}s")

    # Optimized logic simulation
    start = time.time()
    placeholders = ','.join(['?'] * len(requested_ids))
    query = f'SELECT id FROM shared_items WHERE user_email = ? AND id IN ({placeholders})'
    c.execute(query, [user_email] + requested_ids)
    authorized = [row[0] for row in c.fetchall()]
    optimized_duration = time.time() - start
    print(f"Optimized logic (IN query): {optimized_duration:.6f}s")

    improvement = (current_duration - optimized_duration) / current_duration * 100
    print(f"Improvement: {improvement:.2f}%")

if __name__ == '__main__':
    run_benchmark()
