import sqlite3
from datetime import datetime

DB_NAME = "focus_bot.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # Pozwala odwoływać się do kolumn po nazwie
    return conn

def init_db():
    """Tworzy tabele, jeśli nie istnieją."""
    conn = get_db_connection()
    c = conn.cursor()
    
    # Tabela Zadań
    c.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_done INTEGER DEFAULT 0,
            priority INTEGER DEFAULT 0
        )
    ''')

    # Migracja: dodaj kolumnę priority jeśli nie istnieje
    try:
        c.execute('ALTER TABLE tasks ADD COLUMN priority INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass  # Kolumna już istnieje

    # Migracja: dodaj kolumnę category jeśli nie istnieje
    try:
        c.execute('ALTER TABLE tasks ADD COLUMN category TEXT')
    except sqlite3.OperationalError:
        pass  # Kolumna już istnieje

    # Tabela Pomysłów
    c.execute('''
        CREATE TABLE IF NOT EXISTS ideas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            category TEXT
        )
    ''')

    # Migracja: dodaj kolumnę category do ideas jeśli nie istnieje
    try:
        c.execute('ALTER TABLE ideas ADD COLUMN category TEXT')
    except sqlite3.OperationalError:
        pass  # Kolumna już istnieje

    # Tabela Przypomnień
    c.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            remind_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_sent INTEGER DEFAULT 0
        )
    ''')

    conn.commit()
    conn.close()

def add_task(content, priority=0, category=None):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('INSERT INTO tasks (content, priority, category) VALUES (?, ?, ?)', (content, priority, category))
    conn.commit()
    conn.close()

def add_idea(content, category=None):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('INSERT INTO ideas (content, category) VALUES (?, ?)', (content, category))
    conn.commit()
    conn.close()

def get_active_tasks(category=None):
    conn = get_db_connection()
    # Sortowanie: pilne (priority=1) na górze, potem po dacie
    if category:
        tasks = conn.execute(
            'SELECT * FROM tasks WHERE is_done = 0 AND category = ? ORDER BY priority DESC, created_at DESC',
            (category,)
        ).fetchall()
    else:
        tasks = conn.execute('SELECT * FROM tasks WHERE is_done = 0 ORDER BY priority DESC, created_at DESC').fetchall()
    conn.close()
    return tasks

def get_ideas(category=None):
    conn = get_db_connection()
    if category:
        ideas = conn.execute('SELECT * FROM ideas WHERE category = ? ORDER BY created_at DESC', (category,)).fetchall()
    else:
        ideas = conn.execute('SELECT * FROM ideas ORDER BY created_at DESC').fetchall()
    conn.close()
    return ideas

def get_all_categories():
    """Pobiera wszystkie unikalne kategorie z zadań i pomysłów."""
    conn = get_db_connection()
    task_cats = conn.execute('SELECT DISTINCT category FROM tasks WHERE category IS NOT NULL').fetchall()
    idea_cats = conn.execute('SELECT DISTINCT category FROM ideas WHERE category IS NOT NULL').fetchall()
    conn.close()
    categories = set()
    for row in task_cats + idea_cats:
        if row['category']:
            categories.add(row['category'])
    return sorted(categories)

def mark_task_done(task_id):
    """Oznacza zadanie jako wykonane."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('UPDATE tasks SET is_done = 1 WHERE id = ?', (task_id,))
    rows_affected = c.rowcount
    conn.commit()
    conn.close()
    return rows_affected > 0

def delete_task(task_id):
    """Usuwa zadanie z bazy danych."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    rows_affected = c.rowcount
    conn.commit()
    conn.close()
    return rows_affected > 0

def delete_idea(idea_id):
    """Usuwa pomysł z bazy danych."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('DELETE FROM ideas WHERE id = ?', (idea_id,))
    rows_affected = c.rowcount
    conn.commit()
    conn.close()
    return rows_affected > 0

def update_task(task_id, new_content):
    """Aktualizuje treść zadania."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('UPDATE tasks SET content = ? WHERE id = ?', (new_content, task_id))
    rows_affected = c.rowcount
    conn.commit()
    conn.close()
    return rows_affected > 0

def update_idea(idea_id, new_content):
    """Aktualizuje treść pomysłu."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('UPDATE ideas SET content = ? WHERE id = ?', (new_content, idea_id))
    rows_affected = c.rowcount
    conn.commit()
    conn.close()
    return rows_affected > 0

def get_completed_tasks(limit=20):
    """Pobiera ukończone zadania (historia)."""
    conn = get_db_connection()
    tasks = conn.execute(
        'SELECT * FROM tasks WHERE is_done = 1 ORDER BY created_at DESC LIMIT ?',
        (limit,)
    ).fetchall()
    conn.close()
    return tasks

def get_task_by_id(task_id):
    """Pobiera pojedyncze zadanie po ID."""
    conn = get_db_connection()
    task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    conn.close()
    return task

def get_idea_by_id(idea_id):
    """Pobiera pojedynczy pomysł po ID."""
    conn = get_db_connection()
    idea = conn.execute('SELECT * FROM ideas WHERE id = ?', (idea_id,)).fetchone()
    conn.close()
    return idea

# --- Przypomnienia ---

def add_reminder(content: str, remind_at: datetime) -> int:
    """Dodaje przypomnienie i zwraca jego ID."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('INSERT INTO reminders (content, remind_at) VALUES (?, ?)', (content, remind_at))
    reminder_id = c.lastrowid
    conn.commit()
    conn.close()
    return reminder_id

def get_pending_reminders() -> list:
    """Pobiera przypomnienia do wysłania (czas minął, jeszcze nie wysłane)."""
    conn = get_db_connection()
    now = datetime.now()
    reminders = conn.execute(
        'SELECT * FROM reminders WHERE is_sent = 0 AND remind_at <= ? ORDER BY remind_at',
        (now,)
    ).fetchall()
    conn.close()
    return reminders

def mark_reminder_sent(reminder_id: int) -> bool:
    """Oznacza przypomnienie jako wysłane."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('UPDATE reminders SET is_sent = 1 WHERE id = ?', (reminder_id,))
    rows_affected = c.rowcount
    conn.commit()
    conn.close()
    return rows_affected > 0

def get_active_reminders() -> list:
    """Pobiera aktywne (niewysłane) przypomnienia."""
    conn = get_db_connection()
    reminders = conn.execute(
        'SELECT * FROM reminders WHERE is_sent = 0 ORDER BY remind_at'
    ).fetchall()
    conn.close()
    return reminders

def delete_reminder(reminder_id: int) -> bool:
    """Usuwa przypomnienie."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('DELETE FROM reminders WHERE id = ?', (reminder_id,))
    rows_affected = c.rowcount
    conn.commit()
    conn.close()
    return rows_affected > 0

# Inicjalizacja przy imporcie (bezpieczne, jeśli plik jest zaimportowany)
if __name__ == "__main__":
    init_db()
    print("Baza danych zainicjowana.")
