import os
import logging
import datetime
from dotenv import load_dotenv
from telegram import Update, BotCommand, ReplyKeyboardMarkup, ReplyKeyboardRemove
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
        BotCommand("start", "Panel startowy")
    ])
    
    if application.job_queue:
        t = datetime.time(8, 00)
        application.job_queue.run_daily(morning_briefing, t, chat_id=MY_CHAT_ID)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await security_check(update): return
    
    # Resetujemy stan
    context.user_data['state'] = STATE_IDLE
    
    keyboard = [
        ['📋 /lista'],
        ['📌 /zadanie', '💡 /pomysl'],
        ['✅ /zrobione']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "👋 Cześć Szefie! Wybierz co chcesz zrobić.",
        reply_markup=reply_markup
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
            
    else:
        # Jeśli nie czekamy na nic konkretnego, traktujemy to domyślnie jako notatkę/zadanie (Inbox)
        # Lub po prostu odpisujemy, że nie rozumiemy. Tutaj: echo z podpowiedzią.
        await update.message.reply_text("🤔 Nie wiem co z tym zrobić. Wybierz opcję z menu.")

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await security_check(update): return
    context.user_data['state'] = STATE_IDLE # Reset stanu przy wyświetlaniu listy
    
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
            response += f"- {i['content']}\n"
    else:
        response += "(pusto)\n"
    
    await update.message.reply_text(response, parse_mode="Markdown")

if __name__ == '__main__':
    if not TOKEN or not MY_CHAT_ID:
        print("BŁĄD: Uzupełnij .env")
    else:
        print("FocusBot v4 (Conversation Mode) nasłuchuje...")
        app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
        
        app.add_handler(CommandHandler('start', start))
        app.add_handler(CommandHandler('zadanie', add_task_command))
        app.add_handler(CommandHandler('pomysl', add_idea_command))
        app.add_handler(CommandHandler('lista', list_command))
        app.add_handler(CommandHandler('zrobione', done_command))
        
        # Obsługa przycisków
        app.add_handler(MessageHandler(filters.Regex(r'^📋 /lista'), list_command))
        app.add_handler(MessageHandler(filters.Regex(r'^📌 /zadanie'), add_task_command))
        app.add_handler(MessageHandler(filters.Regex(r'^💡 /pomysl'), add_idea_command))
        app.add_handler(MessageHandler(filters.Regex(r'^✅ /zrobione'), done_command))
        app.add_handler(MessageHandler(filters.Regex(r'^/pomysł'), add_idea_command))

        # Obsługa zwykłego tekstu (odpowiedzi na pytania bota)
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
        
        app.run_polling()