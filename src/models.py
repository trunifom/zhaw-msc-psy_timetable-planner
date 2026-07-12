from pydantic import BaseModel, field_validator
from datetime import time

class ZHAWModule(BaseModel):
    modulname: str
    modultyp: str  # z.B. Pflicht, Wahlpflicht
    ects: int
    wochentag: str
    startzeit: time
    endzeit: time
    dozierende: str | None = None

    @field_validator("endzeit")
    @classmethod
    def check_time_logic(cls, v: time, info) -> time:
        if "startzeit" in info.data and v <= info.data["startzeit"]:
            raise ValueError(f"Endzeit muss nach der Startzeit liegen. (Modul: {info.data.get('modulname')})")
        return v