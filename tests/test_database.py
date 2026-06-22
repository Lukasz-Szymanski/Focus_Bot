import os
import tempfile
import datetime
import pytest
from datetime import timedelta

# Konfiguracja tymczasowej bazy przed importem database
db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
db_path = db_file.name
db_file.close()

os.environ["DATABASE_PATH"] = db_path

import database as db

@pytest.fixture(autouse=True)
def setup_teardown():
    # Przygotowanie czystej bazy danych przed każdym testem
    db.init_db()
    # Czyszczenie tabel
    with db.db.connection_context():
        db.Task.delete().execute()
        db.Idea.delete().execute()
        db.Reminder.delete().execute()
        db.RecurringReminder.delete().execute()
    yield

def test_add_and_get_tasks():
    db.add_task("Zadanie 1", priority=0, category="dom")
    db.add_task("Zadanie 2", priority=1, category="praca")

    active = db.get_active_tasks()
    assert len(active) == 2
    # Zadanie z priorytetem 1 powinno być pierwsze
    assert active[0]['content'] == "Zadanie 2"
    assert active[0]['priority'] == 1
    assert active[0]['category'] == "praca"

    assert active[1]['content'] == "Zadanie 1"
    assert active[1]['priority'] == 0
    assert active[1]['category'] == "dom"

def test_get_active_tasks_filtering():
    db.add_task("Zadanie 1", category="dom")
    db.add_task("Zadanie 2", category="praca")

    dom_tasks = db.get_active_tasks("dom")
    assert len(dom_tasks) == 1
    assert dom_tasks[0]['content'] == "Zadanie 1"

def test_add_and_get_ideas():
    db.add_idea("Pomysł 1", category="projekty")
    db.add_idea("Pomysł 2")

    ideas = db.get_ideas()
    assert len(ideas) == 2
    assert ideas[0]['content'] == "Pomysł 2"
    assert ideas[1]['content'] == "Pomysł 1"

def test_get_all_categories():
    db.add_task("Zadanie", category="dom")
    db.add_idea("Pomysł", category="praca")
    db.add_idea("Pomysł 2", category="dom")  # powtórzona kategoria

    cats = db.get_all_categories()
    assert cats == ["dom", "praca"]

def test_mark_task_done():
    db.add_task("Zadanie")
    active = db.get_active_tasks()
    task_id = active[0]['id']

    success = db.mark_task_done(task_id)
    assert success is True

    active_after = db.get_active_tasks()
    assert len(active_after) == 0

    completed = db.get_completed_tasks()
    assert len(completed) == 1
    assert completed[0]['id'] == task_id

def test_delete_task():
    db.add_task("Zadanie")
    active = db.get_active_tasks()
    task_id = active[0]['id']

    success = db.delete_task(task_id)
    assert success is True
    assert len(db.get_active_tasks()) == 0

def test_update_task():
    db.add_task("Zadanie")
    active = db.get_active_tasks()
    task_id = active[0]['id']

    success = db.update_task(task_id, "Nowa treść")
    assert success is True

    task = db.get_task_by_id(task_id)
    assert task['content'] == "Nowa treść"

def test_add_and_get_reminders():
    remind_at = datetime.datetime.now() + timedelta(hours=1)
    reminder_id = db.add_reminder("Zadzwonić", remind_at)
    assert reminder_id is not None

    active = db.get_active_reminders()
    assert len(active) == 1
    assert active[0]['content'] == "Zadzwonić"

def test_get_pending_reminders():
    past_time = datetime.datetime.now() - timedelta(minutes=5)
    future_time = datetime.datetime.now() + timedelta(minutes=5)

    db.add_reminder("Przeszłe", past_time)
    db.add_reminder("Przyszłe", future_time)

    pending = db.get_pending_reminders()
    assert len(pending) == 1
    assert pending[0]['content'] == "Przeszłe"

def test_mark_reminder_sent():
    remind_at = datetime.datetime.now() - timedelta(minutes=5)
    reminder_id = db.add_reminder("Zadzwonić", remind_at)

    success = db.mark_reminder_sent(reminder_id)
    assert success is True
    assert len(db.get_pending_reminders()) == 0

def test_add_and_get_recurring_reminders():
    next_run = datetime.datetime.now() + timedelta(hours=1)
    reminder_id = db.add_recurring_reminder("Cykliczne", "daily", None, "12:00", next_run)
    assert reminder_id is not None

    active = db.get_active_recurring_reminders()
    assert len(active) == 1
    assert active[0]['content'] == "Cykliczne"

def test_get_due_recurring_reminders():
    past_time = datetime.datetime.now() - timedelta(minutes=5)
    future_time = datetime.datetime.now() + timedelta(minutes=5)

    db.add_recurring_reminder("Przeszłe", "daily", None, "12:00", past_time)
    db.add_recurring_reminder("Przyszłe", "daily", None, "12:00", future_time)

    due = db.get_due_recurring_reminders()
    assert len(due) == 1
    assert due[0]['content'] == "Przeszłe"

def test_get_weekly_stats():
    db.add_task("Aktywne")
    db.add_task("Ukończone")
    
    active = db.get_active_tasks()
    task_id = [t for t in active if t['content'] == "Ukończone"][0]['id']
    db.mark_task_done(task_id)
    
    db.add_idea("Nowy Pomysł")
    
    stats = db.get_weekly_stats()
    assert stats['completed'] == 1
    assert stats['active'] == 1
    assert stats['created'] == 2
    assert stats['new_ideas'] == 1
