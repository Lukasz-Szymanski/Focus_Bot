import datetime
import pytest
from datetime import timedelta

import utils

# --- Testy parsowania priorytetów ---
def test_parse_priority_urgent():
    content, priority = utils.parse_priority("! Kupić mleko")
    assert content == "Kupić mleko"
    assert priority == 1

def test_parse_priority_normal():
    content, priority = utils.parse_priority("Kupić mleko")
    assert content == "Kupić mleko"
    assert priority == 0

def test_parse_priority_whitespace():
    content, priority = utils.parse_priority("  !   Kupić mleko   ")
    assert content == "Kupić mleko"
    assert priority == 1


# --- Testy parsowania kategorii ---
def test_parse_category_present():
    content, category = utils.parse_category("Kupić karmę #dom")
    assert content == "Kupić karmę"
    assert category == "dom"

def test_parse_category_not_present():
    content, category = utils.parse_category("Kupić karmę")
    assert content == "Kupić karmę"
    assert category is None

def test_parse_category_case_insensitive():
    content, category = utils.parse_category("Zrobić przelew #Praca")
    assert content == "Zrobić przelew"
    assert category == "praca"


# --- Testy parsowania czasu przypomnień ---
def test_parse_reminder_time_relative_minutes():
    base_time = datetime.datetime(2026, 6, 22, 12, 0)
    remind_at, content = utils.parse_reminder_time("za 30m Sprawdzić pranie", now=base_time)
    assert content == "Sprawdzić pranie"
    assert remind_at == base_time + timedelta(minutes=30)

def test_parse_reminder_time_relative_hours():
    base_time = datetime.datetime(2026, 6, 22, 12, 0)
    remind_at, content = utils.parse_reminder_time("za 2h Spotkanie", now=base_time)
    assert content == "Spotkanie"
    assert remind_at == base_time + timedelta(hours=2)

def test_parse_reminder_time_absolute_future():
    base_time = datetime.datetime(2026, 6, 22, 12, 0)
    remind_at, content = utils.parse_reminder_time("15:00 Zadzwonić", now=base_time)
    assert content == "Zadzwonić"
    assert remind_at == datetime.datetime(2026, 6, 22, 15, 0)

def test_parse_reminder_time_absolute_past_should_be_tomorrow():
    base_time = datetime.datetime(2026, 6, 22, 16, 0)
    remind_at, content = utils.parse_reminder_time("15:00 Zadzwonić", now=base_time)
    assert content == "Zadzwonić"
    assert remind_at == datetime.datetime(2026, 6, 23, 15, 0)


# --- Testy parsowania cyklicznych przypomnień ---
def test_parse_recurring_schedule_daily():
    schedule, content = utils.parse_recurring_schedule("codziennie 08:30 Raport")
    assert content == "Raport"
    assert schedule == {
        'type': 'daily',
        'days': None,
        'time': '08:30'
    }

def test_parse_recurring_schedule_range():
    schedule, content = utils.parse_recurring_schedule("pon-pt 09:00 Standup")
    assert content == "Standup"
    assert schedule == {
        'type': 'weekdays',
        'days': '0,1,2,3,4',
        'time': '09:00'
    }

def test_parse_recurring_schedule_weekly():
    schedule, content = utils.parse_recurring_schedule("co tydzień śr 10:00 Pranie")
    assert content == "Pranie"
    assert schedule == {
        'type': 'weekly',
        'days': '2',
        'time': '10:00'
    }

def test_parse_recurring_schedule_list():
    schedule, content = utils.parse_recurring_schedule("pon,śr,pt 18:00 Siłownia")
    assert content == "Siłownia"
    assert schedule == {
        'type': 'custom_days',
        'days': '0,2,4',
        'time': '18:00'
    }

def test_parse_recurring_schedule_monthly():
    schedule, content = utils.parse_recurring_schedule("co miesiąc 10 09:00 Opłata")
    assert content == "Opłata"
    assert schedule == {
        'type': 'monthly',
        'days': '10',
        'time': '09:00'
    }


# --- Testy obliczania czasu następnego uruchomienia ---
def test_calculate_next_run_daily_future():
    # Poniedziałek, 12:00
    base_time = datetime.datetime(2026, 6, 22, 12, 0)
    next_run = utils.calculate_next_run('daily', None, '15:00', now=base_time)
    assert next_run == datetime.datetime(2026, 6, 22, 15, 0)

def test_calculate_next_run_daily_past():
    # Poniedziałek, 16:00
    base_time = datetime.datetime(2026, 6, 22, 16, 0)
    next_run = utils.calculate_next_run('daily', None, '15:00', now=base_time)
    assert next_run == datetime.datetime(2026, 6, 23, 15, 0)

def test_calculate_next_run_weekdays_future():
    # Poniedziałek, 12:00
    base_time = datetime.datetime(2026, 6, 22, 12, 0)
    next_run = utils.calculate_next_run('weekdays', '0,1,2,3,4', '15:00', now=base_time)
    assert next_run == datetime.datetime(2026, 6, 22, 15, 0)

def test_calculate_next_run_weekdays_weekend():
    # Sobota, 12:00
    base_time = datetime.datetime(2026, 6, 27, 12, 0)
    next_run = utils.calculate_next_run('weekdays', '0,1,2,3,4', '15:00', now=base_time)
    assert next_run == datetime.datetime(2026, 6, 29, 15, 0)


# --- Testy formatowania opisów i widoków ---
def test_format_schedule_description_daily():
    desc = utils.format_schedule_description('daily', None, '12:00')
    assert desc == "codziennie o 12:00"

def test_format_schedule_description_weekdays():
    desc = utils.format_schedule_description('weekdays', '0,1,2,3,4', '09:00')
    assert desc == "Pn-Pt o 09:00"

def test_format_task_simple_normal():
    task = {'id': 1, 'content': 'Test task', 'priority': 0, 'category': None}
    assert utils.format_task_simple(task) == "`1`. Test task"

def test_format_task_simple_priority_and_tag():
    task = {'id': 2, 'content': 'Urgent task', 'priority': 1, 'category': 'work'}
    assert utils.format_task_simple(task) == "🔴 `2`. **Urgent task** `#work`"
