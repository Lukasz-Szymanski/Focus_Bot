import os
import datetime
from peewee import *

DB_NAME = os.getenv("DATABASE_PATH", "focus_bot.db")

db = SqliteDatabase(DB_NAME)

class BaseModel(Model):
    class Meta:
        database = db

class Task(BaseModel):
    id = AutoField()
    content = TextField()
    created_at = DateTimeField(constraints=[SQL('DEFAULT CURRENT_TIMESTAMP')])
    is_done = IntegerField(default=0)
    priority = IntegerField(default=0)
    category = TextField(null=True)

    class Meta:
        table_name = 'tasks'

class Idea(BaseModel):
    id = AutoField()
    content = TextField()
    created_at = DateTimeField(constraints=[SQL('DEFAULT CURRENT_TIMESTAMP')])
    category = TextField(null=True)

    class Meta:
        table_name = 'ideas'

class Reminder(BaseModel):
    id = AutoField()
    content = TextField()
    remind_at = DateTimeField()
    created_at = DateTimeField(constraints=[SQL('DEFAULT CURRENT_TIMESTAMP')])
    is_sent = IntegerField(default=0)

    class Meta:
        table_name = 'reminders'

class RecurringReminder(BaseModel):
    id = AutoField()
    content = TextField()
    schedule_type = TextField()
    schedule_days = TextField(null=True)
    schedule_time = TextField()
    next_run = DateTimeField()
    created_at = DateTimeField(constraints=[SQL('DEFAULT CURRENT_TIMESTAMP')])
    is_active = IntegerField(default=1)

    class Meta:
        table_name = 'recurring_reminders'


def init_db():
    """Inicjalizuje bazę danych i tworzy tabele, jeśli nie istnieją."""
    db.connect(reuse_if_open=True)
    db.create_tables([Task, Idea, Reminder, RecurringReminder])
    db.close()

def _clean_row(row_dict):
    """Konwertuje obiekty datetime na napisy ISO dla pełnej kompatybilności z bot.py."""
    if not row_dict:
        return row_dict
    for k, v in row_dict.items():
        if isinstance(v, datetime.datetime):
            row_dict[k] = v.isoformat()
    return row_dict

def _clean_rows(rows_list):
    return [_clean_row(r) for r in rows_list]


def add_task(content, priority=0, category=None):
    with db.connection_context():
        Task.create(content=content, priority=priority, category=category)

def add_idea(content, category=None):
    with db.connection_context():
        Idea.create(content=content, category=category)

def get_active_tasks(category=None):
    with db.connection_context():
        query = Task.select().where(Task.is_done == 0)
        if category:
            query = query.where(Task.category == category)
        return _clean_rows(list(query.order_by(Task.priority.desc(), Task.created_at.desc(), Task.id.desc()).dicts()))

def get_ideas(category=None):
    with db.connection_context():
        query = Idea.select()
        if category:
            query = query.where(Idea.category == category)
        return _clean_rows(list(query.order_by(Idea.created_at.desc(), Idea.id.desc()).dicts()))

def get_all_categories():
    """Pobiera unikalne kategorie z zadań i pomysłów."""
    with db.connection_context():
        task_cats = Task.select(Task.category).where(Task.category.is_null(False)).distinct().dicts()
        idea_cats = Idea.select(Idea.category).where(Idea.category.is_null(False)).distinct().dicts()
        
        categories = set()
        for row in list(task_cats) + list(idea_cats):
            if row['category']:
                categories.add(row['category'])
        return sorted(list(categories))

def mark_task_done(task_id):
    """Oznacza zadanie jako wykonane."""
    with db.connection_context():
        rows_affected = Task.update(is_done=1).where(Task.id == task_id).execute()
        return rows_affected > 0

def delete_task(task_id):
    """Usuwa zadanie z bazy."""
    with db.connection_context():
        rows_affected = Task.delete().where(Task.id == task_id).execute()
        return rows_affected > 0

def delete_idea(idea_id):
    """Usuwa pomysł z bazy."""
    with db.connection_context():
        rows_affected = Idea.delete().where(Idea.id == idea_id).execute()
        return rows_affected > 0

def update_task(task_id, new_content):
    """Aktualizuje treść zadania."""
    with db.connection_context():
        rows_affected = Task.update(content=new_content).where(Task.id == task_id).execute()
        return rows_affected > 0

def update_idea(idea_id, new_content):
    """Aktualizuje treść pomysłu."""
    with db.connection_context():
        rows_affected = Idea.update(content=new_content).where(Idea.id == idea_id).execute()
        return rows_affected > 0

def get_completed_tasks(limit=20):
    """Pobiera limit ukończonych zadań."""
    with db.connection_context():
        query = Task.select().where(Task.is_done == 1).order_by(Task.created_at.desc()).limit(limit)
        return _clean_rows(list(query.dicts()))

def get_task_by_id(task_id):
    """Pobiera zadanie po ID."""
    with db.connection_context():
        row = Task.select().where(Task.id == task_id).dicts().first()
        return _clean_row(row)

def get_idea_by_id(idea_id):
    """Pobiera pomysł po ID."""
    with db.connection_context():
        row = Idea.select().where(Idea.id == idea_id).dicts().first()
        return _clean_row(row)


# --- Przypomnienia ---

def add_reminder(content: str, remind_at: datetime.datetime) -> int:
    with db.connection_context():
        reminder = Reminder.create(content=content, remind_at=remind_at)
        return reminder.id

def get_pending_reminders() -> list:
    with db.connection_context():
        now = datetime.datetime.now()
        query = Reminder.select().where((Reminder.is_sent == 0) & (Reminder.remind_at <= now)).order_by(Reminder.remind_at)
        return _clean_rows(list(query.dicts()))

def mark_reminder_sent(reminder_id: int) -> bool:
    with db.connection_context():
        rows_affected = Reminder.update(is_sent=1).where(Reminder.id == reminder_id).execute()
        return rows_affected > 0

def get_active_reminders() -> list:
    with db.connection_context():
        query = Reminder.select().where(Reminder.is_sent == 0).order_by(Reminder.remind_at)
        return _clean_rows(list(query.dicts()))

def delete_reminder(reminder_id: int) -> bool:
    with db.connection_context():
        rows_affected = Reminder.delete().where(Reminder.id == reminder_id).execute()
        return rows_affected > 0


# --- Cykliczne Przypomnienia ---

def add_recurring_reminder(content: str, schedule_type: str, schedule_days: str | None,
                           schedule_time: str, next_run: datetime.datetime) -> int:
    with db.connection_context():
        reminder = RecurringReminder.create(
            content=content,
            schedule_type=schedule_type,
            schedule_days=schedule_days,
            schedule_time=schedule_time,
            next_run=next_run
        )
        return reminder.id

def get_active_recurring_reminders() -> list:
    with db.connection_context():
        query = RecurringReminder.select().where(RecurringReminder.is_active == 1).order_by(RecurringReminder.next_run)
        return _clean_rows(list(query.dicts()))

def get_due_recurring_reminders() -> list:
    with db.connection_context():
        now = datetime.datetime.now()
        query = RecurringReminder.select().where((RecurringReminder.is_active == 1) & (RecurringReminder.next_run <= now)).order_by(RecurringReminder.next_run)
        return _clean_rows(list(query.dicts()))

def update_recurring_reminder_next_run(reminder_id: int, next_run: datetime.datetime) -> bool:
    with db.connection_context():
        rows_affected = RecurringReminder.update(next_run=next_run).where(RecurringReminder.id == reminder_id).execute()
        return rows_affected > 0

def delete_recurring_reminder(reminder_id: int) -> bool:
    with db.connection_context():
        rows_affected = RecurringReminder.delete().where(RecurringReminder.id == reminder_id).execute()
        return rows_affected > 0

def get_recurring_reminder_by_id(reminder_id: int):
    with db.connection_context():
        row = RecurringReminder.select().where(RecurringReminder.id == reminder_id).dicts().first()
        return _clean_row(row)


if __name__ == "__main__":
    init_db()
    print("Baza danych zainicjowana.")
