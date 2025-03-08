import logging
from typing import Dict, List, Optional, Any
import json

# Próba importu różnych wersji OpenAI API
try:
    # Próba importu nowej wersji (1.0.0+)
    from openai import OpenAI
    USING_NEW_OPENAI = True
    logging.getLogger(__name__).info("Using OpenAI new API (1.0.0+)")
except (ImportError, AttributeError):
    # Fallback do starszej wersji
    import openai
    USING_NEW_OPENAI = False
    logging.getLogger(__name__).info("Using OpenAI legacy API (<1.0.0)")

logger = logging.getLogger(__name__)

class AIHelper:
    def __init__(self, api_key):
        """Inicjalizacja pomocnika AI"""
        self.api_key = api_key
        if USING_NEW_OPENAI:
            # Nowa wersja API (1.0.0+)
            self.client = OpenAI(api_key=api_key)
            self.default_model = "gpt-4o-mini"
            logger.info("OpenAI client initialized with modern SDK")
        else:
            # Starsza wersja API (<1.0.0)
            openai.api_key = api_key
            self.client = openai
            # Użyj kompatybilnego modelu dla starszej wersji API
            self.default_model = "gpt-3.5-turbo"
            logger.info("OpenAI client initialized with legacy SDK")
        
        logger.info("AIHelper initialized")
        
    def analyze_issue(self, issue_description: str) -> str:
        """
        Analizuje wstępny opis problemu i zadaje odpowiednie pytania
        
        Args:
            issue_description: Opis problemu od użytkownika
            
        Returns:
            str: Wygenerowana odpowiedź od AI
        """
        try:
            logger.debug(f"Analyzing issue: {issue_description[:100]}...")
            
            system_content = """Jesteś asystentem technicznym specjalizującym się w ultrasonografach weterynaryjnych.
            Twoje odpowiedzi powinny być:
            1. Empatyczne i profesjonalne
            2. Zawierać podstawowe pytania diagnostyczne
            3. Skupiać się na wstępnej diagnozie problemu
            4. Pytać o kluczowe szczegóły aby zrozumieć problem
            
            Odpowiedź powinna być ZWIĘZŁA i KONKRETNA."""
            
            user_content = f"Problem z urządzeniem: {issue_description}"
            
            if USING_NEW_OPENAI:
                # Nowa wersja API (1.0.0+)
                response = self.client.chat.completions.create(
                    model=self.default_model,
                    messages=[
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": user_content}
                    ],
                    temperature=0.5,
                    max_tokens=500
                )
                result = response.choices[0].message.content
            else:
                # Starsza wersja API (<1.0.0)
                response = self.client.ChatCompletion.create(
                    model=self.default_model,
                    messages=[
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": user_content}
                    ],
                    temperature=0.5,
                    max_tokens=500
                )
                result = response.choices[0]['message']['content']
            
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

Odpowiedź powinna być szczegółowa i profesjonalna, ale zrozumiała dla niespecjalisty."""

            system_content = "Jesteś asystentem technicznym specjalizującym się w diagnostyce i rozwiązywaniu problemów z urządzeniami medycznymi."
            
            if USING_NEW_OPENAI:
                # Nowa wersja API (1.0.0+)
                response = self.client.chat.completions.create(
                    model=self.default_model,
                    messages=[
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.4,
                    max_tokens=800
                )
                result = response.choices[0].message.content
            else:
                # Starsza wersja API (<1.0.0)
                response = self.client.ChatCompletion.create(
                    model=self.default_model,
                    messages=[
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.4,
                    max_tokens=800
                )
                result = response.choices[0]['message']['content']
            
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
        """Formatuj rozwiązania do prompta"""
        if not solutions:
            return "Brak dokładnych dopasowań w bazie wiedzy dla tego problemu."
        
        formatted = []
        for i, solution in enumerate(solutions, 1):
            relevance = solution.get('relevance', 0) * 100
            solution_type = solution.get('type', 'unknown')
            content = solution.get('content', 'Brak treści')
            
            formatted.append(f"Rozwiązanie {i} (Trafność: {relevance:.0f}%, Typ: {solution_type}):\n{content}\n")
        
        return "\n".join(formatted)
    
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