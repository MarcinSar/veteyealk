from openai import OpenAI
import logging
from typing import Dict, List, Optional, Any
import json

logger = logging.getLogger(__name__)

class AIHelper:
    def __init__(self, api_key):
        """Inicjalizacja pomocnika AI"""
        self.client = OpenAI(api_key=api_key)
        self.default_model = "gpt-4o-mini"
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
            
            response = self.client.chat.completions.create(
                model=self.default_model,
                messages=[
                    {"role": "system", "content": """Jesteś asystentem technicznym specjalizującym się w ultrasonografach weterynaryjnych.
                    Twoje odpowiedzi powinny być:
                    1. Empatyczne i profesjonalne
                    2. Zawierać podstawowe pytania diagnostyczne
                    3. Skupiać się na wstępnej diagnozie problemu
                    4. Pytać o kluczowe szczegóły aby zrozumieć problem
                    
                    Odpowiedź powinna być ZWIĘZŁA i KONKRETNA."""},
                    {"role": "user", "content": f"Problem z urządzeniem: {issue_description}"}
                ],
                temperature=0.5,
                max_tokens=500
            )
            
            result = response.choices[0].message.content
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

Na podstawie powyższych informacji:
1. Zidentyfikuj prawdopodobną przyczynę problemu
2. Przedstaw konkretne rozwiązanie krok po kroku
3. Podaj dodatkowe wskazówki, które mogą być istotne
4. Zachowaj profesjonalny, ale przyjazny ton
5. Na końcu zapytaj, czy zaproponowane rozwiązanie pomogło

Twoja odpowiedź powinna być ZWIĘZŁA i na temat."""

            response = self.client.chat.completions.create(
                model=self.default_model,
                messages=[
                    {"role": "system", "content": """Jesteś ekspertem technicznym specjalizującym się w ultrasonografach 
                    i urządzeniach medycznych firmy Vet-Eye. Twoja wiedza techniczna jest na najwyższym poziomie."""},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            result = response.choices[0].message.content
            
            # Ocena poziomu pewności odpowiedzi
            confidence_prompt = f"""Na podstawie:
            1. Opisu problemu: "{issue_description}"
            2. Dostępnych rozwiązań z bazy wiedzy
            3. Wygenerowanej odpowiedzi: "{result}"
            
            Oceń poziom pewności odpowiedzi w skali 0.0-1.0, gdzie:
            - 0.0-0.3: Niski poziom pewności - odpowiedź jest ogólna, brak konkretnego dopasowania w bazie wiedzy
            - 0.4-0.7: Średni poziom pewności - częściowe dopasowanie, ale mogą być potrzebne dodatkowe informacje
            - 0.8-1.0: Wysoki poziom pewności - bardzo dobre dopasowanie, rozwiązanie powinno być skuteczne
            
            Zwróć TYLKO liczbę bez dodatkowego tekstu."""
            
            confidence_response = self.client.chat.completions.create(
                model=self.default_model,
                messages=[
                    {"role": "system", "content": "Jesteś systemem oceniającym trafność dopasowania rozwiązań technicznych."},
                    {"role": "user", "content": confidence_prompt}
                ],
                temperature=0.1,
                max_tokens=10
            )
            
            try:
                confidence = float(confidence_response.choices[0].message.content.strip())
            except ValueError:
                confidence = 0.5  # Domyślna wartość w przypadku błędu
            
            return {
                "solution": result,
                "confidence_score": confidence
            }
            
        except Exception as e:
            logger.error(f"Error in analyze_problem_with_knowledge: {str(e)}", exc_info=True)
            return {
                "solution": f"Przepraszam, wystąpił błąd podczas analizy problemu. Sugeruję kontakt z serwisem.",
                "confidence_score": 0.1
            }
    
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