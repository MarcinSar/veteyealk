from enum import Enum
from typing import Dict, Optional, List, Set
from datetime import datetime
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

class ConversationState(Enum):
    WELCOME = "welcome"                           # Powitanie użytkownika
    GDPR = "gdpr"                                 # Zgoda RODO
    DEVICE_VERIFICATION = "device_verification"   # Weryfikacja urządzenia
    ISSUE_ANALYSIS = "issue_analysis"             # Analiza problemu
    CHECK_RESOLUTION = "check_resolution"         # Sprawdzenie czy problem rozwiązany
    ISSUE_REPORTED = "issue_reported"             # Zgłoszenie problemu
    SERVICE_SCHEDULING = "service_scheduling"     # Umawianie wizyty
    COLLECT_CUSTOMER_INFO = "collect_customer_info"  # Zbieranie danych klienta
    CONFIRMATION = "confirmation"                 # Potwierdzenie
    END = "end"                                   # Zakończenie

# Mapa dozwolonych przejść między stanami
VALID_STATE_TRANSITIONS = {
    ConversationState.WELCOME: {ConversationState.DEVICE_VERIFICATION},
    ConversationState.GDPR: {ConversationState.DEVICE_VERIFICATION, ConversationState.END},
    ConversationState.DEVICE_VERIFICATION: {ConversationState.ISSUE_ANALYSIS, ConversationState.GDPR},
    ConversationState.ISSUE_ANALYSIS: {ConversationState.CHECK_RESOLUTION, ConversationState.ISSUE_REPORTED},
    ConversationState.CHECK_RESOLUTION: {ConversationState.END, ConversationState.ISSUE_REPORTED},
    ConversationState.ISSUE_REPORTED: {ConversationState.SERVICE_SCHEDULING, ConversationState.END},
    ConversationState.SERVICE_SCHEDULING: {ConversationState.COLLECT_CUSTOMER_INFO, ConversationState.END},
    ConversationState.COLLECT_CUSTOMER_INFO: {ConversationState.CONFIRMATION, ConversationState.SERVICE_SCHEDULING},
    ConversationState.CONFIRMATION: {ConversationState.END, ConversationState.SERVICE_SCHEDULING},
    ConversationState.END: {ConversationState.WELCOME}  # Możliwość rozpoczęcia nowej konwersacji
}

@dataclass
class ConversationContext:
    """Klasa przechowująca kontekst konwersacji"""
    _current_state: ConversationState = field(default=ConversationState.WELCOME)
    state_history: List[str] = field(default_factory=list)
    messages_history: List[Dict] = field(default_factory=list)
    current_conversation_id: Optional[str] = None
    last_interaction: datetime = field(default_factory=datetime.now)
    
    # Dane urządzenia i klienta
    verified_device: Optional[Dict] = None
    customer_info: Dict = field(default_factory=dict)
    
    # Dane zgłoszenia
    issue_description: str = ""
    service_request: Dict = field(default_factory=dict)
    
    # Dane kalendarza
    available_slots: List[datetime] = field(default_factory=list)
    selected_slot: Optional[datetime] = None
    
    # Flagi i inne dane
    gdpr_consent: bool = False
    data_collection_step: str = "name"  # Jeden z: name, phone, email, address
    
    def add_message(self, message: Dict) -> None:
        """Dodaje wiadomość do historii"""
        self.messages_history.append(message)
        self.last_interaction = datetime.now()
    
    @property
    def current_state(self) -> ConversationState:
        """Zwraca aktualny stan konwersacji"""
        return self._current_state
    
    @current_state.setter
    def current_state(self, new_state: ConversationState) -> None:
        """Ustawia nowy stan konwersacji i zapisuje historię"""
        if new_state != self._current_state:
            self.state_history.append(self._current_state.value)
            self._current_state = new_state
            logger.info(f"State changed to: {new_state.value}")
    
    def is_valid_transition(self, new_state: ConversationState) -> bool:
        """Sprawdza czy przejście do nowego stanu jest dozwolone"""
        return new_state in VALID_STATE_TRANSITIONS.get(self._current_state, set()) 