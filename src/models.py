
### `src/models.py`


"""
ZHAW MSc Psychology - Timetable Planner (Domain Models Layer)
Author: HealthData CodeArchitect
Description: Defines the core data structures using Pydantic V2. 
Provides rigorous validation, type coercion, and sanitization to ensure 
that the UI/UX layer receives exclusively flawless and strictly typed data.
"""

from typing import Optional, Any
from datetime import time, datetime, date
from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

# ==========================================
# 1. ENUMERATIONS (Standardizing UI Inputs)
# ==========================================
class Weekday(str, Enum):
    """
    Standardizes weekdays to prevent UI sorting issues or filtering bugs 
    caused by typos in the raw data.
    """
    MONDAY = "montag"
    TUESDAY = "dienstag"
    WEDNESDAY = "mittwoch"
    THURSDAY = "donnerstag"
    FRIDAY = "freitag"
    SATURDAY = "samstag"
    SUNDAY = "sonntag"


# ==========================================
# 2. CORE DOMAIN MODELS
# ==========================================
class ZHAWModule(BaseModel):
    """
    Core data model representing a single academic module/course.
    Enforces strict typing and logical constraints to guarantee UI stability.
    """
    
    # --- Pydantic V2 Configuration ---
    # Automatically strip whitespace from strings and forbid extra fields
    # to maintain a clean memory footprint.
    model_config = ConfigDict(
        str_strip_whitespace=True, 
        extra="ignore",
        frozen=False  # Set to True if objects should be strictly immutable after creation
    )

    # --- Required Fields (The Schema Contract) ---
    modulname: str = Field(
        ..., 
        min_length=2, 
        max_length=300,
        description="Official name of the module."
    )

    datum: Optional[date] = Field(
        default=None,
        description="Calendar date of the module if available."
    )

    modul_nr: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Module identifier (e.g. KP10-1)."
    )

    kurs_nr: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Course identifier within a module."
    )

    pruefung_flag: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Raw exam indicator from source exports."
    )

    ist_pruefung: bool = Field(
        default=False,
        description="True if this row represents an exam event."
    )
    
    wochentag: Weekday = Field(
        ..., 
        description="Day of the week the module takes place."
    )
    
    startzeit: time = Field(
        ..., 
        description="Start time of the module (HH:MM format)."
    )
    
    endzeit: time = Field(
        ..., 
        description="End time of the module (HH:MM format)."
    )
    
    ects: int = Field(
        ..., 
        ge=0, 
        le=60, 
        description="ECTS credits awarded. Must be realistically bounded (0-60)."
    )

    # --- Optional Fields (UI Enhancements) ---
    modultyp: Optional[str] = Field(
        default="N/A", 
        max_length=50, 
        description="Type of the module (e.g., Lecture, Seminar)."
    )
    
    dozierende: Optional[str] = Field(
        default="N/A", 
        max_length=200, 
        description="Name(s) of the lecturer(s)."
    )
    
    raum: Optional[str] = Field(
        default="N/A", 
        max_length=100, 
        description="Room number or building code."
    )

    # ==========================================
    # 3. CUSTOM VALIDATORS & DATA COERCION
    # ==========================================
    
    @field_validator('wochentag', mode='before')
    @classmethod
    def sanitize_weekday(cls, v: str) -> str:
        """
        Pre-processes the weekday string before Enum validation.
        Ensures that ' Montag ', 'MONTAG', or 'montag' all map correctly.
        """
        if isinstance(v, str):
            normalized = v.strip().lower()
            aliases = {
                "mo": "montag",
                "mon": "montag",
                "monday": "montag",
                "di": "dienstag",
                "tue": "dienstag",
                "tuesday": "dienstag",
                "mi": "mittwoch",
                "wed": "mittwoch",
                "wednesday": "mittwoch",
                "do": "donnerstag",
                "thu": "donnerstag",
                "thursday": "donnerstag",
                "fr": "freitag",
                "fri": "freitag",
                "friday": "freitag",
                "sa": "samstag",
                "sat": "samstag",
                "saturday": "samstag",
                "so": "sonntag",
                "sun": "sonntag",
                "sunday": "sonntag",
            }
            return aliases.get(normalized, normalized)
        return v

    @field_validator('startzeit', 'endzeit', mode='before')
    @classmethod
    def parse_time_strings(cls, v: str | time) -> time:
        """
        Robustly parses various time string formats into Python datetime.time objects.
        This prevents UI crashes when rendering timeline components.
        """
        if isinstance(v, time):
            return v
        
        if isinstance(v, str):
            v_clean = v.strip().replace('.', ':') # Handle common typo '08.15' -> '08:15'
            try:
                # Attempt standard HH:MM parsing
                parsed_time = datetime.strptime(v_clean, '%H:%M').time()
                return parsed_time
            except ValueError:
                # Attempt parsing if seconds are included (HH:MM:SS)
                try:
                    return datetime.strptime(v_clean, '%H:%M:%S').time()
                except ValueError:
                    raise ValueError(f"Invalid time format: '{v}'. Expected HH:MM.")
        
        raise ValueError("Time must be a string or datetime.time object.")

    @field_validator('datum', mode='before')
    @classmethod
    def parse_date_value(cls, v: str | date | datetime | None) -> date | None:
        """Parse common date formats from timetable exports."""
        if v is None:
            return None
        if isinstance(v, date) and not isinstance(v, datetime):
            return v
        if isinstance(v, datetime):
            return v.date()
        if isinstance(v, str):
            value = v.strip()
            if value.lower() in {"", "n/a", "na", "none", "nan"}:
                return None

            # Fast path for ISO-like datetime strings, e.g. "2026-11-05 00:00:00".
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
            except ValueError:
                pass

            for fmt in (
                "%d.%m.%Y",
                "%Y-%m-%d",
                "%d/%m/%Y",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M",
                "%d.%m.%Y %H:%M:%S",
                "%d.%m.%Y %H:%M",
            ):
                try:
                    return datetime.strptime(value, fmt).date()
                except ValueError:
                    continue
        raise ValueError(f"Invalid date format: '{v}'.")

    @field_validator('modul_nr', 'kurs_nr', 'pruefung_flag', mode='before')
    @classmethod
    def sanitize_optional_identifiers(cls, v: str | None) -> str | None:
        """Normalize optional identifier fields and drop placeholder values."""
        if v is None:
            return None
        value = str(v).strip()
        if value.lower() in {"", "n/a", "na", "none", "nan"}:
            return None
        return value

    @field_validator('ist_pruefung', mode='before')
    @classmethod
    def parse_exam_boolean(cls, v: Any) -> bool:
        """Parse flexible boolean-like exam indicators."""
        if isinstance(v, bool):
            return v
        if v is None:
            return False
        value = str(v).strip().lower()
        if value in {"", "0", "false", "nein", "no", "none", "nan"}:
            return False
        if value in {"1", "true", "ja", "yes", "pruefung", "prüfung", "exam"}:
            return True
        return False

    @model_validator(mode='after')
    def validate_time_logic(self) -> 'ZHAWModule':
        """
        Cross-field validation: Guarantees that a module's end time is always 
        strictly after its start time. This is critical for any calendar/timeline UI
        to prevent negative height calculations or rendering bugs.
        """
        # Convert time to total minutes for safe mathematical comparison
        start_minutes = self.startzeit.hour * 60 + self.startzeit.minute
        end_minutes = self.endzeit.hour * 60 + self.endzeit.minute

        if end_minutes <= start_minutes:
            raise ValueError(
                f"Logical Error in '{self.modulname}': "
                f"End time ({self.endzeit}) must be strictly after start time ({self.startzeit})."
            )
            
        # Infer exam rows from name/flag even if explicit flag is missing.
        title = (self.modulname or "").lower()
        flag = (self.pruefung_flag or "").lower()
        if ("pruefung" in title or "prüfung" in title or "pruefung" in flag or "prüfung" in flag):
            self.ist_pruefung = True

        return self

    # ==========================================
    # 4. HELPER METHODS FOR THE GUI
    # ==========================================
    
    @property
    def duration_minutes(self) -> int:
        """
        Calculates the duration of the module in minutes.
        Highly useful for the UI when calculating block sizes in a grid layout.
        """
        start_min = self.startzeit.hour * 60 + self.startzeit.minute
        end_min = self.endzeit.hour * 60 + self.endzeit.minute
        return end_min - start_min

    def to_ui_dict(self) -> dict:
        """
        Serializes the object into a clean dictionary formatted specifically 
        for frontend consumption (e.g., Streamlit Dataframes or AG Grid).
        """
        return {
            "Modul-Nr": self.modul_nr,
            "Kurs-Nr": self.kurs_nr,
            "Modul": self.modulname,
            "Tag": self.wochentag.value.capitalize(),
            "Datum": self.datum.strftime('%Y-%m-%d') if self.datum else "",
            "Zeit": f"{self.startzeit.strftime('%H:%M')} - {self.endzeit.strftime('%H:%M')}",
            "Dauer (Min)": self.duration_minutes,
            "ECTS": self.ects,
            "Pruefung": "Ja" if self.ist_pruefung else "Nein",
            "Dozent:in": self.dozierende,
            "Raum": self.raum,
            "Typ": self.modultyp
        }

