"""
Clinical Data Pipeline Package.

Dieses Modul stellt die Infrastruktur für automatisierte Datenverarbeitung,
prädiktive Modellierung und Orchestrierung im klinischen Umfeld bereit.
Alle Kernkomponenten sind so konzipiert, dass sie DSGVO-konform und 
fehlertolerant arbeiten.
"""

# Exponieren der Hauptklasse für einen sauberen und einfachen Import
# an anderer Stelle (z. B.: from src import ClinicalPipelineScheduler)
from .scheduler import ClinicalPipelineScheduler

# Definition von Metadaten für das Package
__version__ = "1.0.0"
__author__ = "HealthData Architecture Team"

# __all__ definiert explizit, was importiert wird, wenn jemand 
# `from src import *` aufruft. Dies verhindert Namespace-Pollution.
__all__ = [
    "ClinicalPipelineScheduler",
]