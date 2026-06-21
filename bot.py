import os
import re
import logging
import datetime
from datetime import timedelta
from dotenv import load_dotenv
from telegram import Update, BotCommand, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, Application

import database as db

# Konfiguracja
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
MY_CHAT_ID = os.getenv("MY_CHAT_ID")

if not TOKEN or not MY_CHAT_ID:
    raise ValueError(
        "❌ Błąd: Brak TELEGRAM_TOKEN lub MY_CHAT_ID w pliku .env!\n"
        "Skopiuj plik .env.example jako .env i uzupełnij poprawne dane."
    )

# Stałe Stanów (do konwersacji)
STATE_IDLE = "IDLE"
STATE_WAITING_TASK = "WAITING_TASK"
STATE_WAITING_IDEA = "WAITING_IDEA"
STATE_WAITING_DONE_ID = "WAITING_DONE_ID"
STATE_WAITING_DELETE_TYPE = "WAITING_DELETE_TYPE"
STATE_WAITING_DELETE_ID = "WAITING_DELETE_ID"
STATE_WAITING_EDIT_TYPE = "WAITING_EDIT_TYPE"
STATE_WAITING_EDIT_ID = "WAITING_EDIT_ID"
STATE_WAITING_EDIT_CONTENT = "WAITING_EDIT_CONTENT"
STATE_WAITING_REMINDER = "WAITING_REMINDER"

# Inicjalizacja bazy danych przy starcie
db.init_db()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def security_check(update: Update) -> bool:
    user_id = str(update.effective_user.id)
    if user_id != MY_CHAT_ID:
        await update.message.reply_text("⛔ Brak dostępu. To jest prywatny bot.")
        return False
    return True

def format_task_simple(task) -> str:
    """Formatuje zadanie z uwzględnieniem priorytetu i kategorii."""
    priority = task['priority'] if 'priority' in task.keys() else 0
    category = task['category'] if 'category' in task.keys() and task['category'] else None
    cat_suffix = f" `#{category}`" if category else ""

    if priority:
        return f"🔴 `{task['id']}`. **{task['content']}**{cat_suffix}"
    return f"`{task['id']}`. {task['content']}{cat_suffix}"

def format_idea_simple(idea) -> str:
    """Formatuje pomysł z uwzględnieniem kategorii."""
    category = idea['category'] if 'category' in idea.keys() and idea['category'] else None
    cat_suffix = f" `#{category}`" if category else ""
    return f"`{idea['id']}`. {idea['content']}{cat_suffix}"

async def morning_briefing(context: ContextTypes.DEFAULT_TYPE):
    tasks = db.get_active_tasks()
    if not tasks:
        message = "☀️ Dzień dobry! Czysta karta na dziś."
    else:
        message = f"☀️ **PORANNY RAPORT**\n\nMasz {len(tasks)} zadań:\n"
        for t in tasks:
            message += format_task_simple(t) + "\n"
        message += "\nUżyj `/zrobione <nr>`, aby odhaczyć."

    await context.bot.send_message(chat_id=MY_CHAT_ID, text=message, parse_mode="Markdown")

async def check_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Job sprawdzający i wysyłający przypomnienia."""
    reminders = db.get_pending_reminders()
    for r in reminders:
        message = f"⏰ **PRZYPOMNIENIE**\n\n{r['content']}"
        await context.bot.send_message(chat_id=MY_CHAT_ID, text=message, parse_mode="Markdown")
        db.mark_reminder_sent(r['id'])

async def post_init(application: Application):
    await application.bot.set_my_commands([
        BotCommand("zadanie", "Dodaj zadanie"),
        BotCommand("zrobione", "Oznacz zadanie jako wykonane"),
        BotCommand("pomysl", "Dodaj pomysł"),
        BotCommand("lista", "Pokaż wszystko"),
        BotCommand("usun", "Usuń zadanie lub pomysł"),
        BotCommand("edytuj", "Edytuj zadanie lub pomysł"),
        BotCommand("historia", "Pokaż ukończone zadania"),
        BotCommand("przypomnij", "Ustaw przypomnienie"),
        BotCommand("przypomnienia", "Pokaż aktywne przypomnienia"),
        BotCommand("cyklicznie", "Ustaw cykliczne przypomnienie"),
        BotCommand("cykliczne", "Pokaż cykliczne przypomnienia"),
        BotCommand("start", "Panel startowy")
    ])

    if application.job_queue:
        t = datetime.time(8, 00)
        application.job_queue.run_daily(morning_briefing, t, chat_id=MY_CHAT_ID)
        # Sprawdzaj przypomnienia co 30 sekund
        application.job_queue.run_repeating(check_reminders, interval=30, first=5)
        # Sprawdzaj cykliczne przypomnienia co 30 sekund
        application.job_queue.run_repeating(check_recurring_reminders, interval=30, first=10)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await security_check(update): return

    # Resetujemy stan
    context.user_data['state'] = STATE_IDLE

    await update.message.reply_text(
        "👋 Cześć Szefie!\n\n"
        "Wpisz `/` aby zobaczyć dostępne komendy.",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )

def extract_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    if context.args:
        return ' '.join(context.args)
    text = update.message.text
    # Jeśli wiadomość zaczyna się od komendy (np. kliknięcie przycisku), usuwamy ją
    if text and text.startswith('/'):
        parts = text.split(' ', 1)
        if len(parts) > 1:
            return parts[1]
    return ''

def parse_priority(content: str) -> tuple[str, int]:
    """Parsuje priorytet z treści zadania.

    '! Zapłacić podatki' -> ('Zapłacić podatki', 1)
    'Kupić mleko' -> ('Kupić mleko', 0)
    """
    content = content.strip()
    if content.startswith('!'):
        return content[1:].strip(), 1
    return content, 0

def parse_category(content: str) -> tuple[str, str | None]:
    """Parsuje kategorię (hashtag) z treści.

    'Kupić karmę #dom' -> ('Kupić karmę', 'dom')
    'Kupić mleko' -> ('Kupić mleko', None)
    """
    match = re.search(r'#(\w+)', content)
    if match:
        category = match.group(1).lower()
        # Usuń hashtag z treści
        clean_content = re.sub(r'\s*#\w+', '', content).strip()
        return clean_content, category
    return content, None

WEEKDAY_MAP = {
    'pn': 0, 'pon': 0, 'poniedziałek': 0, 'poniedzialek': 0,
    'wt': 1, 'wto': 1, 'wtorek': 1,
    'śr': 2, 'sr': 2, 'sro': 2, 'środa': 2, 'sroda': 2,
    'cz': 3, 'czw': 3, 'czwartek': 3,
    'pt': 4, 'pia': 4, 'piątek': 4, 'piatek': 4,
    'sb': 5, 'sob': 5, 'sobota': 5,
    'nd': 6, 'nie': 6, 'niedziela': 6,
}

def parse_recurring_schedule(text: str) -> tuple[dict | None, str]:
    """Parsuje harmonogram cyklicznego przypomnienia.

    Obsługiwane formaty:
    - 'codziennie 08:00 Poranny raport' -> (schedule_info, 'Poranny raport')
    - 'pon-pt 09:00 Standup' -> (schedule_info, 'Standup')
    - 'co tydzień pn 10:00 Weekly' -> (schedule_info, 'Weekly')
    - 'pon,śr,pt 15:00 Ćwiczenia' -> (schedule_info, 'Ćwiczenia')
    - 'co miesiąc 1 09:00 Rachunki' -> (schedule_info, 'Rachunki')

    Zwraca: (schedule_info, content) lub (None, error_message)
    schedule_info = {
        'type': 'daily' | 'weekdays' | 'weekly' | 'custom_days' | 'monthly',
        'days': str | None,  # np. '0,1,2,3,4' lub '1' (dzień miesiąca)
        'time': 'HH:MM'
    }
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

def calculate_next_run(schedule_type: str, days: str | None, time_str: str) -> datetime.datetime:
    """Oblicza następny czas uruchomienia dla cyklicznego przypomnienia."""
    now = datetime.datetime.now()
    hour, minute = map(int, time_str.split(':'))
    target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if schedule_type == 'daily':
        if target_time <= now:
            target_time += timedelta(days=1)
        return target_time

    elif schedule_type in ('weekdays', 'weekly', 'custom_days'):
        allowed_days = [int(d) for d in days.split(',')]
        current_weekday = now.weekday()

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
        # Spróbuj ten miesiąc
        try:
            target = now.replace(day=day_of_month, hour=hour, minute=minute, second=0, microsecond=0)
            if target > now:
                return target
        except ValueError:
            pass  # Dzień nie istnieje w tym miesiącu

        # Następny miesiąc
        if now.month == 12:
            next_month = now.replace(year=now.year + 1, month=1, day=1)
        else:
            next_month = now.replace(month=now.month + 1, day=1)

        try:
            return next_month.replace(day=day_of_month, hour=hour, minute=minute, second=0, microsecond=0)
        except ValueError:
            # Jeśli dzień nie istnieje, użyj ostatniego dnia miesiąca
            if next_month.month == 12:
                last_day = (next_month.replace(year=next_month.year + 1, month=1, day=1) - timedelta(days=1)).day
            else:
                last_day = (next_month.replace(month=next_month.month + 1, day=1) - timedelta(days=1)).day
            return next_month.replace(day=min(day_of_month, last_day), hour=hour, minute=minute, second=0, microsecond=0)

    return target_time

def format_schedule_description(schedule_type: str, days: str | None, time_str: str) -> str:
    """Formatuje opis harmonogramu do wyświetlenia użytkownikowi."""
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

def parse_reminder_time(text: str) -> tuple[datetime.datetime | None, str]:
    """Parsuje czas przypomnienia z tekstu.

    Obsługiwane formaty:
    - '15:00 Zadzwonić' -> (datetime z godziną 15:00, 'Zadzwonić')
    - 'za 30m Sprawdzić' -> (datetime za 30 minut, 'Sprawdzić')
    - 'za 2h Spotkanie' -> (datetime za 2 godziny, 'Spotkanie')
    - 'za 1d Raport' -> (datetime za 1 dzień, 'Raport')
    """
    text = text.strip()
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
            # Jeśli godzina już minęła, ustaw na jutro
            if remind_at <= now:
                remind_at += timedelta(days=1)
            return remind_at, content

    return None, text

# --- Funkcje pomocnicze (DRY) ---

def save_task(content: str) -> tuple[str, str]:
    """Parsuje i zapisuje zadanie. Zwraca (prefix, suffix) do odpowiedzi."""
    task_content, priority = parse_priority(content)
    task_content, category = parse_category(task_content)
    db.add_task(task_content, priority, category)
    prefix = "🔴 PILNE: " if priority else "✅ Dodano: "
    suffix = f" `#{category}`" if category else ""
    return f"{prefix}{task_content}{suffix}"

def save_idea(content: str) -> str:
    """Parsuje i zapisuje pomysł. Zwraca tekst odpowiedzi."""
    idea_content, category = parse_category(content)
    db.add_idea(idea_content, category)
    suffix = f" `#{category}`" if category else ""
    return f"💡 Zapisano: {idea_content}{suffix}"

def save_reminder(content: str) -> tuple[bool, str]:
    """Parsuje i zapisuje przypomnienie. Zwraca (sukces, tekst odpowiedzi)."""
    remind_at, reminder_content = parse_reminder_time(content)
    if remind_at:
        db.add_reminder(reminder_content, remind_at)
        time_str = remind_at.strftime("%H:%M")
        date_str = remind_at.strftime("%d.%m")
        return True, f"⏰ Przypomnienie ustawione!\n\n📝 {reminder_content}\n🕐 {time_str} ({date_str})"
    return False, (
        "⚠️ Nie rozpoznałem formatu czasu.\n\n"
        "Użyj:\n"
        "• `15:00 Zadzwonić do lekarza`\n"
        "• `za 30m Sprawdzić pranie`\n"
        "• `za 2h Spotkanie`"
    )

def build_list_response(header: str, tasks: list, ideas: list, show_prompt: bool = False) -> str:
    """Buduje odpowiedź z listą zadań i pomysłów."""
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

async def add_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await security_check(update): return
    content = extract_content(update, context)

    if content:
        response = save_task(content)
        await update.message.reply_text(response, parse_mode="Markdown")
        context.user_data['state'] = STATE_IDLE
    else:
        context.user_data['state'] = STATE_WAITING_TASK
        await update.message.reply_text("✍️ Napisz treść zadania:\n_(Dodaj `!` = PILNE, `#tag` = kategoria)_", parse_mode="Markdown")

async def add_idea_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await security_check(update): return
    content = extract_content(update, context)

    if content:
        response = save_idea(content)
        await update.message.reply_text(response, parse_mode="Markdown")
        context.user_data['state'] = STATE_IDLE
    else:
        context.user_data['state'] = STATE_WAITING_IDEA
        await update.message.reply_text("🧠 Napisz swój pomysł:\n_(Dodaj `#tag` = kategoria)_", parse_mode="Markdown")

async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await security_check(update): return
    
    # Próbujemy pobrać ID z komendy
    if context.args:
        try:
            task_id = int(context.args[0])
            success = db.mark_task_done(task_id)
            if success:
                await update.message.reply_text(f"🎉 Brawo! Zadanie #{task_id} wykonane.")
            else:
                await update.message.reply_text(f"❌ Nie znaleziono zadania o ID {task_id}.")
            context.user_data['state'] = STATE_IDLE
        except ValueError:
             await update.message.reply_text("⚠️ Numer musi być cyfrą.")
    else:
        # Kliknięto sam przycisk
        context.user_data['state'] = STATE_WAITING_DONE_ID
        await update.message.reply_text("🔢 Podaj numer zadania do odhaczenia:")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Obsługuje zwykły tekst w zależności od stanu rozmowy."""
    if not await security_check(update): return

    state = context.user_data.get('state', STATE_IDLE)
    text = update.message.text

    # Ignorujemy, jeśli ktoś wpisał komendę (obsłużą to inne handlery)
    if text.startswith('/'):
        return

    if state == STATE_WAITING_TASK:
        response = save_task(text)
        await update.message.reply_text(response, parse_mode="Markdown")
        context.user_data['state'] = STATE_IDLE

    elif state == STATE_WAITING_IDEA:
        response = save_idea(text)
        await update.message.reply_text(response, parse_mode="Markdown")
        context.user_data['state'] = STATE_IDLE

    elif state == STATE_WAITING_DONE_ID:
        try:
            task_id = int(text)
            success = db.mark_task_done(task_id)
            if success:
                await update.message.reply_text(f"🎉 Brawo! Zadanie #{task_id} wykonane.")
            else:
                await update.message.reply_text(f"❌ Nie znaleziono zadania o ID {task_id}.")
        except ValueError:
            await update.message.reply_text("⚠️ To nie jest numer. Spróbuj ponownie lub użyj innej komendy.")
        finally:
            context.user_data['state'] = STATE_IDLE

    elif state == STATE_WAITING_DELETE_TYPE:
        choice = text.lower().strip()
        if choice in ['z', 'zadanie']:
            context.user_data['delete_type'] = 'task'
            context.user_data['state'] = STATE_WAITING_DELETE_ID
            await update.message.reply_text("🔢 Podaj numer(y) zadań do usunięcia:\n_(np. `3` lub `1,3,5`)_", parse_mode="Markdown")
        elif choice in ['p', 'pomysl', 'pomysł']:
            context.user_data['delete_type'] = 'idea'
            context.user_data['state'] = STATE_WAITING_DELETE_ID
            await update.message.reply_text("🔢 Podaj numer(y) pomysłów do usunięcia:\n_(np. `2` lub `1,4,6`)_", parse_mode="Markdown")
        else:
            await update.message.reply_text("⚠️ Wpisz `z` (zadanie) lub `p` (pomysł).", parse_mode="Markdown")

    elif state == STATE_WAITING_DELETE_ID:
        # Obsługa wielu ID: "1,3,5" lub "1 3 5" lub "1, 3, 5"
        raw_ids = text.replace(',', ' ').split()
        delete_type = context.user_data.get('delete_type', 'task')
        deleted = []
        not_found = []
        invalid = []

        for raw_id in raw_ids:
            try:
                item_id = int(raw_id.strip())
                if delete_type == 'task':
                    success = db.delete_task(item_id)
                else:
                    success = db.delete_idea(item_id)

                if success:
                    deleted.append(str(item_id))
                else:
                    not_found.append(str(item_id))
            except ValueError:
                invalid.append(raw_id)

        # Buduj odpowiedź
        response = ""
        if deleted:
            item_name = "zadania" if delete_type == 'task' else "pomysły"
            response += f"🗑️ Usunięto {item_name}: #{', #'.join(deleted)}\n"
        if not_found:
            response += f"❌ Nie znaleziono: #{', #'.join(not_found)}\n"
        if invalid:
            response += f"⚠️ Nieprawidłowe: {', '.join(invalid)}"

        await update.message.reply_text(response.strip())
        context.user_data['state'] = STATE_IDLE

    elif state == STATE_WAITING_EDIT_TYPE:
        choice = text.lower().strip()
        if choice in ['z', 'zadanie']:
            context.user_data['edit_type'] = 'task'
            context.user_data['state'] = STATE_WAITING_EDIT_ID
            await update.message.reply_text("🔢 Podaj numer zadania do edycji:")
        elif choice in ['p', 'pomysl', 'pomysł']:
            context.user_data['edit_type'] = 'idea'
            context.user_data['state'] = STATE_WAITING_EDIT_ID
            await update.message.reply_text("🔢 Podaj numer pomysłu do edycji:")
        else:
            await update.message.reply_text("⚠️ Wpisz `z` (zadanie) lub `p` (pomysł).", parse_mode="Markdown")

    elif state == STATE_WAITING_EDIT_ID:
        try:
            item_id = int(text)
            edit_type = context.user_data.get('edit_type', 'task')
            if edit_type == 'task':
                item = db.get_task_by_id(item_id)
                if item:
                    context.user_data['edit_id'] = item_id
                    context.user_data['state'] = STATE_WAITING_EDIT_CONTENT
                    await update.message.reply_text(
                        f"📝 Aktualna treść:\n`{item['content']}`\n\nWpisz nową treść:",
                        parse_mode="Markdown"
                    )
                else:
                    await update.message.reply_text(f"❌ Nie znaleziono zadania #{item_id}.")
                    context.user_data['state'] = STATE_IDLE
            else:
                item = db.get_idea_by_id(item_id)
                if item:
                    context.user_data['edit_id'] = item_id
                    context.user_data['state'] = STATE_WAITING_EDIT_CONTENT
                    await update.message.reply_text(
                        f"📝 Aktualna treść:\n`{item['content']}`\n\nWpisz nową treść:",
                        parse_mode="Markdown"
                    )
                else:
                    await update.message.reply_text(f"❌ Nie znaleziono pomysłu #{item_id}.")
                    context.user_data['state'] = STATE_IDLE
        except ValueError:
            await update.message.reply_text("⚠️ To nie jest numer.")
            context.user_data['state'] = STATE_IDLE

    elif state == STATE_WAITING_EDIT_CONTENT:
        edit_type = context.user_data.get('edit_type', 'task')
        edit_id = context.user_data.get('edit_id')
        if edit_type == 'task':
            success = db.update_task(edit_id, text)
            if success:
                await update.message.reply_text(f"✏️ Zadanie #{edit_id} zaktualizowane!")
            else:
                await update.message.reply_text("❌ Wystąpił błąd podczas edycji.")
        else:
            success = db.update_idea(edit_id, text)
            if success:
                await update.message.reply_text(f"✏️ Pomysł #{edit_id} zaktualizowany!")
            else:
                await update.message.reply_text("❌ Wystąpił błąd podczas edycji.")
        context.user_data['state'] = STATE_IDLE

    elif state == STATE_WAITING_REMINDER:
        _, response = save_reminder(text)
        await update.message.reply_text(response, parse_mode="Markdown")
        context.user_data['state'] = STATE_IDLE

    else:
        await update.message.reply_text("🤔 Nie wiem co z tym zrobić. Wybierz opcję z menu.")

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await security_check(update): return
    context.user_data['state'] = STATE_IDLE

    # Sprawdź czy filtrujemy po kategorii
    content = extract_content(update, context)
    category = None
    if content:
        _, category = parse_category(content)
        if not category and content.startswith('#'):
            category = content[1:].lower().strip()

    tasks = db.get_active_tasks(category)
    ideas = db.get_ideas(category)

    if category:
        header = f"📋 **FILTR: #{category}**"
    else:
        header = "📋 **CENTRUM DOWODZENIA**"
        categories = db.get_all_categories()
        if categories:
            header += f"\n\n🏷️ Kategorie: {', '.join([f'`#{c}`' for c in categories])}"

    response = build_list_response(header, tasks, ideas)
    await update.message.reply_text(response, parse_mode="Markdown")

async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Komenda /usun - usuwa zadanie lub pomysł."""
    if not await security_check(update): return

    if context.args and len(context.args) >= 2:
        item_type = context.args[0].lower()
        try:
            item_id = int(context.args[1])
            if item_type in ['z', 'zadanie']:
                success = db.delete_task(item_id)
                msg = f"🗑️ Zadanie #{item_id} usunięte." if success else f"❌ Nie znaleziono zadania #{item_id}."
            elif item_type in ['p', 'pomysl', 'pomysł']:
                success = db.delete_idea(item_id)
                msg = f"🗑️ Pomysł #{item_id} usunięty." if success else f"❌ Nie znaleziono pomysłu #{item_id}."
            else:
                msg = "⚠️ Użyj: `/usun z <nr>` lub `/usun p <nr>`"
            await update.message.reply_text(msg, parse_mode="Markdown")
        except ValueError:
            await update.message.reply_text("⚠️ Numer musi być cyfrą.")
        context.user_data['state'] = STATE_IDLE
    else:
        tasks = db.get_active_tasks()
        ideas = db.get_ideas()
        response = build_list_response("🗑️ **CO CHCESZ USUNĄĆ?**", tasks, ideas, show_prompt=True)
        context.user_data['state'] = STATE_WAITING_DELETE_TYPE
        await update.message.reply_text(response, parse_mode="Markdown")

async def edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Komenda /edytuj - edytuje zadanie lub pomysł."""
    if not await security_check(update): return

    tasks = db.get_active_tasks()
    ideas = db.get_ideas()
    response = build_list_response("✏️ **CO CHCESZ EDYTOWAĆ?**", tasks, ideas, show_prompt=True)
    context.user_data['state'] = STATE_WAITING_EDIT_TYPE
    await update.message.reply_text(response, parse_mode="Markdown")

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Komenda /historia - pokazuje ukończone zadania."""
    if not await security_check(update): return
    context.user_data['state'] = STATE_IDLE

    completed = db.get_completed_tasks(limit=20)

    if not completed:
        await update.message.reply_text("📜 Historia jest pusta. Czas coś zrobić!")
        return

    response = "📜 **HISTORIA (ostatnie 20)**\n\n"
    for t in completed:
        response += f"✅ ~~{t['content']}~~\n"

    await update.message.reply_text(response, parse_mode="Markdown")

async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Komenda /przypomnij - ustawia przypomnienie."""
    if not await security_check(update): return

    content = extract_content(update, context)

    if content:
        _, response = save_reminder(content)
        await update.message.reply_text(response, parse_mode="Markdown")
        context.user_data['state'] = STATE_IDLE
    else:
        context.user_data['state'] = STATE_WAITING_REMINDER
        await update.message.reply_text(
            "⏰ Ustaw przypomnienie:\n\n"
            "Formaty:\n"
            "• `15:00 Zadzwonić do lekarza`\n"
            "• `za 30m Sprawdzić pranie`\n"
            "• `za 2h Spotkanie`\n"
            "• `za 1d Raport`",
            parse_mode="Markdown"
        )

async def reminders_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Komenda /przypomnienia - pokazuje aktywne przypomnienia."""
    if not await security_check(update): return
    context.user_data['state'] = STATE_IDLE

    reminders = db.get_active_reminders()

    if not reminders:
        await update.message.reply_text("⏰ Brak aktywnych przypomnień.")
        return

    response = "⏰ **AKTYWNE PRZYPOMNIENIA**\n\n"
    for r in reminders:
        remind_at = datetime.datetime.fromisoformat(r['remind_at'])
        time_str = remind_at.strftime("%H:%M")
        date_str = remind_at.strftime("%d.%m")
        response += f"`{r['id']}`. {r['content']} — 🕐 {time_str} ({date_str})\n"

    await update.message.reply_text(response, parse_mode="Markdown")

# --- Cykliczne Przypomnienia ---

async def recurring_remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Komenda /cyklicznie - tworzy cykliczne przypomnienie."""
    if not await security_check(update): return

    content = extract_content(update, context)

    if content:
        schedule_info, reminder_content = parse_recurring_schedule(content)
        if schedule_info:
            next_run = calculate_next_run(
                schedule_info['type'],
                schedule_info['days'],
                schedule_info['time']
            )
            reminder_id = db.add_recurring_reminder(
                reminder_content,
                schedule_info['type'],
                schedule_info['days'],
                schedule_info['time'],
                next_run
            )
            schedule_desc = format_schedule_description(
                schedule_info['type'],
                schedule_info['days'],
                schedule_info['time']
            )
            next_run_str = next_run.strftime("%d.%m %H:%M")
            await update.message.reply_text(
                f"🔄 Cykliczne przypomnienie #{reminder_id} utworzone!\n\n"
                f"📝 {reminder_content}\n"
                f"🗓️ {schedule_desc}\n"
                f"⏭️ Następne: {next_run_str}",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                "⚠️ Nie rozpoznałem formatu.\n\n"
                "Użyj:\n"
                "• `codziennie 08:00 Poranna kawa`\n"
                "• `pon-pt 09:00 Standup`\n"
                "• `co tydzień pn 10:00 Weekly review`\n"
                "• `pon,śr,pt 18:00 Ćwiczenia`\n"
                "• `co miesiąc 1 09:00 Rachunki`",
                parse_mode="Markdown"
            )
        context.user_data['state'] = STATE_IDLE
    else:
        await update.message.reply_text(
            "🔄 **Cykliczne przypomnienie**\n\n"
            "Formaty:\n"
            "• `codziennie 08:00 Poranna kawa`\n"
            "• `pon-pt 09:00 Standup`\n"
            "• `co tydzień pn 10:00 Weekly review`\n"
            "• `pon,śr,pt 18:00 Ćwiczenia`\n"
            "• `co miesiąc 1 09:00 Rachunki`\n\n"
            "Przykład:\n"
            "`/cyklicznie pon-pt 09:00 Daily standup`",
            parse_mode="Markdown"
        )
        context.user_data['state'] = STATE_IDLE

async def recurring_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Komenda /cykliczne - pokazuje cykliczne przypomnienia."""
    if not await security_check(update): return
    context.user_data['state'] = STATE_IDLE

    reminders = db.get_active_recurring_reminders()

    if not reminders:
        await update.message.reply_text("🔄 Brak cyklicznych przypomnień.")
        return

    response = "🔄 **CYKLICZNE PRZYPOMNIENIA**\n\n"
    for r in reminders:
        schedule_desc = format_schedule_description(
            r['schedule_type'],
            r['schedule_days'],
            r['schedule_time']
        )
        next_run = datetime.datetime.fromisoformat(r['next_run'])
        next_run_str = next_run.strftime("%d.%m %H:%M")
        response += f"`{r['id']}`. {r['content']}\n    🗓️ {schedule_desc}\n    ⏭️ {next_run_str}\n\n"

    response += "_Usuń: `/usun-cykl <nr>`_"
    await update.message.reply_text(response, parse_mode="Markdown")

async def delete_recurring_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Komenda /usun-cykl - usuwa cykliczne przypomnienie."""
    if not await security_check(update): return
    context.user_data['state'] = STATE_IDLE

    if context.args:
        try:
            reminder_id = int(context.args[0])
            reminder = db.get_recurring_reminder_by_id(reminder_id)
            if reminder:
                db.delete_recurring_reminder(reminder_id)
                await update.message.reply_text(
                    f"🗑️ Usunięto cykliczne przypomnienie #{reminder_id}:\n_{reminder['content']}_",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(f"❌ Nie znaleziono przypomnienia #{reminder_id}.")
        except ValueError:
            await update.message.reply_text("⚠️ Podaj numer przypomnienia, np. `/usun-cykl 1`", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ Podaj numer przypomnienia, np. `/usun-cykl 1`", parse_mode="Markdown")

async def check_recurring_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Job sprawdzający i wysyłający cykliczne przypomnienia."""
    reminders = db.get_due_recurring_reminders()
    for r in reminders:
        schedule_desc = format_schedule_description(
            r['schedule_type'],
            r['schedule_days'],
            r['schedule_time']
        )
        message = f"🔄 **PRZYPOMNIENIE** ({schedule_desc})\n\n{r['content']}"
        await context.bot.send_message(chat_id=MY_CHAT_ID, text=message, parse_mode="Markdown")

        # Oblicz następny czas uruchomienia
        next_run = calculate_next_run(
            r['schedule_type'],
            r['schedule_days'],
            r['schedule_time']
        )
        db.update_recurring_reminder_next_run(r['id'], next_run)

if __name__ == '__main__':
    if not TOKEN or not MY_CHAT_ID:
        print("BŁĄD: Uzupełnij .env")
    else:
        print("FocusBot v7 (z przypomnieniami) nasłuchuje...")
        app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()

        app.add_handler(CommandHandler('start', start))
        app.add_handler(CommandHandler('zadanie', add_task_command))
        app.add_handler(CommandHandler('pomysl', add_idea_command))
        app.add_handler(CommandHandler('lista', list_command))
        app.add_handler(CommandHandler('zrobione', done_command))
        app.add_handler(CommandHandler('usun', delete_command))
        app.add_handler(CommandHandler('edytuj', edit_command))
        app.add_handler(CommandHandler('historia', history_command))
        app.add_handler(CommandHandler('przypomnij', remind_command))
        app.add_handler(CommandHandler('przypomnienia', reminders_list_command))
        app.add_handler(CommandHandler('cyklicznie', recurring_remind_command))
        app.add_handler(CommandHandler('cykliczne', recurring_list_command))
        app.add_handler(CommandHandler('usun_cykl', delete_recurring_command))

        # Obsługa polskiego /pomysł
        app.add_handler(MessageHandler(filters.Regex(r'^/pomysł'), add_idea_command))
        # Obsługa /usun-cykl z myślnikiem
        app.add_handler(MessageHandler(filters.Regex(r'^/usun-cykl'), delete_recurring_command))

        # Obsługa zwykłego tekstu (odpowiedzi na pytania bota)
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

        app.run_polling()