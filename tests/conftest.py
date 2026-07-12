import pytest
import pandas as pd
import numpy as np

@pytest.fixture
def mock_patient_data() -> pd.DataFrame:
    """
    Stellt einen synthetischen Datensatz für Tests zur Verfügung.
    Enthält absichtlich direkte Identifikatoren (Namen), um die 
    DSGVO-konformen Anonymisierungs-Pipelines testen zu können.
    Ebenso werden fehlende Werte (NaN) für Robustheitstests inkludiert.
    """
    data = {
        "patient_id": ["P001", "P002", "P003", "P004"],
        "name": ["Max Mustermann", "Erika Musterfrau", "John Doe", "Jane Roe"], # Sensible Daten (PII)
        "age": [45, 62, 29, 81],
        "icd_10_code": ["E11.9", "I10.90", "J45.9", "E11.9"], # z.B. Diabetes, Hypertonie, Asthma
        "biomarker_level": [1.2, 3.4, np.nan, 2.8] # np.nan simuliert unvollständige EHR-Daten
    }
    return pd.DataFrame(data)

@pytest.fixture
def mock_scheduler_config() -> dict:
    """Stellt eine Dummy-Konfiguration für den Pipeline-Scheduler bereit."""
    return {
        "timezone": "Europe/Zurich",
        "max_instances": 1,
        "coalesce": True
    }