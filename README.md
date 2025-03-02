# VetEye Service Assistant

Asystent serwisowy dla urządzeń VetEye, pomagający w diagnostyce problemów, udzielaniu informacji o produktach oraz zarządzaniu zgłoszeniami serwisowymi.

## Funkcje

- Weryfikacja urządzeń na podstawie numeru seryjnego
- Analiza problemów i diagnostyka
- Dostęp do dokumentacji technicznej
- Planowanie wizyt serwisowych
- Integracja z bazą wiedzy

## Wymagania

- Python 3.13+
- Streamlit 1.31.0+
- Klucz API Airtable
- Klucz API OpenAI

## Instalacja lokalna

1. Sklonuj repozytorium:
```bash
git clone https://github.com/MarcinSar/veteyealk.git
cd veteyealk
```

2. Zainstaluj zależności:
```bash
pip install -r requirements.txt
```

3. Utwórz plik `.env` na podstawie `.env.example` i uzupełnij zmienne środowiskowe.

4. Uruchom aplikację:
```bash
streamlit run app.py
```

## Wdrożenie na Streamlit Cloud

1. Połącz swoje konto GitHub z kontem Streamlit Cloud
2. Wybierz repozytorium `veteyealk` do wdrożenia
3. Skonfiguruj zmienne środowiskowe (klucze API)
4. Wdrożenie nastąpi automatycznie

## Wdrożenie na Heroku

1. Zainstaluj Heroku CLI
2. Zaloguj się do Heroku:
```bash
heroku login
```

3. Utwórz aplikację Heroku:
```bash
heroku create veteyealk
```

4. Skonfiguruj zmienne środowiskowe:
```bash
heroku config:set AIRTABLE_API_KEY=your_key
heroku config:set AIRTABLE_BASE_ID=your_base_id
heroku config:set OPENAI_API_KEY=your_key
```

5. Wdróż aplikację:
```bash
git push heroku master
```

## Licencja

Projekt jest własnością prywatną i nie jest dostępny do użytku publicznego bez zgody właściciela. 