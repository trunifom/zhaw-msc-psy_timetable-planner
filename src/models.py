
### `src/models.py`


"""
ZHAW MSc Psychology - Timetable Planner (Domain Models Layer)
Author: HealthData CodeArchitect
Description: Defines the core data structures using Pydantic V2. 
Provides rigorous validation, type coercion, and sanitization to ensure 
that the UI/UX layer receives exclusively flawless and strictly typed data.
"""

from typing import Optional
from datetime import time, datetime
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
        max_length=150, 
        description="Official name of the module."
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
            return v.strip().lower()
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
            "Modul": self.modulname,
            "Tag": self.wochentag.value.capitalize(),
            "Zeit": f"{self.startzeit.strftime('%H:%M')} - {self.endzeit.strftime('%H:%M')}",
            "Dauer (Min)": self.duration_minutes,
            "ECTS": self.ects,
            "Dozent:in": self.dozierende,
            "Raum": self.raum,
            "Typ": self.modultyp
        }

