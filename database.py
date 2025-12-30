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
            is_done INTEGER DEFAULT 0
        )
    ''')
    
    # Tabela Pomysłów
    c.execute('''
        CREATE TABLE IF NOT EXISTS ideas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def add_task(content):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('INSERT INTO tasks (content) VALUES (?)', (content,))
    conn.commit()
    conn.close()

def add_idea(content):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('INSERT INTO ideas (content) VALUES (?)', (content,))
    conn.commit()
    conn.close()

def get_active_tasks():
    conn = get_db_connection()
    tasks = conn.execute('SELECT * FROM tasks WHERE is_done = 0 ORDER BY created_at DESC').fetchall()
    conn.close()
    return tasks

def get_ideas():
    conn = get_db_connection()
    ideas = conn.execute('SELECT * FROM ideas ORDER BY created_at DESC').fetchall()
    conn.close()
    return ideas

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

# Inicjalizacja przy imporcie (bezpieczne, jeśli plik jest zaimportowany)
if __name__ == "__main__":
    init_db()
    print("Baza danych zainicjowana.")
