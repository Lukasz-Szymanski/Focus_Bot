# 🎯 FocusBot: Brief Projektu

FocusBot to prywatny asystent na Telegramie, który pomaga w błyskawicznym zapisywaniu zadań i pomysłów oraz dba o to, by użytkownik zaczął dzień z jasnym planem.

---

## 🛠️ Podstawowe Funkcjonalności

1. **System Komend (Opcja A):**
   - `/zadanie <treść>` – dodaje nową pozycję do listy zadań.
   - `/pomysl <treść>` – zapisuje pomysł do osobnej listy inspiracji.
   - `/lista` – wyświetla aktualne zadania i pomysły.

2. **Poranny Raport (Morning Brief):**
   - Codziennie o godzinie **08:00** bot automatycznie wysyła zestawienie wszystkich aktywnych zadań.

3. **Prywatność i Bezpieczeństwo:**
   - **White-list:** Bot reaguje tylko na komendy od konkretnego ID użytkownika (Ciebie). Próby kontaktu od innych osób są ignorowane.

---

## 🏗️ Architektura Techniczna

- **Język:** Python 3.9+
- **Interfejs:** Telegram Bot API (biblioteka `python-telegram-bot` lub `aiogram`)
- **Baza Danych:** SQLite (lokalny plik `focus_bot.db`)
- **Harmonogram (Scheduler):** `apscheduler` (do obsługi raportów o 08:00)

---

## 📅 Plan Implementacji (MVP)

1. **Faza 1: Bot Setup** – Rejestracja bota u @BotFather, konfiguracja środowiska i skrypt "Hello World".
2. **Faza 2: Database & Storage** – Tworzenie tabel SQLite i logika zapisywania zadań/pomysłów.
3. **Faza 3: Logic & Commands** – Implementacja komend `/zadanie` i `/pomysl`.
4. **Faza 4: Reminder System** – Konfiguracja automatycznego wysyłania wiadomości o 08:00.
5. **Faza 5: Polish & Security** – Zablokowanie dostępu dla osób trzecich i estetyczne formatowanie wiadomości.
