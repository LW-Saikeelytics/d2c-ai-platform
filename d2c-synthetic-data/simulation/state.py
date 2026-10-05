from dataclasses import dataclass, field
from typing import Dict, Any, List
from datetime import date, timedelta


@dataclass
class SimulationState:

    # --------------------------------------------------
    # SIMULATION CLOCK
    # --------------------------------------------------

    current_day: int = 1
    current_date: date | None = None

    # --------------------------------------------------
    # CORE PERSISTENT STATE
    # --------------------------------------------------

    customers: Dict[str, Dict[str, Any]] = field(
        default_factory=dict
    )

    inventory: Dict[str, Dict[str, int]] = field(
        default_factory=dict
    )

    orders: Dict[str, Dict[str, Any]] = field(
        default_factory=dict
    )

    events: Dict[str, Dict[str, Any]] = field(
        default_factory=dict
    )

    active_deliveries: Dict[str, Dict[str, Any]] = field(
        default_factory=dict
    )

    # --------------------------------------------------
    # CUSTOMER / BEHAVIOR HISTORY
    # --------------------------------------------------

    customer_history: Dict[str, Dict[str, Any]] = field(
        default_factory=dict
    )

    behavior_history: List[Dict[str, Any]] = field(
        default_factory=list
    )

    conversion_history: List[Dict[str, Any]] = field(
        default_factory=list
    )

    # --------------------------------------------------
    # DAILY TEMPORARY STATE
    # --------------------------------------------------

    daily_events: List[Dict[str, Any]] = field(
        default_factory=list
    )

    daily_behaviors: List[Dict[str, Any]] = field(
        default_factory=list
    )

    daily_conversions: List[Dict[str, Any]] = field(
        default_factory=list
    )

    daily_orders: List[Dict[str, Any]] = field(
        default_factory=list
    )

    # --------------------------------------------------
    # DAILY SUMMARY HISTORY
    # --------------------------------------------------

    daily_metrics: List[Dict[str, Any]] = field(
        default_factory=list
    )

    # --------------------------------------------------
    # GLOBAL COUNTERS
    # --------------------------------------------------

    counters: Dict[str, int] = field(
        default_factory=lambda: {
            "customer": 0,
            "order": 0,
            "event": 0
        }
    )

    # --------------------------------------------------
    # DAILY STATE MANAGEMENT
    # --------------------------------------------------

    def reset_daily_state(self) -> None:
        """
        Clears only temporary state used during the current simulation day.

        Persistent history is intentionally preserved.
        """

        self.daily_events.clear()
        self.daily_behaviors.clear()
        self.daily_conversions.clear()
        self.daily_orders.clear()

    # --------------------------------------------------
    # SIMULATION CLOCK
    # --------------------------------------------------

    def advance_day(self) -> None:
        """
        Advance the simulation by one day.
        """

        self.current_day += 1

        if self.current_date is not None:
            self.current_date += timedelta(days=1)