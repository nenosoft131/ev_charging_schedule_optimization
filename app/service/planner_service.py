from app.model.models import PlanResult, Hour
from typing import List,Tuple
import logging
logger = logging.getLogger("ev_scheduler")

class PlannerService():
    """
    EV charging planner optimization.
    """


    def plan_charging(
        self,
        forecast: List[Hour],
        current_soc_pct: float,
        target_soc_pct: float,
        capacity_kwh: float,
        max_power_kw: float,
        confidence_floor: float,
        feed_in: float = 0.08,
        solar_is_free: bool = True,
        value_of_full: float = 0.0,
    ) -> List:
        """
        Builds an optimized charging schedule based on price and solar availability.
        """

        # ------------------------------------------------------------
        # Build energy offers (solar + grid)
        # ------------------------------------------------------------

        logger.info(
            "Starting planning | SOC: %.1f → %.1f | forecast_hours=%d",
            current_soc_pct,
            target_soc_pct,
            len(forecast),
        )
        tiers = self.build_energy_tiers(forecast, max_power_kw, feed_in, solar_is_free)
        energy_to_target = max(0.0, (target_soc_pct - current_soc_pct) / 100 * capacity_kwh / confidence_floor)

        # energy_to_target = min(
        #     max(0.0, (target_soc_pct - current_soc_pct) / 100 * capacity_kwh / confidence_floor),  // If dont want to plan for more than capacity
        #     energy_to_full,
        # )
        energy_to_full = max(0.0, (100.0 - current_soc_pct) / 100 * capacity_kwh)
        allocations = [0.0] * len(forecast)
        taken = 0.0

        # ------------------------------------------------------------
        # Greedy allocation (cheapest-first)
        # ------------------------------------------------------------

        for _, raw_cost, kwh, i in tiers:
            if taken < energy_to_target:
                take = min(kwh, energy_to_target - taken, energy_to_full)
            elif raw_cost < value_of_full:
                # take = min(kwh)
                take = min(kwh, energy_to_full - taken)
            else:
                continue
                
            if take <= 0:
                continue
            allocations[i] += take
            taken += take
            if taken >= energy_to_full:
                break

        # ------------------------------------------------------------
        # Build final schedule
        # ------------------------------------------------------------
        schedule = []
        total_kwh = 0.0
        total_cost = 0.0
        
        for h, energy in zip(forecast, allocations):
            p = energy
            solar_used = min(h.solar, energy)
            grid_used = energy - solar_used
            cost = (solar_used * (0.0 if solar_is_free else feed_in)) + (grid_used * h.price)

            schedule.append({
                "hour": h.hour.isoformat().replace("+00:00", "Z"),
                "chargingPower": round(p, 2)
            })
            
            total_kwh += energy
            total_cost += cost

        # Print cost summary to console
        avg_cost = round(total_cost / total_kwh, 4) if total_kwh > 0 else 0.0
        # print(f"Total: {round(total_kwh, 2)} kWh | Cost: {round(total_cost, 2)} EUR | Avg: {avg_cost} EUR/kWh")

        logger.info(
            "Planning complete | total=%.2f kWh | cost=%.2f EUR | avg=%.4f EUR/kWh",
            total_kwh,
            total_cost,
            avg_cost,
        )

        # Return JSON-ready list
        return schedule
    
    # ------------------------------------------------------------
    # Tier builder
    # ------------------------------------------------------------
    def build_energy_tiers(
        self,
        forecast: List[Hour],
        max_power_kw: float,
        feed_in: float,
        solar_is_free: bool,
    ) -> List[Tuple[float, float, float, int]]:
        """
        Returns sorted energy opportunities:
        (adjusted_cost, raw_cost, energy_kwh, hour_index)
        """  

        tiers = []   
        EPSILON = 1e-6          

        for i, h in enumerate(forecast):

            cap = max_power_kw
            solar_kwh = min(max(h.solar, 0.0), cap)
            conf = max(h.confidence, EPSILON)
            
            # Solar Tier
            if solar_kwh > 0:
                # If solar is free than (0.0). Otherwise, use feed_in.
                solar_raw_cost = 0.0 if solar_is_free else feed_in
                tiers.append((solar_raw_cost / conf, solar_raw_cost, solar_kwh, i))
                
            # Grid Tier
            if cap - solar_kwh > 0:
                tiers.append((h.price / conf, h.price, cap - solar_kwh, i))
                
        return sorted(tiers, key=lambda tier: tier[0])

