# 🎯 FocusBot

> **Your Private Digital Second Brain.**
>
> FocusBot is a lightweight, secure Telegram bot designed to capture tasks and ideas instantly, minimizing friction and context switching. Built with Python and SQLite.

---

## 🧐 What is it?

FocusBot acts as a "Capture Tool" for your productivity system. Instead of opening complex apps to write down "Buy milk" or "App idea", you simply text your private bot. It stores everything in a local database, ensuring your data stays with you.

## 🚀 Features

-   **📝 Quick Capture:** Add tasks and ideas via simple commands.
-   **✏️ Edit & Delete:** Full control over your entries - edit or delete tasks and ideas.
-   **🗑️ Batch Delete:** Remove multiple items at once (e.g., `1,3,5`).
-   **📜 History:** View completed tasks for motivation.
-   **🇵🇱 Polish Language Support:** Handles special characters gracefully (e.g., `/pomysł`).
-   **🛡️ Private & Secure:** Uses a whitelist (`MY_CHAT_ID`) to ignore messages from unauthorized users.
-   **💾 Local Database:** All data is stored in a lightweight `sqlite3` database (`focus_bot.db`).
-   **📋 Instant Overview:** View all active tasks and ideas with a single command.
-   **☀️ Morning Briefing:** Automatic daily report at 08:00 with all active tasks.

## 🛠️ Prerequisites

-   Python 3.9+
-   A Telegram account
-   A Bot Token (from @BotFather)

## ⚙️ Installation & Setup

1.  **Clone or Navigate to the folder:**
    ```bash
    cd focus_bot
    ```

2.  **Install Dependencies:**
    ```bash
    pip install python-telegram-bot python-dotenv
    ```

3.  **Configure Secrets:**
    Create a `.env` file in the `focus_bot` directory (use `.env.example` as a reference):
    ```ini
    TELEGRAM_TOKEN=your_bot_token_here
    MY_CHAT_ID=123456789
    ```
    *(To find your Chat ID, run the bot and send `/start` - it will display your ID in the console).*

4.  **Run the Bot:**
    ```bash
    python bot.py
    ```

## 💻 Usage

| Command | Description | Example |
| :--- | :--- | :--- |
| `/zadanie <text>` | Adds a new task. Interactive mode if no text. | `/zadanie Buy coffee` |
| `/zrobione <id>` | Marks a task as completed. | `/zrobione 1` |
| `/pomysl <text>` | Saves an idea. | `/pomysl New app logic` |
| `/pomysł <text>` | Alias for idea (supports 'ł'). | `/pomysł Nowy projekt` |
| `/lista` | Shows all active tasks and ideas with IDs. | `/lista` |
| `/usun` | Deletes task or idea. Supports batch: `1,3,5` | `/usun z 1` or `/usun p 2` |
| `/edytuj` | Edits task or idea content. | `/edytuj` |
| `/historia` | Shows last 20 completed tasks. | `/historia` |
| `/start` | Welcome message, removes old keyboard. | `/start` |

## 📂 Project Structure

```text
focus_bot/
├── docs/             # Project documentation (Brief & Plan)
├── bot.py            # Main entry point, Telegram logic & State Machine
├── database.py       # SQLite database connection & CRUD operations
├── .env              # Secrets (Token & Chat ID) - NOT COMMITTED
├── .gitignore        # Git rules
└── README.md         # Documentation
```

---

## 📜 Changelog

<details>
<summary><strong>Click to expand version history</strong></summary>

### v0.6.0 (2025-12-30)
*   **feat(core):** Implemented `/usun` command to delete tasks and ideas.
*   **feat(core):** Implemented `/edytuj` command to edit tasks and ideas.
*   **feat(core):** Implemented `/historia` command to view completed tasks.
*   **feat(ux):** Batch delete support - remove multiple items at once (`1,3,5`).
*   **feat(ux):** Show list before delete/edit for better context.
*   **feat(ux):** Removed Reply Keyboard in favor of cleaner `/` command menu.
*   **feat(db):** Added `delete_task`, `delete_idea`, `update_task`, `update_idea`, `get_completed_tasks`, `get_task_by_id`, `get_idea_by_id` functions.

### v0.5.0 (2025-12-17)
*   **feat(ui):** Implemented **Conversational Mode** (State Machine). If a command is sent without parameters, the bot asks for input.
*   **feat(ui):** Added **Reply Keyboard** (buttons under the keyboard) for faster access on mobile.
*   **chore:** Removed `/z` shortcut to maintain a cleaner interface.

### v0.4.0 (2025-12-17)
*   **feat(core):** Implemented `/zrobione <id>` command to mark tasks as done.
*   **feat(ui):** Updated `/lista` to display Task IDs for easy reference.
*   **feat(db):** Added `mark_task_done` function to handle task status updates.

### v0.3.0 (2025-12-17)
*   **feat(ui):** Added interactive Command Menu (`post_init`) - hints appear when typing `/`.

### v0.2.0 (2025-12-17)
*   **feat(commands):** Added support for Polish characters in commands.
*   **fix(bot):** Implemented `Regex` `MessageHandler` workaround to bypass Telegram's ASCII-only command restriction for `/pomysł`.

### v0.1.0 (2025-12-17)
*   **feat(core):** Initial release of the MVP.
*   **feat(db):** Implemented SQLite backend (`database.py`) with `tasks` and `ideas` tables.
*   **feat(security):** Added `security_check` middleware to block unauthorized users via `MY_CHAT_ID`.
*   **feat(bot):** Implemented core handlers: `/zadanie`, `/pomysl`, `/lista`.
*   **chore:** Set up project structure (`.env`, `.gitignore`, `requirements`).

</details>

---

_Created by Łukasz Szymański._
