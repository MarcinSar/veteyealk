from airtable import Airtable
import logging
import re
from typing import Dict, List, Optional, Union, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class AirtableClient:
    def __init__(self, api_key, base_id):
        """
        Inicjalizuje klienta Airtable
        
        Args:
            api_key: Klucz API Airtable
            base_id: ID bazy Airtable
        """
        try:
            # Używamy bezpośrednio Airtable bez dodatkowych parametrów, które mogą powodować problemy
            self.technicians = Airtable(base_id, 'Technicians', api_key)
            self.devices = Airtable(base_id, 'Devices', api_key)
            self.customers = Airtable(base_id, 'Customers', api_key)
            self.service_requests = Airtable(base_id, 'Service_Requests', api_key)
            logger.info("Airtable client initialized")
        except Exception as e:
            logger.error(f"Error initializing Airtable client: {str(e)}", exc_info=True)
            raise
    
    def get_device_info(self, serial_input: str) -> Dict[str, Any]:
        """
        Pobiera informacje o urządzeniu na podstawie numeru seryjnego
        
        Args:
            serial_input: Numer seryjny (może zawierać prefiks SN:)
            
        Returns:
            Dict: Informacje o urządzeniu lub komunikat o błędzie
        """
        try:
            # Wyczyść format numeru seryjnego
            serial_pattern = re.compile(r'SN[:.]?\s*(\w+)', re.IGNORECASE)
            match = serial_pattern.search(serial_input)
            
            if match:
                clean_serial = match.group(1)
            else:
                clean_serial = serial_input.replace('SN:', '').strip()
            
            logger.debug(f"Searching for device with SN: {clean_serial}")
            
            # Szukamy w kolumnie 'serial_number'
            devices = self.devices.search('serial_number', clean_serial)
            
            if devices:
                device_info = devices[0]
                
                # Pobierz dane klienta jeśli są dostępne
                customer_info = None
                if 'customer_id' in device_info['fields']:
                    customer_id = device_info['fields']['customer_id']
                    if customer_id:
                        customer_info = self.get_customer_by_id(customer_id)
                
                logger.info(f"Device found: {device_info['id']}")
                
                return {
                    "status": "success",
                    "device": device_info,
                    "customer": customer_info
                }
            else:
                logger.warning(f"Device not found: {clean_serial}")
                return {
                    "status": "error",
                    "message": f"Nie znaleziono urządzenia o numerze seryjnym: {clean_serial}"
                }
                
        except Exception as e:
            logger.error(f"Error getting device info: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": "Wystąpił błąd podczas weryfikacji urządzenia"
            }
    
    def get_customer_by_id(self, customer_id: str) -> Optional[Dict]:
        """
        Pobiera dane klienta na podstawie ID
        
        Args:
            customer_id: ID klienta w Airtable
            
        Returns:
            Optional[Dict]: Dane klienta lub None
        """
        try:
            customer = self.customers.get(customer_id)
            return customer
        except Exception as e:
            logger.error(f"Error getting customer by ID {customer_id}: {str(e)}")
            return None
    
    def create_service_request(self, data: Dict) -> Dict:
        """
        Tworzy zgłoszenie serwisowe w Airtable
        
        Args:
            data: Dane zgłoszenia serwisowego
            
        Returns:
            Dict: Informacje o utworzonym zgłoszeniu lub błędzie
        """
        try:
            required_fields = ['device_id', 'issue_description']
            missing_fields = [f for f in required_fields if f not in data]
            
            if missing_fields:
                return {
                    "status": "error",
                    "message": f"Brak wymaganych pól: {', '.join(missing_fields)}"
                }
            
            # Przygotuj dane do zapisu
            fields = {
                'Device': [data['device_id']],
                'Description': data['issue_description'],
                'Status': 'New',
                'Created': datetime.now().isoformat(),
            }
            
            # Dodaj opcjonalne pola
            if 'customer_id' in data:
                fields['Customer'] = [data['customer_id']]
            
            if 'scheduled_date' in data:
                fields['Scheduled_Date'] = data['scheduled_date']
            
            # Utwórz zgłoszenie
            result = self.service_requests.insert(fields)
            
            logger.info(f"Service request created: {result['id']}")
            
            return {
                "status": "success",
                "id": result['id'],
                "fields": result['fields']
            }
            
        except Exception as e:
            logger.error(f"Error creating service request: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": f"Błąd podczas tworzenia zgłoszenia: {str(e)}"
            }
    
    def schedule_service(self, service_id: str, scheduled_date: str) -> Dict:
        """
        Aktualizuje termin zgłoszenia serwisowego
        
        Args:
            service_id: ID zgłoszenia serwisowego
            scheduled_date: Data zaplanowanej wizyty (ISO format)
            
        Returns:
            Dict: Wynik aktualizacji
        """
        try:
            result = self.service_requests.update(service_id, {
                'Status': 'Scheduled',
                'Scheduled_Date': scheduled_date
            })
            
            logger.info(f"Service request {service_id} scheduled for {scheduled_date}")
            
            return {
                "status": "success",
                "id": result['id'],
                "fields": result['fields']
            }
            
        except Exception as e:
            logger.error(f"Error scheduling service: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": f"Błąd podczas aktualizacji terminu: {str(e)}"
            }
    
    def get_technicians(self) -> List[Dict]:
        """
        Pobiera listę dostępnych techników
        
        Returns:
            List[Dict]: Lista techników
        """
        try:
            return self.technicians.get_all()
        except Exception as e:
            logger.error(f"Error getting technicians: {str(e)}")
            return []
    
    def update_customer_info(self, customer_id: str, data: Dict) -> Dict:
        """
        Aktualizuje dane klienta
        
        Args:
            customer_id: ID klienta
            data: Nowe dane klienta
            
        Returns:
            Dict: Wynik aktualizacji
        """
        try:
            fields = {}
            
            # Mapowanie pól
            if 'name' in data:
                fields['Name'] = data['name']
            if 'email' in data:
                fields['Email'] = data['email']
            if 'phone' in data:
                fields['Phone'] = data['phone']
            if 'address' in data:
                fields['Address'] = data['address']
            
            # Aktualizuj dane
            result = self.customers.update(customer_id, fields)
            
            return {
                "status": "success",
                "id": result['id'],
                "fields": result['fields']
            }
            
        except Exception as e:
            logger.error(f"Error updating customer info: {str(e)}")
            return {
                "status": "error",
                "message": f"Błąd podczas aktualizacji danych klienta: {str(e)}"
            }

    def create_calendar_record(self, record_data):
        """Dodaje nowy wpis do tabeli Calendar"""
        try:
            # Sprawdź czy tabela Calendar istnieje, jeśli nie - utwórz ją
            if not hasattr(self, 'calendar'):
                self.calendar = Airtable(self.devices.base_id, 'Calendar', self.devices.api_key)
            
            response = self.calendar.insert(record_data)
            return {'status': 'success', 'record': response}
        except Exception as e:
            logger.error(f"Error creating calendar record: {str(e)}")
            return {'status': 'error', 'message': str(e)}