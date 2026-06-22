import os
import re
import logging
import datetime
from datetime import timedelta
from dotenv import load_dotenv
from telegram import Update, BotCommand, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, Application

import database as db
import utils

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

# Funkcje formatowania format_task_simple i format_idea_simple zostały przeniesione do utils.py

async def morning_briefing(context: ContextTypes.DEFAULT_TYPE):
    tasks = db.get_active_tasks()
    if not tasks:
        message = "☀️ Dzień dobry! Czysta karta na dziś."
    else:
        message = f"☀️ **PORANNY RAPORT**\n\nMasz {len(tasks)} zadań:\n"
        for t in tasks:
            message += utils.format_task_simple(t) + "\n"
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

# Funkcje pomocnicze parsowania i harmonogramowania zostały przeniesione do utils.py

# --- Funkcje pomocnicze (DRY) ---

def save_task(content: str) -> tuple[str, str]:
    """Parsuje i zapisuje zadanie. Zwraca (prefix, suffix) do odpowiedzi."""
    task_content, priority = utils.parse_priority(content)
    task_content, category = utils.parse_category(task_content)
    db.add_task(task_content, priority, category)
    prefix = "🔴 PILNE: " if priority else "✅ Dodano: "
    suffix = f" `#{category}`" if category else ""
    return f"{prefix}{task_content}{suffix}"

def save_idea(content: str) -> str:
    """Parsuje i zapisuje pomysł. Zwraca tekst odpowiedzi."""
    idea_content, category = utils.parse_category(content)
    db.add_idea(idea_content, category)
    suffix = f" `#{category}`" if category else ""
    return f"💡 Zapisano: {idea_content}{suffix}"

def save_reminder(content: str) -> tuple[bool, str]:
    """Parsuje i zapisuje przypomnienie. Zwraca (sukces, tekst odpowiedzi)."""
    remind_at, reminder_content = utils.parse_reminder_time(content)
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

# Funkcja build_list_response została przeniesiona do utils.py

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
        _, category = utils.parse_category(content)
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

    response = utils.build_list_response(header, tasks, ideas)
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
        response = utils.build_list_response("🗑️ **CO CHCESZ USUNĄĆ?**", tasks, ideas, show_prompt=True)
        context.user_data['state'] = STATE_WAITING_DELETE_TYPE
        await update.message.reply_text(response, parse_mode="Markdown")

async def edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Komenda /edytuj - edytuje zadanie lub pomysł."""
    if not await security_check(update): return

    tasks = db.get_active_tasks()
    ideas = db.get_ideas()
    response = utils.build_list_response("✏️ **CO CHCESZ EDYTOWAĆ?**", tasks, ideas, show_prompt=True)
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
        schedule_info, reminder_content = utils.parse_recurring_schedule(content)
        if schedule_info:
            next_run = utils.calculate_next_run(
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
            schedule_desc = utils.format_schedule_description(
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
        schedule_desc = utils.format_schedule_description(
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
        schedule_desc = utils.format_schedule_description(
            r['schedule_type'],
            r['schedule_days'],
            r['schedule_time']
        )
        message = f"🔄 **PRZYPOMNIENIE** ({schedule_desc})\n\n{r['content']}"
        await context.bot.send_message(chat_id=MY_CHAT_ID, text=message, parse_mode="Markdown")

        # Oblicz następny czas uruchomienia
        next_run = utils.calculate_next_run(
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