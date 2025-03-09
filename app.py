import logging
import sys
import os
import streamlit as st
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
from dateutil.parser import parse
import pytz
from airtable import Airtable
import toml
from pathlib import Path

# Konfiguracja zmiennych środowiskowych
def load_environment_variables():
    """Ładuje zmienne środowiskowe z różnych źródeł"""
    # 1. Próba załadowania z pliku .env (lokalne środowisko)
    load_dotenv()
    
    # 2. Próba załadowania z Streamlit secrets
    try:
        if hasattr(st, 'secrets') and 'AIRTABLE_API_KEY' in st.secrets:
            os.environ['AIRTABLE_API_KEY'] = st.secrets['AIRTABLE_API_KEY']
            os.environ['AIRTABLE_BASE_ID'] = st.secrets['AIRTABLE_BASE_ID']
            os.environ['OPENAI_API_KEY'] = st.secrets['OPENAI_API_KEY']
            os.environ['DEBUG'] = st.secrets.get('DEBUG', 'False')
            print("Załadowano zmienne środowiskowe ze Streamlit secrets")
            return True
    except Exception as e:
        print(f"Błąd podczas ładowania sekretów ze Streamlit: {e}")
    
    # 3. Próba załadowania z pliku .streamlit/secrets.toml
    try:
        secrets_path = Path(".streamlit/secrets.toml")
        if secrets_path.exists():
            secrets = toml.load(secrets_path)
            os.environ['AIRTABLE_API_KEY'] = secrets['AIRTABLE_API_KEY']
            os.environ['AIRTABLE_BASE_ID'] = secrets['AIRTABLE_BASE_ID']
            os.environ['OPENAI_API_KEY'] = secrets['OPENAI_API_KEY']
            os.environ['DEBUG'] = secrets.get('DEBUG', 'False')
            print("Załadowano zmienne środowiskowe z pliku .streamlit/secrets.toml")
            return True
    except Exception as e:
        print(f"Błąd podczas ładowania sekretów z pliku: {e}")
    
    # Sprawdź, czy zmienne są już ustawione w środowisku
    required_vars = ['AIRTABLE_API_KEY', 'AIRTABLE_BASE_ID', 'OPENAI_API_KEY']
    if all(var in os.environ for var in required_vars):
        print("Zmienne środowiskowe już ustawione w systemie")
        return True
    
    print("UWAGA: Nie udało się załadować wszystkich wymaganych zmiennych środowiskowych!")
    return False

# Ładowanie zmiennych środowiskowych
load_environment_variables()

# Konfiguracja logowania
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log', encoding='utf-8')
    ]
)

# Ustawienie poziomów logowania dla różnych modułów
logging.getLogger().setLevel(logging.DEBUG)
logging.getLogger('airtable').setLevel(logging.INFO)
logging.getLogger('calendar').setLevel(logging.INFO)

# Logger dla głównej aplikacji
logger = logging.getLogger('app')
logger.setLevel(logging.DEBUG)

# Ładowanie modułów aplikacji
from utils.airtable import AirtableClient
from utils.calendar import CalendarClient
from utils.knowledge import KnowledgeBase
from utils.ai import AIHelper
from src.models.states import ConversationState, ConversationContext, VALID_STATE_TRANSITIONS

# Konfiguracja strony Streamlit
st.set_page_config(
    page_title="VetEye Service Assistant",
    page_icon="🩺",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Inicjalizacja komponentów
def initialize_components():
    """Inicjalizuje komponenty aplikacji"""
    try:
        airtable_client = AirtableClient(
            api_key=os.getenv('AIRTABLE_API_KEY'),
            base_id=os.getenv('AIRTABLE_BASE_ID')
        )
        calendar_client = CalendarClient()
        knowledge_base = KnowledgeBase()
        ai_helper = AIHelper(api_key=os.getenv('OPENAI_API_KEY'))
        
        return airtable_client, calendar_client, knowledge_base, ai_helper
    except Exception as e:
        logger.error(f"Error initializing components: {str(e)}", exc_info=True)
        st.error(f"Błąd inicjalizacji komponentów: {str(e)}")
        return None, None, None, None

# Inicjalizacja stanu sesji
def initialize_session_state():
    """Inicjalizuje stan sesji aplikacji"""
    # Główny kontekst konwersacji
    if 'context' not in st.session_state:
        st.session_state.context = ConversationContext()
    
    # Historia wiadomości
    if 'messages' not in st.session_state:
        st.session_state.messages = []
        # Dodaj wiadomość powitalną
        st.session_state.messages.append({
            "role": "assistant",
            "content": """## 👋 Witaj w serwisie wsparcia technicznego Vet-Eye!

Jestem Agentem AI i moim zadaniem jest udzielenie wsparcia w celu rozwiązania Twoich problemów z urządzeniem wyprodukowanym przez Vet-Eye.

### Aby kontynuować naszą rozmowę potrzebuję Twojej zgody na:

1. Rozpoczęcie interakcji ze mną, jako Agentem AI. Musisz wiedzieć, że nie jestem człowiekiem, tylko systemem sztucznej inteligencji, który będzie przetwarzał informacje wprowadzone przez Ciebie podczas rozmowy w celu zdiagnozowania opisywanych przez Ciebie problemów technicznych i ich rozwiązania, a także

2. Przetwarzanie Twoich danych osobowych przez VetEye Sp. z o.o., jako Administrator danych osobowych, zgodnie z przepisami rozporządzenia RODO, w przypadku konieczności utworzenia zgłoszenia serwisowego.

### Informacje o przetwarzaniu danych:

* Twoje dane osobowe będą zbierane tylko wtedy, gdy nie uda się rozwiązać zgłoszonego problemu i konieczne będzie przygotowanie zlecenia serwisowego
* Twoje dane osobowe będą przetwarzane w celu przygotowania zlecenia serwisowego i jego późniejszej obsługi oraz kontaktu naszego serwisu w sprawie realizacji tego zlecenia
* Twoje dane osobowe będą przechowywane przez okres niezbędny do realizacji usługi oraz wymagany przepisami prawa
* Przysługuje Ci prawo dostępu do swoich danych, ich sprostowania, usunięcia, ograniczenia przetwarzania, a także ich przenoszenia oraz wniesienia sprzeciwu
* Masz prawo wniesienia skargi do Urzędu Ochrony Danych Osobowych, jeżeli Twoje dane osobowe będą przetwarzane niezgodnie z deklaracją Administratora Danych Osobowych
* Szczegółowe informacje znajdziesz w naszej Polityce Prywatności

**Czy wyrażasz zgodę na powyższe warunki? (tak/nie)**

*Uwaga: Brak Twojej zgody na którykolwiek z powyższych punktów, uniemożliwi rozpoczęcie naszej rozmowy, zdiagnozowanie problemu i uzyskanie wsparcia technicznego.*"""
        })
    
    # Dostępne terminy
    if 'available_slots' not in st.session_state:
        st.session_state.available_slots = []
    if 'formatted_slots' not in st.session_state:
        st.session_state.formatted_slots = []
    if 'showing_slots' not in st.session_state:
        st.session_state.showing_slots = False
    
    # Dane urządzenia i klienta
    defaults = {
        'device_info': None,
        'issue_description': "",
        'selected_slot': None,
        'client_name': "",
        'client_phone': "",
        'client_email': "",
        'client_address': "",
        'current_model': "",
        'error_message': "",
        'is_submitting': False
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# Funkcja zmieniająca stan konwersacji
def set_state(new_state: ConversationState) -> bool:
    """
    Zmienia stan konwersacji na nowy
    
    Args:
        new_state: Docelowy stan konwersacji
        
    Returns:
        bool: True jeśli przejście było udane, False w przeciwnym razie
    """
    try:
        current_state = st.session_state.context.current_state
        
        if new_state in VALID_STATE_TRANSITIONS.get(current_state, set()):
            st.session_state.context.current_state = new_state
            logger.info(f"State transition: {current_state.value} -> {new_state.value}")
            return True
        else:
            logger.warning(f"Invalid state transition: {current_state.value} -> {new_state.value}")
            return False
    except Exception as e:
        logger.error(f"Error in set_state: {str(e)}", exc_info=True)
        return False

# Obsługa stanów konwersacji
def handle_welcome(message: str) -> str:
    """Obsługuje stan powitalny i zgodę RODO"""
    # Obsługa odpowiedzi na pytanie o zgodę RODO
    if message.lower() in ['tak', 't', 'yes', 'y']:
        # First set GDPR consent
        st.session_state.context.gdpr_consent = True
        # Then attempt state transition
        if set_state(ConversationState.DEVICE_VERIFICATION):
            return """### Dziękuję za zgodę! 🙂 

Aby pomóc Ci w diagnostyce, potrzebuję numeru seryjnego Twojego urządzenia. Pomoże mi to lepiej zrozumieć problem i pomóc Ci w jego rozwiązaniu i jednocześnie sprawdzić czy urządzenie jest objęte gwarancją. 

**Proszę podaj numer seryjny w formacie: SN: XXXX** 
(gdzie XXXX to właściwy numer seryjny urządzenia)"""
        else:
            return "Przepraszam, wystąpił błąd podczas przetwarzania zgody. Spróbuj ponownie."
    elif message.lower() in ['nie', 'n', 'no']:
        # Zwróć komunikat o zakończeniu rozmowy bez zmiany stanu
        return """### Rozumiem Twoją decyzję.

Niestety bez Twojej zgody na przetwarzanie danych osobowych i rozmowę z Agentem AI nie możemy kontynuować rozmowy ani udzielić wsparcia technicznego poprzez tego asystenta.

Jeśli nadal potrzebujesz pomocy z urządzeniem, prosimy o bezpośredni kontakt z naszym działem serwisu:

**Telefon:** +48 444 444 444
**E-mail:** serwis@veteye.pl

Nasi specjaliści są dostępni od poniedziałku do piątku w godzinach 8:00-16:00.

Dziękujemy za zrozumienie i życzymy miłego dnia!"""
    else:
        # Sprawdź, czy użytkownik już wyraził zgodę RODO, ale wpisuje coś innego niż numer seryjny
        if hasattr(st.session_state.context, 'gdpr_consent') and st.session_state.context.gdpr_consent:
            return """### Potrzebuję numeru seryjnego Twojego urządzenia

Aby kontynuować diagnostykę, proszę podaj numer seryjny w formacie: SN: XXXX
(gdzie XXXX to właściwy numer seryjny urządzenia)

Numer seryjny znajduje się na naklejce na spodzie lub z tyłu urządzenia."""
        else:
            return """### Przepraszam, ale aby kontynuować potrzebuję jasnej odpowiedzi.

Czy wyrażasz zgodę na przetwarzanie danych osobowych zgodnie z RODO w przypadku konieczności utworzenia zgłoszenia serwisowego? 

**Proszę odpowiedz: tak lub nie**"""

def handle_device_verification(message: str, airtable_client: AirtableClient) -> str:
    """Obsługuje weryfikację urządzenia"""
    # Sprawdź, czy wiadomość wygląda jak numer seryjny
    if not message.lower().startswith("sn:") and not message.lower().startswith("sn "):
        # Jeśli nie wygląda jak numer seryjny, poproś o podanie numeru seryjnego
        return """### Potrzebuję numeru seryjnego Twojego urządzenia

Aby kontynuować diagnostykę, proszę podaj numer seryjny w formacie: SN: XXXX
(gdzie XXXX to właściwy numer seryjny urządzenia)

Numer seryjny znajduje się na naklejce na spodzie lub z tyłu urządzenia."""
    
    result = airtable_client.get_device_info(message)
    
    if result["status"] == "success":
        device = result["device"]
        st.session_state.device_info = device
        st.session_state.current_model = device['fields'].get('model', 'Nieznany model')
        warranty = device['fields'].get('warranty_status', 'Brak informacji')
        
        # Zapisz urządzenie w kontekście
        st.session_state.context.verified_device = device
        
        set_state(ConversationState.ISSUE_ANALYSIS)
        return f"""### ✅ Zweryfikowano urządzenie:

**Model:** {st.session_state.current_model}
**Status gwarancji:** {warranty}

Proszę opisać problem z urządzeniem."""
    else:
        return f"""### ❌ Nie znaleziono urządzenia

{result['message']}

Proszę sprawdzić i spróbować ponownie."""

def handle_issue_analysis(message: str, ai_helper: AIHelper, knowledge_base: KnowledgeBase) -> str:
    """Obsługuje analizę problemu"""
    try:
        # Get device model from context
        model = st.session_state.context.verified_device.get('model', 'unknown')
        
        # Check if the question is on-topic
        topic_check = ai_helper.is_on_topic(message)
        if not topic_check.get("is_on_topic", True):
            # Jeśli pytanie nie jest związane z urządzeniami, zwróć odpowiednią odpowiedź
            logger.warning(f"Detected off-topic question: {message}")
            return topic_check.get("response", "Przepraszam, mogę odpowiadać tylko na pytania związane z urządzeniami Vet-Eye.")
        
        # Jeśli opis problemu jest bardzo krótki (mniej niż 5 słów), poproś o więcej szczegółów
        words = [w for w in message.split() if len(w) > 1]  # Ignoruj jednoliterowe słowa
        if len(words) < 3 and len(message) < 20:
            return """Dziękuję za zgłoszenie problemu. Aby lepiej Ci pomóc, potrzebuję nieco więcej szczegółów.

Czy mógłbyś opisać dokładniej, na czym polega problem z urządzeniem? Na przykład:
- Jakie objawy zauważyłeś?
- Kiedy problem się pojawił?
- Czy występuje w konkretnych sytuacjach?

Im więcej szczegółów podasz, tym lepiej będę mógł zdiagnozować problem."""
        
        # Get solutions from knowledge base
        solutions, _ = knowledge_base.find_solution(model, message)
        logger.info(f"Found {len(solutions)} potential solutions")
        
        # Analyze problem using AI
        response = ai_helper.analyze_problem_with_knowledge(
            device_model=model,
            issue_description=message,
            solutions=solutions
        )
        
        # Set issue description in context
        st.session_state.context.issue_description = message
        
        # Attempt state transition
        if set_state(ConversationState.CHECK_RESOLUTION):
            return f"""{response}

**Czy powyższe instrukcje pomogły rozwiązać Twój problem? (tak/nie)**"""
        else:
            return "Przepraszam, wystąpił błąd podczas analizy problemu. Spróbuj ponownie."
            
    except Exception as e:
        logger.error(f"Error in handle_issue_analysis: {str(e)}", exc_info=True)
        return f"Przepraszam, wystąpił błąd podczas analizy problemu: {str(e)}"

def handle_check_resolution(message: str) -> str:
    """Obsługuje sprawdzenie, czy rozwiązanie pomogło"""
    # Najpierw sprawdź czy to jednoznaczne tak lub nie
    if message.lower() in ['tak', 't', 'yes', 'y']:
        set_state(ConversationState.END)
        return "Cieszę się, że udało się rozwiązać problem! Czy mogę jeszcze w czymś pomóc?"
    
    # Sprawdź czy to jednoznaczne nie lub zawiera informacje wskazujące na brak rozwiązania problemu
    elif message.lower() in ['nie', 'n', 'no'] or any(phrase in message.lower() for phrase in ['nadal', 'wciąż', 'dalej', 'nie pomogło', 'nie działa']):
        # Zapisz dodatkowe informacje od użytkownika w kontekście
        if message.lower() not in ['nie', 'n', 'no']:
            st.session_state.context.additional_info = st.session_state.context.additional_info + "\n" + message if hasattr(st.session_state.context, 'additional_info') else message
        
        # Wprowadź dodatkowy etap pogłębionej diagnostyki
        st.session_state.context.attempts = st.session_state.context.attempts + 1 if hasattr(st.session_state.context, 'attempts') else 1
        
        # Pobierz informacje o problemie
        issue_description = st.session_state.context.issue_description.lower() if hasattr(st.session_state.context, 'issue_description') else ""
        
        # Dostosuj pytania diagnostyczne w zależności od rodzaju problemu
        if st.session_state.context.attempts <= 2:
            if st.session_state.context.attempts == 1:
                # Wybierz pytania dostosowane do rodzaju problemu
                if "zdjęcia" in issue_description or "obraz" in issue_description or "jakość obrazu" in issue_description:
                    return ("Rozumiem, że problem z jakością obrazu nadal występuje. Spróbujmy bardziej szczegółowej diagnozy:\n\n"
                           "1. Kiedy ostatnio czyszczona była głowica urządzenia?\n"
                           "2. Czy problem występuje podczas wszystkich badań, czy tylko w określonych warunkach?\n"
                           "3. Czy próbowano różnych ustawień jasności, kontrastu i ostrości?\n"
                           "4. Czy problem pojawił się nagle, czy jakość pogarszała się stopniowo?\n\n"
                           "Odpowiedzi na te pytania pomogą mi lepiej zrozumieć problem.")
                elif "restart" in issue_description or "wyłącza" in issue_description or "zawiesza" in issue_description:
                    return ("Rozumiem, że problem z restartowaniem się nadal występuje. Spróbujmy bardziej szczegółowej diagnozy:\n\n"
                           "1. Czy urządzenie restartuje się w określonych momentach, np. podczas wykonywania konkretnych operacji?\n"
                           "2. Czy na ekranie pojawiają się jakiekolwiek komunikaty błędów przed wyłączeniem?\n"
                           "3. Czy problem nasila się, gdy urządzenie jest używane przez dłuższy czas?\n"
                           "4. Czy próbowano podłączyć urządzenie do innego źródła zasilania?\n\n"
                           "Te informacje pomogą mi lepiej zrozumieć charakter problemu.")
                elif "gorące" in issue_description or "temperatura" in issue_description or "przegrzewa" in issue_description:
                    return ("Rozumiem, że problem z przegrzewaniem się nadal występuje. Spróbujmy bardziej szczegółowej diagnozy:\n\n"
                           "1. Jak długo urządzenie pozostaje włączone, zanim staje się gorące?\n"
                           "2. Czy urządzenie stoi na płaskiej powierzchni z dobrą wentylacją?\n"
                           "3. Czy zauważyłeś jakiekolwiek zmiany w wydajności urządzenia w trakcie pracy?\n"
                           "4. Czy słychać pracę wentylatorów wewnątrz urządzenia?\n\n"
                           "Te szczegóły pomogą mi lepiej zrozumieć problem z przegrzewaniem.")
                elif "nie włącza" in issue_description or "nie uruchamia" in issue_description:
                    return ("Rozumiem, że urządzenie nadal nie chce się włączyć. Spróbujmy bardziej szczegółowej diagnozy:\n\n"
                           "1. Czy na urządzeniu widać jakiekolwiek oznaki aktywności (diody, dźwięki)?\n"
                           "2. Czy próbowano podłączyć urządzenie do innego gniazdka?\n"
                           "3. Czy kabel zasilający jest w dobrym stanie i dobrze podłączony?\n"
                           "4. Czy wystąpiły jakiekolwiek incydenty (upadek, zalanie) przed problemem?\n\n"
                           "Te informacje będą kluczowe w dalszej diagnostyce.")
                else:
                    # Ogólne pytania dla innych problemów
                    return ("Rozumiem, że pierwsze rozwiązanie nie pomogło. Spróbujmy bardziej szczegółowej diagnozy:\n\n"
                           "1. Kiedy dokładnie pojawił się problem i jak często występuje?\n"
                           "2. Czy problem występuje w określonych warunkach lub podczas wykonywania konkretnych zadań?\n"
                           "3. Czy przed wystąpieniem problemu urządzenie działało normalnie, czy zauważyłeś jakieś nietypowe zachowania?\n"
                           "4. Czy wykonałeś już jakieś próby naprawy na własną rękę?\n\n"
                           "Te dodatkowe informacje pomogą mi lepiej zrozumieć charakter problemu.")
            else:
                # Druga próba - propozycje konkretnych rozwiązań w zależności od rodzaju problemu
                if "zdjęcia" in issue_description or "obraz" in issue_description or "jakość obrazu" in issue_description:
                    return ("Dziękuję za dodatkowe informacje. Spróbujmy jeszcze jednego rozwiązania dla poprawy jakości obrazu:\n\n"
                           "1. Wykonaj reset do ustawień fabrycznych poprzez menu Ustawienia > System > Resetowanie urządzenia.\n"
                           "2. Dokładnie wyczyść głowicę używając specjalnego preparatu do czyszczenia sond (nie używaj alkoholu ani środków ściernych).\n"
                           "3. Sprawdź połączenia kablowe między głowicą a jednostką główną.\n"
                           "4. Uruchom urządzenie ponownie i wykonaj test kalibracyjny dostępny w menu Diagnostyka.\n\n"
                           "Czy po wykonaniu tych czynności zauważyłeś poprawę jakości obrazu?")
                elif "restart" in issue_description or "wyłącza" in issue_description or "zawiesza" in issue_description:
                    return ("Dziękuję za dodatkowe informacje. Spróbujmy bardziej zaawansowanego rozwiązania problemu z restartami:\n\n"
                           "1. Zaktualizuj oprogramowanie urządzenia do najnowszej wersji (dostępne na stronie producenta).\n"
                           "2. Wykonaj przywracanie ustawień fabrycznych z menu Ustawienia > System > Reset fabryczny.\n"
                           "3. Sprawdź, czy problem występuje na zasilaniu bateryjnym, jeśli urządzenie posiada baterię.\n"
                           "4. Sprawdź, czy urządzenie nie jest podatne na zakłócenia elektromagnetyczne - oddal inne urządzenia elektroniczne.\n\n"
                           "Czy którekolwiek z tych rozwiązań przyniosło poprawę?")
                else:
                    # Ogólne rozwiązania dla pozostałych problemów
                    return ("Dziękuję za dodatkowe informacje. Spróbujmy jeszcze jednego rozwiązania:\n\n"
                           "1. Odłącz urządzenie od zasilania na co najmniej 5 minut.\n"
                           "2. Sprawdź, czy złącza i przewody są dobrze podłączone i nie są uszkodzone.\n"
                           "3. Jeśli urządzenie ma przycisk reset (często mały otwór, który można nacisnąć spinaczem), użyj go.\n"
                           "4. Podłącz urządzenie ponownie i spróbuj je włączyć.\n\n"
                           "Czy po wykonaniu tych kroków zauważyłeś jakąkolwiek poprawę?")
        else:
            # Po wyczerpaniu prób diagnostycznych, zaproponuj wizytę serwisową
            set_state(ConversationState.ISSUE_REPORTED)
            return ("Bardzo mi przykro, że nie udało się rozwiązać problemu zdalnie. W takim przypadku najlepszym rozwiązaniem będzie wizyta serwisowa. "
                   "Serwisant będzie mógł bezpośrednio zbadać urządzenie i zdiagnozować przyczynę problemu. Muszę poinformować, że wizyta serwisowa może okazać się płatna nawet w przypadku gdy urządzenie jest objęte gwarancją. Wszystko zależy od przyczyny problemu.\n\n"
                   "Czy chciałbyś umówić wizytę serwisową? (tak/nie)")
    
    # Jeśli odpowiedź nie jest jednoznaczna, ale zawiera informacje diagnostyczne, potraktuj jak dodatkowe dane
    else:
        # Zapisz informacje od użytkownika w kontekście
        st.session_state.context.additional_info = st.session_state.context.additional_info + "\n" + message if hasattr(st.session_state.context, 'additional_info') else message
        
        # Zamiast pytać ponownie o skuteczność, zaproponuj nowe rozwiązanie
        issue_description = st.session_state.context.issue_description.lower() if hasattr(st.session_state.context, 'issue_description') else ""
        
        if "zdjęcia" in issue_description or "obraz" in issue_description or "jakość obrazu" in issue_description:
            return ("Dziękuję za dodatkowe informacje. Na podstawie dostarczonych szczegółów, proponuję następujące rozwiązanie problemu z jakością obrazu:\n\n"
                   "1. Wykonaj pełną kalibrację urządzenia z menu serwisowego (dostęp: przytrzymaj przycisk zasilania + przycisk funkcyjny F2 podczas włączania).\n"
                   "2. Sprawdź, czy wszystkie filtry obrazu są prawidłowo skonfigurowane.\n"
                   "3. Spróbuj przełączyć urządzenie w tryb diagnostyczny, który oferuje lepszą jakość obrazu do celów testowych.\n\n"
                   "Czy udało Ci się wykonać te czynności i czy przyniosły one poprawę?")
        elif "restart" in issue_description or "wyłącza" in issue_description or "zawiesza" in issue_description:
            return ("Dziękuję za dodatkowe informacje. Na podstawie dostarczonych szczegółów, proponuję następujące rozwiązanie problemu z restartami:\n\n"
                   "1. Wykonaj diagnostykę sprzętową z menu rozruchowego (dostęp przez przytrzymanie przycisku funkcyjnego podczas włączania).\n"
                   "2. Sprawdź logi systemowe, które mogą wskazywać na przyczynę problemów.\n"
                   "3. Jeśli możliwe, podłącz urządzenie do zasilania przez stabilizator napięcia, aby wyeliminować problemy z zasilaniem.\n\n"
                   "Czy udało Ci się wykonać te czynności i czy przyniosły one poprawę?")
        else:
            # Ogólne rozwiązania dla pozostałych problemów
            return ("Dziękuję za dodatkowe informacje. Na ich podstawie proponuję następujące rozwiązanie:\n\n"
                   "1. Wykonaj pełną diagnostykę urządzenia z menu serwisowego.\n"
                   "2. Sprawdź, czy są dostępne aktualizacje oprogramowania dla Twojego modelu urządzenia.\n"
                   "3. Wykonaj procedurę czyszczenia pamięci podręcznej urządzenia (cache).\n\n"
                   "Czy udało Ci się wykonać te czynności i czy przyniosły one poprawę?")

def handle_issue_reported(message: str) -> str:
    """Obsługuje zgłoszenie problemu"""
    if message.lower() in ['tak', 't', 'yes', 'y']:
        set_state(ConversationState.SERVICE_SCHEDULING)
        return "Dziękuję. Aby umówić wizytę serwisową, potrzebuję sprawdzić dostępne terminy. Czy chcesz zobaczyć listę dostępnych terminów? (tak/nie)"
    elif message.lower() in ['nie', 'n', 'no']:
        set_state(ConversationState.END)
        return "Rozumiem. Jeśli zmienisz zdanie lub problem będzie się powtarzał, proszę o ponowny kontakt. Czy mogę jeszcze w czymś pomóc?"
    else:
        return "Przepraszam, nie zrozumiałem odpowiedzi. Czy chcesz umówić wizytę serwisową? (tak/nie)"

def handle_service_scheduling(message: str, calendar_client: CalendarClient) -> str:
    """Obsługuje umawianie wizyty serwisowej"""
    if message.lower() in ['tak', 't', 'yes', 'y']:
        if st.session_state.showing_slots:
            return "Proszę wybrać termin z listy powyżej wpisując numer (np. 1, 2, 3...)"
        else:
            try:
                # Generuj dostępne terminy na najbliższe dni (np. 10 dni roboczych)
                start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                available_slots = []
                formatted_slots = []
                
                # Pobierz już zajęte terminy z Airtable
                occupied_slots = get_occupied_slots()
                
                # Generuj sloty czasowe na 10 dni do przodu, wyłączając zajęte terminy
                for day in range(10):
                    current_date = start_date + timedelta(days=day)
                    # Pomiń weekendy
                    if current_date.weekday() >= 5:  # 5=sobota, 6=niedziela
                        continue
                    
                    # Dla każdego dnia generuj 10 slotów od 8:00 do 17:00
                    for hour in range(8, 18):
                        slot_time = current_date.replace(hour=hour, minute=0, second=0, microsecond=0)
                        
                        # Sprawdź czy termin jest już zajęty
                        if not is_slot_occupied(slot_time, occupied_slots):
                            available_slots.append(slot_time)
                            # Format: Poniedziałek, 01.01.2023 09:00
                            day_name = slot_time.strftime("%A").capitalize()
                            day_name_pl = translate_day_name(day_name)
                            formatted_slot = f"{day_name_pl}, {slot_time.strftime('%d.%m.%Y %H:%M')}"
                            formatted_slots.append(formatted_slot)
                
                if not available_slots:
                    return "Przepraszam, nie znaleziono żadnych dostępnych terminów w najbliższym czasie. Proszę spróbować później."
                
                # Zapisz dostępne terminy w sesji
                st.session_state.available_slots = available_slots
                st.session_state.formatted_slots = formatted_slots
                st.session_state.showing_slots = True
                
                # Wyświetl dostępne terminy
                slots_text = "Dostępne terminy:\n\n"
                for i, slot in enumerate(formatted_slots):
                    slots_text += f"{i+1}. {slot}\n"
                
                return slots_text + "Proszę wybrać termin wpisując jego numer (np. 1, 2, 3...) lub wpisać 'inne' jeśli żaden termin nie odpowiada."
                
            except Exception as e:
                logger.error(f"Error generating time slots: {str(e)}", exc_info=True)
                return f"Przepraszam, wystąpił błąd podczas generowania terminów: {str(e)}"
    
    elif message.lower() in ['nie', 'n', 'no']:
        return "Rozumiem. Jeśli zmienisz zdanie, możesz skontaktować się z nami telefonicznie lub przez email, aby umówić wizytę serwisową."
    
    elif st.session_state.showing_slots:
        try:
            # Obsługa wyboru terminu
            if message.lower() == 'inne':
                return "Rozumiem, że żaden z proponowanych terminów nie odpowiada. Proszę o kontakt telefoniczny z serwisem w celu ustalenia dogodnego terminu."
            
            try:
                # Próba parsowania numeru terminu
                slot_number = int(message)
                
                if 1 <= slot_number <= len(st.session_state.available_slots):
                    # Wybrano poprawny termin
                    selected_slot = st.session_state.available_slots[slot_number - 1]
                    st.session_state.selected_slot = selected_slot
                    
                    # Przejdź do zbierania danych klienta
                    set_state(ConversationState.COLLECT_CUSTOMER_INFO)
                    return "Termin został wybrany. Teraz potrzebuję kilku informacji kontaktowych. Proszę podać imię i nazwisko osoby zgłaszającej problem:"
                else:
                    return f"Proszę wybrać numer z zakresu 1-{len(st.session_state.available_slots)}."
                    
            except ValueError:
                return "Proszę wybrać numer odpowiadający terminowi lub wpisać 'inne'."
                
        except Exception as e:
            logger.error(f"Error processing slot selection: {str(e)}", exc_info=True)
            return f"Przepraszam, wystąpił błąd podczas przetwarzania wyboru: {str(e)}"
    else:
        return "Czy chcesz zobaczyć listę dostępnych terminów? (tak/nie)"

# Funkcje pomocnicze do sprawdzania zajętości terminów
def get_occupied_slots():
    """Pobiera już zajęte terminy z Airtable"""
    try:
        # Utwórz instancję dla tabeli Calendar
        base_id = os.getenv('AIRTABLE_BASE_ID')
        api_key = os.getenv('AIRTABLE_API_KEY')
        calendar_table = Airtable(base_id, 'Calendar', api_key)
        
        # Pobierz wszystkie rekordy
        records = calendar_table.get_all()
        
        # Wyodrębnij daty i przekształć je na obiekty datetime
        occupied_slots = []
        for record in records:
            date_str = record['fields'].get('date_time')
            if date_str:
                try:
                    # Konwertowanie z ISO format string (np. "2023-01-01T09:00:00Z")
                    date_obj = parse(date_str)
                    # Ustaw strefę czasową na Europe/Warsaw
                    if date_obj.tzinfo is None:
                        date_obj = pytz.utc.localize(date_obj)
                    # Konwertuj do strefy czasowej Europe/Warsaw
                    local_tz = pytz.timezone('Europe/Warsaw')
                    local_date = date_obj.astimezone(local_tz)
                    occupied_slots.append(local_date)
                except Exception as e:
                    logger.error(f"Error parsing date {date_str}: {str(e)}")
        
        return occupied_slots
    except Exception as e:
        logger.error(f"Error getting occupied slots: {str(e)}")
        return []

def is_slot_occupied(slot_time, occupied_slots):
    """Sprawdza czy dany termin jest już zajęty"""
    for occupied in occupied_slots:
        # Porównaj datę i godzinę - ignoruj strefy czasowe
        if (slot_time.year == occupied.year and 
            slot_time.month == occupied.month and 
            slot_time.day == occupied.day and 
            slot_time.hour == occupied.hour):
            return True
    return False

def translate_day_name(day_name):
    """Tłumaczy nazwy dni tygodnia na polski"""
    translations = {
        "Monday": "Poniedziałek",
        "Tuesday": "Wtorek",
        "Wednesday": "Środa",
        "Thursday": "Czwartek",
        "Friday": "Piątek",
        "Saturday": "Sobota",
        "Sunday": "Niedziela"
    }
    return translations.get(day_name, day_name)

def handle_custom_slot_request(message: str, calendar_client: CalendarClient) -> str:
    """Obsługuje żądanie niestandardowego terminu"""
    # Parsowanie preferowanego terminu
    preferred_slot = calendar_client.parse_preferred_time(message)
    
    if preferred_slot:
        # Sprawdzenie dostępności +/- 2 godziny od preferowanego terminu
        available_slots = calendar_client.get_available_slots_around(preferred_slot, hours_range=2)
        if available_slots:
            st.session_state.available_slots = available_slots
            st.session_state.formatted_slots = [calendar_client.format_single_slot(slot) for slot in available_slots]
            
            response = "Znalazłem następujące dostępne terminy blisko Twojej preferencji:\n"
            for i, slot in enumerate(st.session_state.formatted_slots, 1):
                response += f"{i}. {slot}\n"
            response += "\n\nProszę wybrać termin wpisując jego numer:"
            
            return response
        else:
            return ("Niestety, serwisanci nie mają wolnych terminów w podanym czasie. "
                  "Proszę podać inny preferowany termin lub wpisać 'pokaż wszystkie' aby zobaczyć wszystkie dostępne terminy:")
    else:
        return "Przepraszam, nie rozpoznaję formatu daty. Proszę podać datę w formacie 'DD.MM HH:MM' lub 'dzień tygodnia HH:MM':"

def handle_collect_customer_info(message: str) -> str:
    """Obsługuje zbieranie danych klienta"""
    data_step = st.session_state.context.data_collection_step
    
    if data_step == "name":
        st.session_state.client_name = message
        st.session_state.context.customer_info['name'] = message
        st.session_state.context.data_collection_step = "phone"
        return "Dziękuję. Proszę podać numer telefonu kontaktowego:"
    
    elif data_step == "phone":
        if len(message.replace(' ', '').replace('-', '')) >= 9:  # Podstawowa walidacja numeru
            st.session_state.client_phone = message
            st.session_state.context.customer_info['phone'] = message
            st.session_state.context.data_collection_step = "email"
            return "Dziękuję. Proszę podać adres email:"
        else:
            return "Nieprawidłowy numer telefonu. Proszę podać prawidłowy numer:"
    
    elif data_step == "email":
        if '@' in message and '.' in message:  # Podstawowa walidacja emaila
            st.session_state.client_email = message
            st.session_state.context.customer_info['email'] = message
            st.session_state.context.data_collection_step = "address"
            return "Dziękuję. Proszę podać adres dla serwisantów:"
        else:
            return "Nieprawidłowy adres email. Proszę podać prawidłowy adres:"
    
    elif data_step == "address":
        st.session_state.client_address = message
        st.session_state.context.customer_info['address'] = message
        
        # Formatuj datę do wyświetlenia w przyjaznym formacie
        formatted_date = st.session_state.selected_slot.strftime('%d.%m.%Y %H:%M')
        
        # Przejdź do potwierdzenia
        set_state(ConversationState.CONFIRMATION)
        return f"""Proszę potwierdzić dane:
        
Imię i nazwisko: {st.session_state.client_name}
Telefon: {st.session_state.client_phone}
Email: {st.session_state.client_email}
Adres: {st.session_state.client_address}
Termin: {formatted_date}

Czy wszystkie dane są prawidłowe? (tak/nie)"""
    
    return "Przepraszam, wystąpił błąd przy zbieraniu danych. Spróbujmy jeszcze raz. Proszę podać imię i nazwisko:"

def handle_confirmation(message: str, airtable_client: AirtableClient, calendar_client: CalendarClient) -> str:
    """Obsługuje potwierdzenie danych i dodaje wizytę serwisową"""
    if message.lower() in ['tak', 't', 'yes', 'y']:
        try:
            # Zbieramy dane bezpośrednio z session_state
            date_time = st.session_state.get('selected_slot')
            customer_name = st.session_state.get('client_name', '')
            customer_email = st.session_state.get('client_email', '')
            customer_phone = st.session_state.get('client_phone', '')
            customer_address = st.session_state.get('client_address', '')
            
            # Pobierz model bezpośrednio z kontekstu konwersacji
            device_info = st.session_state.context.verified_device_info if hasattr(st.session_state.context, 'verified_device_info') else "Nieznany model"
            
            # Jeśli nie ma informacji o modelu w kontekście, spróbuj uzyskać z wiadomości
            if device_info == "Nieznany model" and len(st.session_state.messages) > 3:
                for msg in st.session_state.messages:
                    if msg["role"] == "assistant" and "Zweryfikowano urządzenie:" in msg["content"]:
                        # Wyciągnij model z wiadomości asystenta
                        content = msg["content"]
                        model_start = content.find("Model:") + 7 if "Model:" in content else -1
                        if model_start > 0:
                            model_end = content.find("Status", model_start)
                            if model_end > 0:
                                device_info = content[model_start:model_end].strip()
                            else:
                                model_end = content.find("\n", model_start)
                                if model_end > 0:
                                    device_info = content[model_start:model_end].strip()
                                else:
                                    device_info = content[model_start:].strip()
                        break
                
            # Uzyskaj tylko nazwę modelu (bez informacji o gwarancji)
            device_model = device_info.split("Status")[0].strip() if "Status" in device_info else device_info
            
            # Pobierz numer seryjny i opis problemu
            device_sn = st.session_state.context.verified_device.get('serial_number', '')
            issue_description = st.session_state.context.issue_description
            
            # Utwórz opis dla wizyty (dla kalendarza Google)
            description = f"""
            Model: {device_model}
            SN: {device_sn}
            Problem: {issue_description}
            
            Klient:
            {customer_name}
            Tel: {customer_phone}
            Email: {customer_email}
            Adres: {customer_address}
            """
            
            # Format daty do Airtable
            if hasattr(date_time, 'isoformat'):
                # Jeśli timezone nie jest ustawiony, ustaw na Europe/Warsaw
                if date_time.tzinfo is None:
                    local_tz = pytz.timezone('Europe/Warsaw')
                    date_time = local_tz.localize(date_time)
                
                # Konwertuj do ISO string z timezone Europe/Warsaw
                formatted_date = date_time.isoformat()
            else:
                # Jeśli to już string, użyj bezpośrednio
                formatted_date = date_time
            
            # Przygotuj dane do zapisania w tabeli Calendar
            calendar_record = {
                'date_time': formatted_date,
                'device_model': device_model,  # Używamy modelu z wiadomości
                'description': issue_description,  # Tylko opis problemu
                'customer_address': customer_address,
                'customer_phone': customer_phone,
                'customer_email': customer_email,
                'customer_name': customer_name  # Imię i nazwisko klienta
            }
            
            # Utwórz nową instancję Airtable dla tabeli Calendar
            # Pobierz wartości z AirtableClient
            base_id = os.getenv('AIRTABLE_BASE_ID')
            api_key = os.getenv('AIRTABLE_API_KEY')
            
            # Utwórz instancję dla tabeli Calendar
            calendar_table = Airtable(base_id, 'Calendar', api_key)
            
            # Dodaj rekord
            calendar_result = calendar_table.insert(calendar_record)
            
            # Dodanie wydarzenia do kalendarza
            event = calendar_client.add_service_event(
                f"Wizyta serwisowa - {customer_name}",  # summary
                description,                            # description
                date_time,                              # date_time
                customer_email=customer_email           # dodatkowy argument
            )
            
            # Weryfikacja czy event to krotka
            event_id = ''
            event_link = ''
            
            if isinstance(event, dict):
                event_id = event.get('id', '')
                event_link = event.get('link', '')
            elif isinstance(event, tuple) and len(event) >= 2:
                event_id = event[0] if event[0] else ''
                event_link = event[1] if len(event) > 1 and event[1] else ''
            
            # Zapisz dane w kontekście
            st.session_state.context.service_event = {
                'id': event_id,
                'link': event_link,
                'datetime': date_time,
                'customer_name': customer_name
            }
            
            # Użyj istniejącego stanu END
            set_state(ConversationState.END)
            return "Dziękuję! Wizyta serwisowa została zaplanowana. Wkrótce otrzymasz potwierdzenie na podany adres email oraz telefon z działu serwisu w celu potwierdzenia terminu. Jeśli wizyta nie zostanie potwierdzona telefonicznie w ciągu 24 godzin, zostanie automatycznie anulowana. Będziemy kontaktować się z Tobą na wskazany przez Ciebie numer telefonu w ciągu 24 godzin."
            
        except Exception as e:
            logger.error(f"Error scheduling service: {str(e)}", exc_info=True)
            return f"Przepraszam, wystąpił błąd podczas dodawania wizyty: {str(e)}"
    elif message.lower() in ['nie', 'n', 'no']:
        set_state(ConversationState.COLLECT_CUSTOMER_INFO)
        return "Rozumiem. Proszę podać poprawne dane."
    else:
        return "Przepraszam, nie zrozumiałem odpowiedzi. Czy dane są poprawne? (tak/nie)"

def handle_end(message: str) -> str:
    """Obsługuje zakończenie konwersacji"""
    if message.lower() in ['tak', 't', 'yes', 'y']:
        # Resetuj kontekst i przejdź do początku
        st.session_state.context = ConversationContext()
        return "W czym jeszcze mogę pomóc?"
    else:
        return "Dziękuję za skorzystanie z asystenta VetEye. Jeśli będziesz potrzebować pomocy, jestem tutaj do dyspozycji. Do widzenia! 👋"

def main():
    """Główna funkcja aplikacji"""
    # Załaduj zmienne środowiskowe
    load_environment_variables()
    
    # Sprawdź, czy wszystkie wymagane zmienne środowiskowe są ustawione
    required_vars = ['AIRTABLE_API_KEY', 'AIRTABLE_BASE_ID', 'OPENAI_API_KEY']
    missing_vars = [var for var in required_vars if var not in os.environ or not os.environ[var]]
    
    if missing_vars:
        st.error("⚠️ Brakujące zmienne środowiskowe!")
        st.write("Aplikacja wymaga następujących zmiennych środowiskowych:")
        for var in missing_vars:
            st.write(f"- {var}")
        
        st.write("### Jak skonfigurować zmienne środowiskowe:")
        st.write("""
        1. W Streamlit Cloud:
           - Przejdź do ustawień aplikacji
           - Znajdź sekcję "Secrets" lub "Environment Variables"
           - Dodaj wymagane zmienne
        
        2. Lokalnie:
           - Utwórz plik `.env` w głównym katalogu projektu
           - Dodaj wymagane zmienne w formacie `NAZWA_ZMIENNEJ=wartość`
        """)
        return
    
    # Inicjalizacja komponentów aplikacji
    try:
        airtable_client, calendar_client, knowledge_base, ai_helper = initialize_components()
        
        # Sprawdź, czy komponenty zostały poprawnie zainicjalizowane
        if airtable_client is None or calendar_client is None or knowledge_base is None or ai_helper is None:
            st.error("Nie udało się zainicjalizować wszystkich komponentów aplikacji. Sprawdź logi, aby uzyskać więcej informacji.")
            return
            
        # Inicjalizacja stanu sesji
        initialize_session_state()
        
        # Wyświetlenie historii czatu
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # Obsługa inputu użytkownika
        if prompt := st.chat_input("Wpisz swoją odpowiedź..."):
            # Dodaj wiadomość użytkownika do historii
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Dodaj wiadomość do kontekstu
            st.session_state.context.add_message({"role": "user", "content": prompt})
            
            # Generuj odpowiedź asystenta
            with st.chat_message("assistant"):
                try:
                    # Pobierz aktualny stan konwersacji
                    current_state = st.session_state.context.current_state
                    logger.info(f"Processing message in state: {current_state.value}")
                    
                    # Obsługa odpowiednich stanów
                    if current_state == ConversationState.WELCOME:
                        response = handle_welcome(prompt)
                    
                    elif current_state == ConversationState.DEVICE_VERIFICATION:
                        response = handle_device_verification(prompt, airtable_client)
                    
                    elif current_state == ConversationState.ISSUE_ANALYSIS:
                        response = handle_issue_analysis(prompt, ai_helper, knowledge_base)
                    
                    elif current_state == ConversationState.CHECK_RESOLUTION:
                        response = handle_check_resolution(prompt)
                    
                    elif current_state == ConversationState.ISSUE_REPORTED:
                        response = handle_issue_reported(prompt)
                    
                    elif current_state == ConversationState.SERVICE_SCHEDULING:
                        response = handle_service_scheduling(prompt, calendar_client)
                    
                    elif current_state == ConversationState.COLLECT_CUSTOMER_INFO:
                        response = handle_collect_customer_info(prompt)
                    
                    elif current_state == ConversationState.CONFIRMATION:
                        response = handle_confirmation(prompt, airtable_client, calendar_client)
                    
                    elif current_state == ConversationState.END:
                        response = handle_end(prompt)
                    
                    else:
                        logger.error(f"Unknown state: {current_state.value}")
                        response = "Przepraszam, wystąpił błąd. Spróbuj ponownie lub skontaktuj się z serwisem."
                    
                    # Dodaj wiadomość asystenta do historii
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    st.session_state.context.add_message({"role": "assistant", "content": response})
                    
                    # Wyświetl odpowiedź
                    st.markdown(response)
                    
                except Exception as e:
                    logger.error(f"Error processing message: {str(e)}", exc_info=True)
                    response = f"Wystąpił błąd: {str(e)}"
                    
                    # Dodaj informację o błędzie do historii
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    st.session_state.context.add_message({"role": "assistant", "content": response})
                    
                    # Wyświetl informację o błędzie
                    st.markdown(response)
                
                # Usuwam tę linię, która powoduje podwójne wyświetlanie odpowiedzi
                # st.markdown(response)
    
    except Exception as e:
        logger.error(f"Error in main function: {str(e)}", exc_info=True)
        st.error(f"Wystąpił błąd w aplikacji: {str(e)}")
        return

if __name__ == "__main__":
    main()