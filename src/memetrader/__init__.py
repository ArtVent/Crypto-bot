"""memetrader – gefilterter Momentum-Bot für pump.fun-Launches.

Design-Entscheidungen aus der Wissensdatenbank dieses Repos:
- KEIN Block-0-Sniping (docs/strategien.md 3.1: Latenz-Arena, für Heim-Setups
  strukturell verloren) – Einstieg erst nach Beobachtungsfenster.
- Filter zuerst (docs/filter-engine.md: der Filter IST der Edge).
- Asymmetrische Exits + Kill-Switch (docs/strategien.md, Abschnitt 4 –
  ohne sie dreht kein Filter das Vorzeichen).
- Paper-Modus als Default; Live-Trading ist expliziter Opt-in, Key nur lokal.

Ehrliche Erwartung (docs/fee-oekonomie.md, docs/ai-und-memecoins.md):
Die Mehrheit der Teilnehmer in diesem Markt verliert. Dieses Programm ist ein
Experiment mit Verlust-Deckel, keine Gelddruckmaschine.
"""

__version__ = "0.1.0"
