import logging
from typing import Dict, List, Optional, Any
import json
import os
import importlib
import sys

logger = logging.getLogger(__name__)

class AIHelper:
    def __init__(self, api_key):
        """Inicjalizacja pomocnika AI"""
        self.api_key = api_key
        self.default_model = "gpt-4o"  # Preferowany model
        
        # Próba inicjalizacji klienta w bezpieczny sposób, bez używania argumentu 'proxies'
        try:
            # Metoda 1: Użycie zmiennej środowiskowej (najbezpieczniejsza metoda)
            logger.info("Trying initialization method 1: Environment variable")
            os.environ["OPENAI_API_KEY"] = api_key
            
            # Sprawdź, czy mamy dostęp do nowego API OpenAI
            if self._is_new_openai_available():
                from openai import OpenAI
                self.client = OpenAI() # Bez jawnego przekazywania api_key - użyje zmiennej środowiskowej
                self.client_type = "new"
                logger.info("Successfully initialized OpenAI client with new API")
            else:
                # Starsza wersja OpenAI
                import openai
                openai.api_key = api_key
                self.client = openai
                self.client_type = "legacy"
                # Dostosowanie modelu do starszej wersji API
                self.default_model = "gpt-4o"
                logger.info("Successfully initialized OpenAI client with legacy API")
        except Exception as e:
            logger.error(f"Error initializing OpenAI client: {str(e)}")
            # Fallback - utworzenie pustego klienta i obsługa błędów w metodach
            self.client = None
            self.client_type = "none"
            logger.warning("Created empty client, API calls will return fallback responses")
    
    def _is_new_openai_available(self):
        """Sprawdza, czy nowa wersja API OpenAI jest dostępna"""
        try:
            # Próba importu klasy OpenAI
            spec = importlib.util.find_spec('openai')
            if spec is None:
                return False
                
            # Spróbuj zaimportować konkretną klasę
            from openai import OpenAI
            return True
        except (ImportError, AttributeError):
            return False
    
    def analyze_issue(self, issue_description: str) -> str:
        """
        Analizuje wstępny opis problemu i zadaje odpowiednie pytania
        
        Args:
            issue_description: Opis problemu od użytkownika
            
        Returns:
            str: Wygenerowana odpowiedź od AI
        """
        try:
            if self.client is None:
                raise Exception("No OpenAI client available")
                
            logger.debug(f"Analyzing issue: {issue_description[:100]}...")
            
            system_content = """Jesteś asystentem technicznym specjalizującym się w ultrasonografach weterynaryjnych firmy VetEye - odpowiadasz na pytania dotyczące sprzętu firmy VetEye a nie ogólnie sprzętu.
            Twoje odpowiedzi powinny być:
            1. Empatyczne i profesjonalne
            2. Zawierać podstawowe pytania diagnostyczne
            3. Skupiać się na wstępnej diagnozie problemu
            4. Pytać o kluczowe szczegóły aby zrozumieć problem
            5. Pytać czy informcje od Ciebie są pomocne i informować że jesteś do dyspozycji na bieżąco
            6. Nie odpowiadać na pytania poza tematem związanym ze sprzętem firmy VetEye!
            
            Odpowiedź powinna być ZWIĘZŁA i KONKRETNA."""
            
            user_content = f"Problem z urządzeniem: {issue_description}"
            
            if self.client_type == "new":
                # Nowa wersja API (1.0.0+)
                response = self.client.chat.completions.create(
                    model=self.default_model,
                    messages=[
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": user_content}
                    ],
                    temperature=0.3,
                    max_tokens=2000
                )
                result = response.choices[0].message.content
            elif self.client_type == "legacy":
                # Starsza wersja API (<1.0.0)
                response = self.client.ChatCompletion.create(
                    model=self.default_model,
                    messages=[
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": user_content}
                    ],
                    temperature=0.3,
                    max_tokens=2000
                )
                result = response.choices[0]['message']['content']
            else:
                raise Exception("Invalid client type")
            
            logger.debug(f"AI response generated: {result[:100]}...")
            return result
            
        except Exception as e:
            logger.error(f"Error in analyze_issue: {str(e)}", exc_info=True)
            return """Rozumiem zgłoszony problem. Aby pomóc w diagnozie, potrzebuję kilku dodatkowych informacji:

1. Kiedy problem wystąpił po raz pierwszy?
2. Czy pojawiają się jakieś komunikaty błędów?
3. Czy próbowano już jakichś rozwiązań?

Proszę o podanie tych szczegółów, żebym mógł lepiej zrozumieć sytuację."""
    
    def analyze_problem_with_knowledge(self, device_model: str, issue_description: str, solutions: List[Dict]) -> str:
        """
        Analyzes the problem using AI and knowledge base solutions
        
        Args:
            device_model: The device model
            issue_description: Description of the issue
            solutions: List of relevant solutions from knowledge base
            
        Returns:
            str: AI generated response with analysis and solution
        """
        try:
            if self.client is None:
                raise Exception("No OpenAI client available")
                
            # Przygotowanie kontekstu z rozwiązań
            solutions_context = self._format_solutions(solutions)
            
            prompt = f"""Analiza problemu z urządzeniem medycznym:

Model urządzenia: {device_model}
Zgłoszony problem: {issue_description}

Informacje z bazy wiedzy:
{solutions_context}

Na podstawie tych informacji i swojej wiedzy, stwórz odpowiedź zawierającą:
1. **Prawdopodobna przyczyna problemu**
2. **Rozwiązanie krok po kroku**
3. **Dodatkowe wskazówki**

Odpowiedź powinna być szczegółowa i profesjonalna, ale zrozumiała dla niespecjalisty - nie sugeruj kontaktowania się z producentem bo uzytkownik właśnie to robi - jesteś przedstawicielem producenta i autoryzowanego serwisu."""

            system_content = "Jesteś asystentem technicznym specjalizującym się w diagnostyce i rozwiązywaniu problemów z urządzeniami medycznymi."
            
            if self.client_type == "new":
                # Nowa wersja API (1.0.0+)
                response = self.client.chat.completions.create(
                    model=self.default_model,
                    messages=[
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.4,
                    max_tokens=2000
                )
                result = response.choices[0].message.content
            elif self.client_type == "legacy":
                # Starsza wersja API (<1.0.0)
                response = self.client.ChatCompletion.create(
                    model=self.default_model,
                    messages=[
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.4,
                    max_tokens=2000
                )
                result = response.choices[0]['message']['content']
            else:
                raise Exception("Invalid client type")
            
            logger.debug(f"AI solution analysis generated: {result[:100]}...")
            return result
        
        except Exception as e:
            logger.error(f"Error in analyze_problem_with_knowledge: {str(e)}", exc_info=True)
            return f"""## Analiza problemu

Na podstawie opisu problemu i dostępnych informacji, oto moja analiza:

1. **Prawdopodobna przyczyna problemu**:
   Trudno jednoznacznie określić przyczynę bez dodatkowych informacji. Problem może być związany z {device_model}.

2. **Rozwiązanie krok po kroku**:
   - Sprawdź, czy urządzenie jest prawidłowo podłączone
   - Upewnij się, że wszystkie komponenty działają prawidłowo
   - Zrestartuj urządzenie i sprawdź, czy problem ustąpił
   - Jeśli problem nadal występuje, skontaktuj się z serwisem

3. **Dodatkowe wskazówki**:
   Aby uzyskać dokładniejszą diagnozę, prosimy o podanie bardziej szczegółowych informacji na temat objawów problemu.

Czy potrzebujesz dodatkowej pomocy lub masz pytania?"""
        
    def _format_solutions(self, solutions: List[Dict]) -> str:
        """Format solutions for inclusion in prompt"""
        formatted = ""
        for i, solution in enumerate(solutions, 1):
            formatted += f"Rozwiązanie {i}:\n"
            formatted += f"Problem: {solution.get('problem', 'Nieznany problem')}\n"
            formatted += f"Rozwiązanie: {solution.get('solution', 'Brak rozwiązania')}\n\n"
        return formatted if formatted else "Brak odpowiednich rozwiązań w bazie wiedzy."
    
    def is_on_topic(self, query: str) -> Dict[str, Any]:
        """
        Sprawdza, czy zapytanie jest związane z tematyką urządzeń i serwisu.
        
        Args:
            query: Zapytanie użytkownika
            
        Returns:
            Dict: Zawiera 'is_on_topic' (bool) i 'response' (str) jeśli zapytanie jest off-topic
        """
        try:
            # Domyślnie zakładamy, że krótkie zapytania są na temat
            # Większość opisów problemów jest krótka, np. "nie działa", "wolno chodzi"
            if len(query.strip()) <= 30:
                return {"is_on_topic": True}
                
            # Prosta heurystyka - sprawdź, czy zapytanie zawiera słowa kluczowe związane z urządzeniami
            device_keywords = [
                "urządzenie", "urządzenia", "sprzęt", "aparat", "zdjęcia", "zdjęcie", "obraz", "obrazy", 
                "jakość", "wyraźne", "niewyraźne", "rozmyte", "ostrość", "kontrast", "jasność", 
                "włącza", "wyłącza", "restart", "zawiesza", "problem", "usterka", "awaria", "naprawa",
                "serwis", "gwarancja", "ekran", "wyświetlacz", "bateria", "zasilanie", "kabel", "głowica",
                "sonda", "przycisk", "menu", "ustawienia", "kalibracja", "diagnostyka", "błąd", "error",
                "vet", "eye", "vet-eye", "weterynaryjne", "weterynaryjny", "medyczne", "medyczny",
                # Dodajemy słowa opisujące ogólne problemy
                "wolno", "chodzi", "działa", "nie działa", "źle", "problem", "powoli", "szybko",
                "zawiesza", "zawiesił", "zacina", "zacięło", "błąd", "błędy", "psuje", "zepsuło",
                "uszkodzone", "uszkodzony", "popsuty", "popsute", "słabo", "kiepsko", "wadliwy",
                "wadliwie", "awaryjny", "awaria", "usterka", "nie", "tak", "pomocy", "pomoc"
            ]
            
            # Sprawdź, czy zapytanie zawiera jakiekolwiek słowo kluczowe
            query_lower = query.lower()
            for keyword in device_keywords:
                if keyword.lower() in query_lower:
                    return {"is_on_topic": True}
            
            # Jeśli zapytanie jest bardzo krótkie (np. "SN"), uznaj je za on-topic
            if len(query.strip()) <= 5:
                return {"is_on_topic": True}
                
            # Sprawdź, czy zapytanie zawiera wyraźne słowa kluczowe związane z polityką, plotkami itp.
            off_topic_keywords = [
                "trump", "biden", "polityka", "wybory", "partia", "prezydent", "premier", 
                "rząd", "sejm", "senat", "ustawa", "prawo", "przepisy", "konstytucja",
                "celebryta", "gwiazda", "aktor", "aktorka", "piosenkarz", "piosenkarka",
                "sport", "mecz", "piłka", "liga", "mistrzostwa", "olimpiada",
                "pogoda", "klimat", "temperatura", "deszcz", "śnieg", "burza"
            ]
            
            # Jeśli zapytanie zawiera wyraźne słowa off-topic, zwróć False
            for keyword in off_topic_keywords:
                if keyword.lower() in query_lower:
                    off_topic_response = """Przepraszam, ale jako asystent serwisowy Vet-Eye mogę odpowiadać wyłącznie na pytania związane z urządzeniami medycznymi naszej firmy, ich obsługą, konfiguracją i problemami technicznymi.

Czy mógłbyś zadać pytanie dotyczące Twojego urządzenia Vet-Eye lub opisać problem techniczny, z którym się spotkałeś? Jestem tu, aby pomóc Ci w rozwiązaniu problemów z urządzeniem."""
                    return {"is_on_topic": False, "response": off_topic_response}
            
            # Jeśli nie znaleziono wyraźnych słów off-topic, uznaj zapytanie za on-topic
            return {"is_on_topic": True}
                
        except Exception as e:
            logger.error(f"Error in is_on_topic: {str(e)}", exc_info=True)
            # W przypadku błędu, zakładamy że pytanie jest na temat
            return {"is_on_topic": True}
    
    def get_service_questions(self) -> List[str]:
        """Zwraca listę pytań potrzebnych do zgłoszenia serwisowego"""
        try:
            return [
                "Kiedy problem wystąpił po raz pierwszy?",
                "Jak często występuje problem?",
                "Czy urządzenie pokazuje jakieś komunikaty błędów?",
                "Czy próbowano już jakichś rozwiązań?",
                "Czy problem występuje w określonych warunkach?",
                "Czy urządzenie działa w trybie awaryjnym?",
                "Jakiej pilności jest zgłoszenie?"
            ]
        except Exception as e:
            logger.error(f"Error in get_service_questions: {str(e)}")
            return ["Opisz problem szczegółowo", "Kiedy problem się pojawił?"]