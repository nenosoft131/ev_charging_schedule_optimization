class PlannerService:

    def __init__(self):
        pass

    def get_score(self, data, P_max=9, risk_aversion=2, solar_exp=1):

        results = []

        for record in data:
            price, solar, conf = record

            if conf <= 0:
                score = float("inf")
            else:
                grid_share = (max(0, P_max - solar) / P_max) ** solar_exp
                eff_price = price * grid_share

                if eff_price < 0:
                    score = eff_price * (conf ** risk_aversion)
                else:
                    score = eff_price / conf

            results.append([price, solar, conf, score])

        return results