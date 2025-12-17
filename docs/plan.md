# 🗺️ FocusBot: Plan Realizacji

> **Cel:** Stworzenie prywatnego asystenta na Telegramie do zarządzania zadaniami i pomysłami z poziomu czatu.

---

## ETAP 1: Fundamenty (Setup) ✅
- [x] Utworzenie bota w Telegramie (@BotFather).
- [x] Konfiguracja środowiska (Python, `python-telegram-bot`).
- [x] Zabezpieczenie tokenów (`.env`, `.gitignore`).
- [x] Test połączenia ("Hello World" bot).

## ETAP 2: Baza Danych i Logika ✅
- [x] Zaprojektowanie schematu bazy SQLite (`tasks`, `ideas`).
- [x] Implementacja modułu `database.py` (CRUD).
- [x] Stworzenie komend dodawania: `/zadanie`, `/pomysl`.
- [x] Stworzenie komendy wyświetlania: `/lista`.
- [x] Obsługa polskich znaków (alias `/pomysł`).

## ETAP 3: Interakcja i UX (UI) ✅
- [x] Dodanie Menu Komend w Telegramie (podpowiedzi `/`).
- [x] Implementacja przycisków pod klawiaturą (`ReplyKeyboard`).
- [x] **Tryb Konwersacyjny:** Obsługa kliknięć w przyciski bez wpisywania argumentów (Bot pyta o treść).

## ETAP 4: Zarządzanie Zadaniami (Flow) ✅
- [x] Wyświetlanie ID zadań na liście.
- [x] Komenda `/zrobione <id>` do odhaczania zadań.
- [x] Obsługa błędów (np. podanie błędnego ID).

## ETAP 5: Automatyzacja (Budzik) ✅
- [x] Instalacja biblioteki `apscheduler`.
- [x] Konfiguracja `JobQueue`.
- [x] Implementacja "Porannego Raportu" o godzinie 08:00.

---

## 🔮 ETAP 6: Przyszłość (Backlog)
- [ ] **Edycja:** Możliwość poprawienia treści zadania.
- [ ] **Kategorie:** Tagowanie zadań (np. #dom, #praca).
- [ ] **Hosting:** Przeniesienie bota na serwer VPS (działanie 24/7).
- [ ] **Statystyki:** Tygodniowe podsumowanie wykonanych zadań.
