import pytest
# Wir importieren über die definierte Public API aus dem src-Package
from src import ClinicalPipelineScheduler

def test_scheduler_initialization(mock_scheduler_config):
    """
    Testet die korrekte Initialisierung des Schedulers unter 
    Verwendung der Fixture-Konfiguration.
    """
    # Arrange & Act
    scheduler = ClinicalPipelineScheduler(config=mock_scheduler_config)
    
    # Assert
    assert scheduler is not None, "Scheduler-Instanz durfte nicht None sein."
    # Annahme: is_running ist ein Property der Klasse
    assert scheduler.is_running is False, "Scheduler sollte initial nicht laufen."
    assert scheduler.config["timezone"] == "Europe/Zurich"

def test_scheduler_starts_and_stops():
    """Prüft das Lifecycle-Management des Schedulers."""
    scheduler = ClinicalPipelineScheduler()
    
    scheduler.start()
    assert scheduler.is_running is True
    
    scheduler.stop()
    assert scheduler.is_running is False