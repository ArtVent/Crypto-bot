"""memescan – Sicherheits-Filter-Engine für Memecoins.

Defensive Token-Prüfung (Rug-/Scam-Erkennung) auf Basis der Wissensdatenbank
dieses Repos: docs/filter-engine.md definiert die Regeln, data/filter-features.json
die Features, data/detection-apis.json die Datenquellen.
"""

__version__ = "0.1.0"

from .models import RiskFlag, Severity, TokenReport, Verdict, VerdictResult
from .engine import evaluate

__all__ = ["RiskFlag", "Severity", "TokenReport", "Verdict", "VerdictResult", "evaluate"]
