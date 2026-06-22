import re
import datetime
from datetime import timedelta

WEEKDAY_MAP = {
    'pn': 0, 'pon': 0, 'poniedziałek': 0, 'poniedzialek': 0,
    'wt': 1, 'wto': 1, 'wtorek': 1,
    'śr': 2, 'sr': 2, 'sro': 2, 'środa': 2, 'sroda': 2,
    'cz': 3, 'czw': 3, 'czwartek': 3,
    'pt': 4, 'pia': 4, 'piątek': 4, 'piatek': 4,
    'sb': 5, 'sob': 5, 'sobota': 5,
    'nd': 6, 'nie': 6, 'niedziela': 6,
}

def format_task_simple(task) -> str:
    """Formatuje zadanie do postaci czytelnej dla użytkownika.

    Uwzględnia priorytet (🔴 dla pilnych) oraz kategorię (`#tag`).
    """
    priority = task['priority'] if 'priority' in task.keys() else 0
    category = task['category'] if 'category' in task.keys() and task['category'] else None
    cat_suffix = f" `#{category}`" if category else ""

    if priority:
        return f"🔴 `{task['id']}`. **{task['content']}**{cat_suffix}"
    return f"`{task['id']}`. {task['content']}{cat_suffix}"

def format_idea_simple(idea) -> str:
    """Formatuje pomysł do postaci czytelnej dla użytkownika.

    Uwzględnia kategorię (`#tag`).
    """
    category = idea['category'] if 'category' in idea.keys() and idea['category'] else None
    cat_suffix = f" `#{category}`" if category else ""
    return f"`{idea['id']}`. {idea['content']}{cat_suffix}"

def parse_priority(content: str) -> tuple[str, int]:
    """Parsuje priorytet z treści zadania.

    Zwraca oczyszczoną treść oraz liczbę określającą priorytet (1 dla pilnych, 0 domyślnie).
    Przykład:
    '! Zapłacić podatki' -> ('Zapłacić podatki', 1)
    """
    content = content.strip()
    if content.startswith('!'):
        return content[1:].strip(), 1
    return content, 0

def parse_category(content: str) -> tuple[str, str | None]:
    """Parsuje kategorię (pierwszy napotkany hashtag #tag) z treści.

    Zwraca oczyszczoną treść (bez hashtaga) oraz nazwę kategorii (małymi literami).
    Przykład:
    'Kupić karmę #dom' -> ('Kupić karmę', 'dom')
    """
    match = re.search(r'#(\w+)', content)
    if match:
        category = match.group(1).lower()
        clean_content = re.sub(r'\s*#\w+', '', content).strip()
        return clean_content, category
    return content, None

def parse_recurring_schedule(text: str) -> tuple[dict | None, str]:
    """Parsuje harmonogram cyklicznego przypomnienia.

    Obsługuje formaty:
    - 'codziennie HH:MM treść'
    - 'pon-pt HH:MM treść'
    - 'co tydzień <dzień> HH:MM treść'
    - 'pon,śr,pt HH:MM treść'
    - 'co miesiąc <dzień> HH:MM treść'

    Zwraca słownik z definicją harmonogramu i treść przypomnienia lub (None, oryginalny tekst).
    """
    text = text.strip()

    # Format: "codziennie HH:MM treść"
    daily_match = re.match(r'^codziennie\s+(\d{1,2}):(\d{2})\s+(.+)$', text, re.IGNORECASE)
    if daily_match:
        hour, minute, content = int(daily_match.group(1)), int(daily_match.group(2)), daily_match.group(3)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return {
                'type': 'daily',
                'days': None,
                'time': f"{hour:02d}:{minute:02d}"
            }, content.strip()

    # Format: "pon-pt HH:MM treść" (zakres dni)
    range_match = re.match(r'^(\w+)-(\w+)\s+(\d{1,2}):(\d{2})\s+(.+)$', text, re.IGNORECASE)
    if range_match:
        start_day = range_match.group(1).lower()
        end_day = range_match.group(2).lower()
        hour, minute = int(range_match.group(3)), int(range_match.group(4))
        content = range_match.group(5)

        if start_day in WEEKDAY_MAP and end_day in WEEKDAY_MAP and 0 <= hour <= 23 and 0 <= minute <= 59:
            start_idx = WEEKDAY_MAP[start_day]
            end_idx = WEEKDAY_MAP[end_day]
            if start_idx <= end_idx:
                days = ','.join(str(d) for d in range(start_idx, end_idx + 1))
            else:
                days = ','.join(str(d) for d in list(range(start_idx, 7)) + list(range(0, end_idx + 1)))

            return {
                'type': 'weekdays',
                'days': days,
                'time': f"{hour:02d}:{minute:02d}"
            }, content.strip()

    # Format: "co tydzień <dzień> HH:MM treść"
    weekly_match = re.match(r'^co\s+tydzie[nń]\s+(\w+)\s+(\d{1,2}):(\d{2})\s+(.+)$', text, re.IGNORECASE)
    if weekly_match:
        day = weekly_match.group(1).lower()
        hour, minute = int(weekly_match.group(2)), int(weekly_match.group(3))
        content = weekly_match.group(4)

        if day in WEEKDAY_MAP and 0 <= hour <= 23 and 0 <= minute <= 59:
            return {
                'type': 'weekly',
                'days': str(WEEKDAY_MAP[day]),
                'time': f"{hour:02d}:{minute:02d}"
            }, content.strip()

    # Format: "pon,śr,pt HH:MM treść" (lista dni)
    list_match = re.match(r'^([\w,]+)\s+(\d{1,2}):(\d{2})\s+(.+)$', text, re.IGNORECASE)
    if list_match:
        days_str = list_match.group(1).lower()
        hour, minute = int(list_match.group(2)), int(list_match.group(3))
        content = list_match.group(4)

        day_parts = [d.strip() for d in days_str.split(',')]
        if len(day_parts) > 1 and all(d in WEEKDAY_MAP for d in day_parts):
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                days = ','.join(str(WEEKDAY_MAP[d]) for d in day_parts)
                return {
                    'type': 'custom_days',
                    'days': days,
                    'time': f"{hour:02d}:{minute:02d}"
                }, content.strip()

    # Format: "co miesiąc <dzień> HH:MM treść"
    monthly_match = re.match(r'^co\s+miesi[aą]c\s+(\d{1,2})\s+(\d{1,2}):(\d{2})\s+(.+)$', text, re.IGNORECASE)
    if monthly_match:
        day_of_month = int(monthly_match.group(1))
        hour, minute = int(monthly_match.group(2)), int(monthly_match.group(3))
        content = monthly_match.group(4)

        if 1 <= day_of_month <= 31 and 0 <= hour <= 23 and 0 <= minute <= 59:
            return {
                'type': 'monthly',
                'days': str(day_of_month),
                'time': f"{hour:02d}:{minute:02d}"
            }, content.strip()

    return None, text

def calculate_next_run(schedule_type: str, days: str | None, time_str: str, now: datetime.datetime | None = None) -> datetime.datetime:
    """Oblicza najbliższy czas kolejnego uruchomienia dla przypomnienia cyklicznego.

    Wspiera harmonogramy: daily, weekdays, weekly, custom_days, monthly.
    """
    if now is None:
        now = datetime.datetime.now()
    hour, minute = map(int, time_str.split(':'))
    target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if schedule_type == 'daily':
        if target_time <= now:
            target_time += timedelta(days=1)
        return target_time

    elif schedule_type in ('weekdays', 'weekly', 'custom_days'):
        allowed_days = [int(d) for d in days.split(',')]

        for i in range(8):  # Sprawdź do 7 dni w przód
            check_date = now + timedelta(days=i)
            if check_date.weekday() in allowed_days:
                candidate = check_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if candidate > now:
                    return candidate

        # Fallback - pierwszy dozwolony dzień w następnym tygodniu
        next_week = now + timedelta(days=7)
        return next_week.replace(hour=hour, minute=minute, second=0, microsecond=0)

    elif schedule_type == 'monthly':
        day_of_month = int(days)
        # Spróbuj w tym miesiącu
        try:
            target = now.replace(day=day_of_month, hour=hour, minute=minute, second=0, microsecond=0)
            if target > now:
                return target
        except ValueError:
            pass  # Dzień nie istnieje w tym miesiącu (np. 31 w lutym)

        # Następny miesiąc
        if now.month == 12:
            next_month = now.replace(year=now.year + 1, month=1, day=1)
        else:
            next_month = now.replace(month=now.month + 1, day=1)

        try:
            return next_month.replace(day=day_of_month, hour=hour, minute=minute, second=0, microsecond=0)
        except ValueError:
            # Jeśli dzień nie istnieje, użyj ostatniego dnia miasta
            if next_month.month == 12:
                last_day = (next_month.replace(year=next_month.year + 1, month=1, day=1) - timedelta(days=1)).day
            else:
                last_day = (next_month.replace(month=next_month.month + 1, day=1) - timedelta(days=1)).day
            return next_month.replace(day=min(day_of_month, last_day), hour=hour, minute=minute, second=0, microsecond=0)

    return target_time

def format_schedule_description(schedule_type: str, days: str | None, time_str: str) -> str:
    """Formatuje harmonogram na czytelny opis słowny w języku polskim."""
    day_names = ['Pn', 'Wt', 'Śr', 'Cz', 'Pt', 'Sb', 'Nd']

    if schedule_type == 'daily':
        return f"codziennie o {time_str}"
    elif schedule_type == 'weekdays':
        day_indices = [int(d) for d in days.split(',')]
        if day_indices == [0, 1, 2, 3, 4]:
            return f"Pn-Pt o {time_str}"
        day_str = ', '.join(day_names[d] for d in day_indices)
        return f"{day_str} o {time_str}"
    elif schedule_type == 'weekly':
        day_idx = int(days)
        return f"co tydzień ({day_names[day_idx]}) o {time_str}"
    elif schedule_type == 'custom_days':
        day_indices = [int(d) for d in days.split(',')]
        day_str = ', '.join(day_names[d] for d in day_indices)
        return f"{day_str} o {time_str}"
    elif schedule_type == 'monthly':
        return f"co miesiąc ({days}.) o {time_str}"
    return time_str

def parse_reminder_time(text: str, now: datetime.datetime | None = None) -> tuple[datetime.datetime | None, str]:
    """Parsuje czas przypomnienia z tekstu.

    Obsługiwane formaty:
    - 'HH:MM treść'
    - 'za Xm treść' (minuty)
    - 'za Xh treść' (godziny)
    - 'za Xd treść' (dni)
    """
    text = text.strip()
    if now is None:
        now = datetime.datetime.now()

    # Format: "za Xm/h/d treść"
    relative_match = re.match(r'^za\s+(\d+)\s*(m|min|h|g|d|dni?)\s+(.+)$', text, re.IGNORECASE)
    if relative_match:
        amount = int(relative_match.group(1))
        unit = relative_match.group(2).lower()
        content = relative_match.group(3).strip()

        if unit in ('m', 'min'):
            remind_at = now + timedelta(minutes=amount)
        elif unit in ('h', 'g'):
            remind_at = now + timedelta(hours=amount)
        elif unit in ('d', 'dn', 'dni'):
            remind_at = now + timedelta(days=amount)
        else:
            return None, text

        return remind_at, content

    # Format: "HH:MM treść"
    time_match = re.match(r'^(\d{1,2}):(\d{2})\s+(.+)$', text)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2))
        content = time_match.group(3).strip()

        if 0 <= hour <= 23 and 0 <= minute <= 59:
            remind_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if remind_at <= now:
                remind_at += timedelta(days=1)
            return remind_at, content

    return None, text

def build_list_response(header: str, tasks: list, ideas: list, show_prompt: bool = False) -> str:
    """Buduje sformatowany tekst listy zadań i pomysłów."""
    response = f"{header}\n\n"
    response += "📌 **ZADANIA:**\n"
    if tasks:
        for t in tasks:
            response += format_task_simple(t) + "\n"
    else:
        response += "(pusto)\n"

    response += "\n💡 **POMYSŁY:**\n"
    if ideas:
        for i in ideas:
            response += format_idea_simple(i) + "\n"
    else:
        response += "(pusto)\n"

    if show_prompt:
        response += "\n➡️ Wpisz `z` (zadanie) lub `p` (pomysł):"

    return response

# Moduł pomocniczy FocusBot v1.0.0
