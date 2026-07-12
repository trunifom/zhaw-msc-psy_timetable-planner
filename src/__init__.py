"""
Stundenplan Planner Package.

Dieses Modul stellt die Kernarchitektur für die Erstellung, 
Verwaltung und Ressourcen-Optimierung (Räume, Lehrkräfte, Klassen) 
von Stundenplänen zur Verfügung.
"""

# 1. Metadaten des Pakets
__version__ = "0.1.0"
__author__ = "Dein Name"

# 2. Imports für das Facade-Pattern
# Anwender können nun `from planner import Timetable` nutzen, 
# statt `from planner.scheduler import Timetable`
from .models import Course, Room, Teacher, TimeSlot
from .scheduler import Timetable, ScheduleOptimizer
from .export import export_timetable_to_pdf, export_to_csv

# 3. Öffentliche API definieren
# Schützt vor unerwünschten Importen bei `from planner import *`
__all__ = [
    "Course",
    "Room",
    "Teacher",
    "TimeSlot",
    "Timetable",
    "ScheduleOptimizer",
    "export_timetable_to_pdf",
    "export_to_csv",
]