from typing import List, Tuple
from models import ZHAWModule

def find_time_conflicts(modules: List[ZHAWModule]) -> List[Tuple[ZHAWModule, ZHAWModule]]:
    """Prüft eine Liste von Modulen auf zeitliche Überschneidungen am selben Tag."""
    conflicts = []
    
    # Nach Wochentag gruppieren, um Vergleiche zu minimieren
    days = set(m.wochentag for m in modules)
    
    for day in days:
        daily_modules = [m for m in modules if m.wochentag == day]
        # Sortieren nach Startzeit
        daily_modules.sort(key=lambda x: x.startzeit)
        
        # Algorithmus zur Konflikterkennung (O(N log N) wegen der Sortierung)
        for i in range(len(daily_modules) - 1):
            current_mod = daily_modules[i]
            next_mod = daily_modules[i + 1]
            
            # Überschneidung liegt vor, wenn das aktuelle Modul nach dem Start des nächsten endet
            if current_mod.endzeit > next_mod.startzeit:
                conflicts.append((current_mod, next_mod))
                
    return conflicts