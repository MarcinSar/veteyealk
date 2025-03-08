import requests
from datetime import datetime, timedelta
import pytz
import logging
import os
from typing import Union, Tuple, Optional
import caldav
from caldav.elements import dav, cdav
import re
from airtable import Airtable
from dateutil import parser

# Usuń istniejącą konfigurację
logging.getLogger(__name__).handlers = []

# Konfiguracja loggera dla kalendarza
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class CalendarClient:
    # Format do zapisywania w Airtable
    AIRTABLE_DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'  # format ISO 8601 z Z na końcu
    # Format do wyświetlania użytkownikowi
    DISPLAY_FORMAT = '%d.%m.%Y %H:%M'  # przyjazny format dla użytkownika

    def __init__(self):
        self.logger = logger  # Użyj loggera zdefiniowanego powyżej
        self.logger.debug("Initializing CalendarClient")
        self.timezone = pytz.timezone('Europe/Warsaw')
        
        # Używamy parametrów pozycyjnych zamiast nazwanych dla większej kompatybilności
        base_id = os.getenv('AIRTABLE_BASE_ID')
        api_key = os.getenv('AIRTABLE_API_KEY')
        
        try:
            # Próba inicjalizacji z airtable-python-wrapper
            self.airtable = Airtable(base_id, 'Calendar', api_key)
            self.logger.info("Initialized with airtable-python-wrapper")
        except Exception as e:
            self.logger.error(f"Error initializing with airtable-python-wrapper: {str(e)}")
            try:
                # Alternatywna inicjalizacja jeśli dostępny jest pyairtable
                import pyairtable
                self.airtable = pyairtable.Table(api_key, base_id, 'Calendar')
                self.logger.info("Initialized with pyairtable")
            except Exception as e2:
                self.logger.error(f"Error initializing with pyairtable: {str(e2)}")
                raise Exception(f"Failed to initialize any Airtable client: {str(e)}, then {str(e2)}")
        
        self.logger.info("CalendarClient initialized successfully")

    def get_available_slots(self, start_date=None):
        """Zwraca 10 najbliższych dostępnych terminów w godzinach pracy"""
        try:
            if not start_date:
                start_date = datetime.now()
            
            available_slots = []
            current_date = start_date
            
            # Godziny pracy
            WORK_HOURS_START = 8  # 8:00
            WORK_HOURS_END = 19   # 19:00
            
            while len(available_slots) < 10:
                # Sprawdź czy dzień jest od poniedziałku (0) do soboty (5)
                if current_date.weekday() < 6:  # 6 = niedziela
                    # Iteruj przez godziny pracy
                    for hour in range(WORK_HOURS_START, WORK_HOURS_END):
                        if len(available_slots) >= 10:
                            break
                        
                        slot_time = current_date.replace(hour=hour, minute=0, second=0, microsecond=0)
                        
                        # Dodaj tylko przyszłe terminy
                        if slot_time > datetime.now():
                            available_slots.append(slot_time)
            
                # Przejdź do następnego dnia
                current_date += timedelta(days=1)
            
            return available_slots
        except Exception as e:
            logger.error(f"Error getting available slots: {e}")
            return []

    def format_slots(self, slots):
        """Formatuj terminy w czytelny sposób"""
        formatted_slots = []
        days_pl = {
            0: 'Poniedziałek',
            1: 'Wtorek',
            2: 'Środa',
            3: 'Czwartek',
            4: 'Piątek',
            5: 'Sobota'
        }
        
        for i, slot in enumerate(slots, 1):
            day_name = days_pl[slot.weekday()]
            formatted_date = slot.strftime("%d.%m.%Y")
            formatted_time = slot.strftime("%H:%M")
            formatted_slots.append(
                f"{i}. {day_name}, {formatted_date}, godz. {formatted_time}"
            )
            
        return formatted_slots

    def get_available_slots_around(self, preferred_time: datetime, hours_range: int = 2) -> list:
        """Get available slots around preferred time."""
        try:
            start_range = preferred_time - timedelta(hours=hours_range)
            end_range = preferred_time + timedelta(hours=hours_range)
            
            # Get all slots in range
            all_slots = []
            current = start_range.replace(minute=0)
            
            while current <= end_range:
                if 9 <= current.hour < 17:  # Business hours
                    all_slots.append(current)
                current += timedelta(hours=1)
            
            # Get booked slots
            events = self.calendar.date_search(
                start=start_range,
                end=end_range
            )
            
            booked_times = []
            for event in events:
                event_data = event.instance.vevent
                start = event_data.dtstart.value
                if isinstance(start, datetime):
                    booked_times.append(start)
            
            # Filter available slots
            available_slots = [
                slot.strftime(self.AIRTABLE_DATETIME_FORMAT)
                for slot in all_slots
                if slot not in booked_times
            ]
            
            return available_slots

        except Exception as e:
            logger.error(f"Error getting available slots around time: {e}")
            return []

    def parse_preferred_time(self, time_str: str) -> Optional[datetime]:
        """Parse user input time string into datetime object."""
        try:
            if re.match(r'\d{2}\.\d{2}\s+\d{2}:\d{2}', time_str):
                # ❌ Zmień format (usuń sekundy)
                date_obj = datetime.strptime(
                    f"{datetime.now().year}.{time_str}", 
                    '%Y.%d.%m %H:%M'
                )
                return self.timezone.localize(date_obj)
            
            # Pattern for day of week HH:MM
            days = {'poniedziałek': 0, 'wtorek': 1, 'środa': 2, 'czwartek': 3,
                   'piątek': 4, 'sobota': 5, 'niedziela': 6}
            
            for day, day_num in days.items():
                if day in time_str.lower():
                    time_part = re.search(r'\d{2}:\d{2}', time_str)
                    if time_part:
                        now = datetime.now()
                        current_weekday = now.weekday()
                        days_ahead = (day_num - current_weekday) % 7
                        if days_ahead == 0 and now.hour >= int(time_part.group().split(':')[0]):
                            days_ahead = 7
                        
                        target_date = now + timedelta(days=days_ahead)
                        time_str = time_part.group()
                        hour, minute = map(int, time_str.split(':'))
                        
                        return self.timezone.localize(
                            target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                        )
            
            return None

        except Exception as e:
            logger.error(f"Error parsing preferred time: {e}")
            return None

    def add_service_event(self, summary, description, date_time, customer_email=None):
        """Dodaje wydarzenie serwisowe do kalendarza"""
        print("=== Starting add_service_event ===")
        print(f"Input date_time: {date_time}, type: {type(date_time)}")
        
        try:
            # Format daty-czasu zgodny z Airtable (ISO 8601)
            if isinstance(date_time, datetime):
                print(f"Date object: {date_time}, type: {type(date_time)}, tzinfo: {date_time.tzinfo}")
                
                # Upewnij się, że data ma strefę czasową
                if date_time.tzinfo is None:
                    local_tz = pytz.timezone('Europe/Warsaw')
                    date_time = local_tz.localize(date_time)
                
                print(f"After localization: {date_time}, tzinfo: {date_time.tzinfo}")
                
                # Konwersja do UTC na potrzeby Airtable
                utc_time = date_time.astimezone(pytz.UTC)
                print(f"Converted to UTC: {utc_time}")
                
                # Format zgodny z ISO 8601 dla Airtable
                formatted_date = utc_time.strftime('%Y-%m-%dT%H:%M:%SZ')
                print(f"Formatted date for Airtable: {formatted_date}")
                
                # Przygotuj rekord do utworzenia
                record = {
                    'date_time': formatted_date,
                    'summary': summary,
                    'description': description,
                }
                
                if customer_email:
                    record['customer_email'] = customer_email
                    
                print(f"Record to create: {record}")
                
                # Utwórz instancję dla tabeli Calendar
                base_id = os.getenv('AIRTABLE_BASE_ID')
                api_key = os.getenv('AIRTABLE_API_KEY')
                calendar_table = Airtable(base_id, 'Calendar', api_key)
                
                # Zmiana z calendar_table.create(record) na calendar_table.insert(record)
                created_record = calendar_table.insert(record)
                
                # Zwróć ID utworzonego rekordu
                return {
                    'id': created_record.get('id', ''),
                    'link': f"https://airtable.com/{base_id}/Calendar/{created_record.get('id', '')}"
                }
                
            else:
                raise ValueError(f"Invalid date_time format: {date_time}, type: {type(date_time)}")
        
        except Exception as e:
            print(f"Error in add_service_event: {str(e)}")
            return {
                'id': '',
                'link': ''
            }

    def validate_event_data(self, event_data: dict) -> bool:
        required_fields = ['date_time', 'title', 'customer_email']
        return all(field in event_data for field in required_fields)

    def safe_airtable_operation(self, operation):
        """Bezpieczne wykonanie operacji Airtable z obsługą błędów i ponownymi próbami"""
        try:
            return operation()
        except Exception as e:
            self.logger.error(f"Airtable operation error: {str(e)}")
            # Można tu dodać logikę ponownych prób, obecnie po prostu przekazujemy błąd
            raise

    def format_single_slot(self, slot):
        """Formatuj pojedynczy termin"""
        days_pl = {
            0: 'Poniedziałek',
            1: 'Wtorek',
            2: 'Środa',
            3: 'Czwartek',
            4: 'Piątek',
            5: 'Sobota'
        }
        
        day_name = days_pl[slot.weekday()]
        formatted_date = slot.strftime(self.DISPLAY_FORMAT)  # używamy stałej DISPLAY_FORMAT
        return f"{day_name}, {formatted_date}"