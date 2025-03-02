import json
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import re
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

class KnowledgeBase:
    def __init__(self, data_path="data"):
        """
        Inicjalizacja bazy wiedzy technicznej
        
        Args:
            data_path: Ścieżka do katalogu z danymi
        """
        self.data_path = Path(data_path)
        logger.info(f"Initializing Knowledge Base from {data_path}")
        
        # Ścieżki do plików z danymi
        self.files_to_load = [
            self.data_path / 'documents.json',
            self.data_path / 'troubleshooting.json',
            self.data_path / 'usage.json'
        ]
        
        # Ładowanie danych
        self.documents = self._load_json_file(self.files_to_load[0])
        self.troubleshooting = self._load_json_file(self.files_to_load[1])
        self.usage_guides = self._load_json_file(self.files_to_load[2])
        
        # Techniczne słowa kluczowe
        self.technical_keywords = [
            "błąd", "nie włącza", "awaria", "problem", "usterka", "uszkodzenie",
            "głośny", "hałas", "wyłącza", "przegrzewa", "restart", "ekran", 
            "obraz", "zasilanie", "bateria", "akumulator", "wentylator", "głośnik",
            "zamraża", "zawiesza", "nie działa", "nie reaguje", "komunikat"
        ]
        
        logger.info(f"Knowledge Base initialized with {len(self.documents)} documents, " +
                   f"{len(self.troubleshooting)} troubleshooting entries, " +
                   f"{len(self.usage_guides)} usage guides")
        
    def _load_json_file(self, filepath: Path) -> List:
        """Ładuje dane z pliku JSON"""
        try:
            if not filepath.exists():
                logger.warning(f"File not found: {filepath}")
                return []
                
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing {filepath}: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Error loading {filepath}: {str(e)}")
            return []

    def find_solution(self, model: str, problem_description: str) -> Tuple[List[Dict], str]:
        """
        Znajduje rozwiązanie problemu na podstawie opisu i modelu urządzenia
        
        Args:
            model: Model urządzenia
            problem_description: Opis problemu
            
        Returns:
            Tuple[List[Dict], str]: Lista znalezionych rozwiązań i komunikat
        """
        logger.info(f"Searching solution for model {model} and problem: {problem_description[:50]}...")
        
        # Tokenizacja problemu
        problem_tokens = self._tokenize(problem_description)
        logger.debug(f"Problem tokens: {problem_tokens[:10]}...")
        
        # Lista znalezionych rozwiązań
        solutions = []
        
        # 1. Szukanie w troubleshooting (priorytet)
        troubleshooting_solutions = self._search_troubleshooting(model, problem_description, problem_tokens)
        if troubleshooting_solutions:
            solutions.extend(troubleshooting_solutions)
            logger.debug(f"Found {len(troubleshooting_solutions)} troubleshooting solutions")
        
        # 2. Szukanie w dokumentacji (jeśli za mało rozwiązań)
        if len(solutions) < 3:
            doc_solutions = self._search_documents(model, problem_description, problem_tokens)
            if doc_solutions:
                solutions.extend(doc_solutions)
                logger.debug(f"Found {len(doc_solutions)} document solutions")
        
        # 3. Szukanie w instrukcjach użytkowania (jeśli nadal za mało)
        if len(solutions) < 3:
            usage_solutions = self._search_usage_guides(model, problem_description, problem_tokens)
            if usage_solutions:
                solutions.extend(usage_solutions)
                logger.debug(f"Found {len(usage_solutions)} usage guide solutions")
        
        # Sortowanie rozwiązań według trafności
        solutions.sort(key=lambda x: x.get('relevance', 0), reverse=True)
        
        # Komunikat zwrotny
        message = self._generate_response_message(solutions)
        
        return solutions[:5], message  # Zwracamy maksymalnie 5 najlepszych rozwiązań
    
    def _search_troubleshooting(self, model: str, problem: str, problem_tokens: List[str]) -> List[Dict]:
        """Wyszukuje rozwiązania w bazie problemów"""
        matches = []
        
        for item in self.troubleshooting:
            # Sprawdź czy dotyczy modelu
            item_model = item.get('metadata', {}).get('device_model', '')
            if item_model and item_model != model:
                continue
            
            # Sprawdź słowa kluczowe
            keywords = item.get('metadata', {}).get('keywords', [])
            keywords_lower = [kw.lower() for kw in keywords]
            
            # Sprawdź symptomy
            symptoms = item.get('metadata', {}).get('symptoms', [])
            symptoms_lower = [s.lower() for s in symptoms]
            
            # Oblicz podobieństwo do problemu
            problem_content = item.get('problem', '')
            solution_content = item.get('solution', '')
            content = f"{problem_content} {solution_content}"
            
            # Oblicz różne metryki podobieństwa
            keyword_match = self._calculate_keyword_match(problem_tokens, keywords_lower)
            symptom_match = self._calculate_symptom_match(problem, symptoms_lower)
            content_match = self._calculate_text_similarity(problem, content)
            
            # Oblicz łączną trafność
            relevance = (keyword_match * 0.4) + (symptom_match * 0.3) + (content_match * 0.3)
            
            if relevance > 0.2:  # Minimalny próg trafności
                matches.append({
                    'content': f"Problem: {problem_content}\n\nRozwiązanie: {solution_content}",
                    'relevance': relevance,
                    'type': 'troubleshooting'
                })
        
        return matches
    
    def _search_documents(self, model, problem_description, problem_tokens):
        """
        Searches through documents to find most relevant ones for the given problem
        """
        results = []
        
        try:
            for doc in self.documents:
                # Check if doc is a list and extract the first item if it is
                if isinstance(doc, list):
                    if not doc:  # Skip empty lists
                        continue
                    doc = doc[0]  # Take the first item
                
                doc_model = doc.get('metadata', {}).get('device_model', '')
                
                # If model specified, filter by model
                if model and model != "unknown" and doc_model and doc_model != model:
                    continue
                    
                # Calculate relevance based on content match
                content = doc.get('content', '').lower()
                
                # Calculate relevance score
                relevance = self._calculate_relevance(content, problem_tokens)
                
                if relevance > 0.1:  # Only include somewhat relevant results
                    results.append({
                        'type': 'document',
                        'content': doc.get('content', ''),
                        'metadata': doc.get('metadata', {}),
                        'relevance': relevance
                    })
                    
            return sorted(results, key=lambda x: x['relevance'], reverse=True)[:5]  # Return top 5
            
        except Exception as e:
            logger.error(f"Error in _search_documents: {str(e)}", exc_info=True)
            return []
    
    def _search_usage_guides(self, model: str, problem: str, problem_tokens: List[str]) -> List[Dict]:
        """Wyszukuje rozwiązania w instrukcjach użytkowania"""
        matches = []
        
        for guide in self.usage_guides:
            # Sprawdź czy dotyczy modelu
            guide_model = guide.get('metadata', {}).get('device_model', '')
            if guide_model and guide_model != model:
                continue
            
            # Sprawdź treść instrukcji
            content = guide.get('content', '')
            title = guide.get('title', '')
            
            # Oblicz podobieństwo tekstu
            similarity = self._calculate_text_similarity(problem, content)
            
            if similarity > 0.15:  # Niższy próg dla instrukcji
                matches.append({
                    'content': f"Instrukcja: {title}\n\n{content}",
                    'relevance': similarity,
                    'type': 'usage_guide'
                })
        
        return matches
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenizacja tekstu z obsługą polskich znaków"""
        return re.findall(r'\w+', text.lower())
    
    def _calculate_keyword_match(self, problem_tokens: List[str], keywords: List[str]) -> float:
        """Oblicza dopasowanie słów kluczowych"""
        if not keywords:
            return 0.0
            
        matches = sum(1 for token in problem_tokens if any(token in kw for kw in keywords))
        return matches / len(problem_tokens) if problem_tokens else 0.0
    
    def _calculate_symptom_match(self, problem: str, symptoms: List[str]) -> float:
        """Oblicza dopasowanie symptomów"""
        if not symptoms:
            return 0.0
            
        # Sprawdź każdy symptom
        symptom_scores = []
        for symptom in symptoms:
            if len(symptom) > 5:  # Tylko dłuższe symptomy
                score = SequenceMatcher(None, problem.lower(), symptom).ratio()
                symptom_scores.append(score)
        
        return max(symptom_scores) if symptom_scores else 0.0
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Oblicza podobieństwo tekstów"""
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    def _generate_response_message(self, solutions: List[Dict]) -> str:
        """Generuje komunikat na podstawie znalezionych rozwiązań"""
        if not solutions:
            return "Nie znaleziono dopasowań w bazie wiedzy dla tego problemu."
        
        count = len(solutions)
        types = [s.get('type', '') for s in solutions]
        
        if 'troubleshooting' in types:
            return f"Znaleziono {count} potencjalnych rozwiązań tego problemu w bazie wiedzy."
        elif 'documentation' in types:
            return f"Znaleziono {count} powiązanych informacji w dokumentacji technicznej."
        else:
            return f"Znaleziono {count} powiązanych informacji w bazie wiedzy."