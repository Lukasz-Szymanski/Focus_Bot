import os
import logging
import datetime
from dotenv import load_dotenv
from telegram import Update, BotCommand, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, Application

import database as db

# Konfiguracja
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
MY_CHAT_ID = os.getenv("MY_CHAT_ID")

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

async def morning_briefing(context: ContextTypes.DEFAULT_TYPE):
    tasks = db.get_active_tasks()
    if not tasks:
        message = "☀️ Dzień dobry! Czysta karta na dziś."
    else:
        message = f"☀️ **PORANNY RAPORT**\n\nMasz {len(tasks)} zadań:\n"
        for t in tasks:
            message += f"`{t['id']}`. {t['content']}\n"
        message += "\nUżyj `/zrobione <nr>`, aby odhaczyć."
    
    await context.bot.send_message(chat_id=MY_CHAT_ID, text=message, parse_mode="Markdown")

async def post_init(application: Application):
    await application.bot.set_my_commands([
        BotCommand("zadanie", "Dodaj zadanie"),
        BotCommand("zrobione", "Oznacz zadanie jako wykonane"),
        BotCommand("pomysl", "Dodaj pomysł"),
        BotCommand("lista", "Pokaż wszystko"),
        BotCommand("usun", "Usuń zadanie lub pomysł"),
        BotCommand("edytuj", "Edytuj zadanie lub pomysł"),
        BotCommand("historia", "Pokaż ukończone zadania"),
        BotCommand("start", "Panel startowy")
    ])
    
    if application.job_queue:
        t = datetime.time(8, 00)
        application.job_queue.run_daily(morning_briefing, t, chat_id=MY_CHAT_ID)

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

async def add_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await security_check(update): return
    content = extract_content(update, context)
    
    if content:
        # Jeśli podano treść od razu (/zadanie Mleko)
        db.add_task(content)
        await update.message.reply_text(f"✅ Dodano: {content}")
        context.user_data['state'] = STATE_IDLE
    else:
        # Jeśli kliknięto sam przycisk -> pytamy o treść
        context.user_data['state'] = STATE_WAITING_TASK
        await update.message.reply_text("✍️ Napisz treść zadania:")

async def add_idea_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await security_check(update): return
    content = extract_content(update, context)
    
    if content:
        db.add_idea(content)
        await update.message.reply_text(f"💡 Zapisano: {content}")
        context.user_data['state'] = STATE_IDLE
    else:
        context.user_data['state'] = STATE_WAITING_IDEA
        await update.message.reply_text("🧠 Napisz swój pomysł:")

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
        db.add_task(text)
        await update.message.reply_text(f"✅ Dodano: {text}")
        context.user_data['state'] = STATE_IDLE

    elif state == STATE_WAITING_IDEA:
        db.add_idea(text)
        await update.message.reply_text(f"💡 Zapisano: {text}")
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

    else:
        await update.message.reply_text("🤔 Nie wiem co z tym zrobić. Wybierz opcję z menu.")

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await security_check(update): return
    context.user_data['state'] = STATE_IDLE

    tasks = db.get_active_tasks()
    ideas = db.get_ideas()

    response = "📋 **CENTRUM DOWODZENIA**\n\n"
    response += "📌 **ZADANIA:**\n"
    if tasks:
        for t in tasks:
            response += f"`{t['id']}`. {t['content']}\n"
    else:
        response += "(pusto)\n"

    response += "\n💡 **POMYSŁY:**\n"
    if ideas:
        for i in ideas:
            response += f"`{i['id']}`. {i['content']}\n"
    else:
        response += "(pusto)\n"

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
                if success:
                    await update.message.reply_text(f"🗑️ Zadanie #{item_id} usunięte.")
                else:
                    await update.message.reply_text(f"❌ Nie znaleziono zadania #{item_id}.")
            elif item_type in ['p', 'pomysl', 'pomysł']:
                success = db.delete_idea(item_id)
                if success:
                    await update.message.reply_text(f"🗑️ Pomysł #{item_id} usunięty.")
                else:
                    await update.message.reply_text(f"❌ Nie znaleziono pomysłu #{item_id}.")
            else:
                await update.message.reply_text("⚠️ Użyj: `/usun z <nr>` lub `/usun p <nr>`", parse_mode="Markdown")
        except ValueError:
            await update.message.reply_text("⚠️ Numer musi być cyfrą.")
        context.user_data['state'] = STATE_IDLE
    else:
        # Wyświetl listę przed pytaniem
        tasks = db.get_active_tasks()
        ideas = db.get_ideas()

        response = "🗑️ **CO CHCESZ USUNĄĆ?**\n\n"
        response += "📌 **ZADANIA:**\n"
        if tasks:
            for t in tasks:
                response += f"`{t['id']}`. {t['content']}\n"
        else:
            response += "(pusto)\n"

        response += "\n💡 **POMYSŁY:**\n"
        if ideas:
            for i in ideas:
                response += f"`{i['id']}`. {i['content']}\n"
        else:
            response += "(pusto)\n"

        response += "\n➡️ Wpisz `z` (zadanie) lub `p` (pomysł):"

        context.user_data['state'] = STATE_WAITING_DELETE_TYPE
        await update.message.reply_text(response, parse_mode="Markdown")

async def edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Komenda /edytuj - edytuje zadanie lub pomysł."""
    if not await security_check(update): return

    # Wyświetl listę przed pytaniem
    tasks = db.get_active_tasks()
    ideas = db.get_ideas()

    response = "✏️ **CO CHCESZ EDYTOWAĆ?**\n\n"
    response += "📌 **ZADANIA:**\n"
    if tasks:
        for t in tasks:
            response += f"`{t['id']}`. {t['content']}\n"
    else:
        response += "(pusto)\n"

    response += "\n💡 **POMYSŁY:**\n"
    if ideas:
        for i in ideas:
            response += f"`{i['id']}`. {i['content']}\n"
    else:
        response += "(pusto)\n"

    response += "\n➡️ Wpisz `z` (zadanie) lub `p` (pomysł):"

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

if __name__ == '__main__':
    if not TOKEN or not MY_CHAT_ID:
        print("BŁĄD: Uzupełnij .env")
    else:
        print("FocusBot v5 (z edycją i usuwaniem) nasłuchuje...")
        app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()

        app.add_handler(CommandHandler('start', start))
        app.add_handler(CommandHandler('zadanie', add_task_command))
        app.add_handler(CommandHandler('pomysl', add_idea_command))
        app.add_handler(CommandHandler('lista', list_command))
        app.add_handler(CommandHandler('zrobione', done_command))
        app.add_handler(CommandHandler('usun', delete_command))
        app.add_handler(CommandHandler('edytuj', edit_command))
        app.add_handler(CommandHandler('historia', history_command))

        # Obsługa polskiego /pomysł
        app.add_handler(MessageHandler(filters.Regex(r'^/pomysł'), add_idea_command))

        # Obsługa zwykłego tekstu (odpowiedzi na pytania bota)
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

        app.run_polling()