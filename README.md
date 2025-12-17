# 🎯 FocusBot

> **Your Private Digital Second Brain.**
>
> FocusBot is a lightweight, secure Telegram bot designed to capture tasks and ideas instantly, minimizing friction and context switching. Built with Python and SQLite.

---

## 🧐 What is it?

FocusBot acts as a "Capture Tool" for your productivity system. Instead of opening complex apps to write down "Buy milk" or "App idea", you simply text your private bot. It stores everything in a local database, ensuring your data stays with you.

## 🚀 Features

-   **📝 Quick Capture:** Add tasks and ideas via simple commands.
-   **🇵🇱 Polish Language Support:** Handles special characters gracefully (e.g., `/pomysł`).
-   **🛡️ Private & Secure:** Uses a whitelist (`MY_CHAT_ID`) to ignore messages from unauthorized users.
-   **💾 Local Database:** All data is stored in a lightweight `sqlite3` database (`focus_bot.db`).
-   **📋 Instant Overview:** View all active tasks and ideas with a single command.

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
| `/zadanie <text>` | Adds a new task. Can be used without text for interactive mode. | `/zadanie Buy coffee` |
| `/zrobione <id>` | Marks a task as completed. Can be used without ID for interactive mode. | `/zrobione 1` |
| `/pomysl <text>` | Saves an idea. Can be used without text for interactive mode. | `/pomysl New app logic` |
| `/pomysł <text>` | Alias for idea (supports 'ł'). | `/pomysł Nowy projekt` |
| `/lista` | Shows all active tasks with IDs. | `/lista` |
| `/start` | checks connection and displays interactive UI buttons. | `/start` |

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
