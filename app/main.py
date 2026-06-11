
from app.service.planner_service import PlannerService
import json
input = [
    [0.32, 0.0, 1.00],
    [0.28, 0.0, 1.00],
    [0.25, 0.2, 0.95],
    [0.22, 0.6, 0.95],
    [0.18, 1.5, 0.90],
    [0.16, 2.8, 0.85],
    [0.17, 4.0, 0.70],
    [0.21, 4.5, 0.60],
    [0.27, 3.2, 0.70],
    [0.35, 1.2, 0.85],
    [0.42, 0.4, 0.95],
    [0.48, 0.1, 0.95],
    [0.45, 0.0, 1.00],
    [0.38, 0.0, 1.00],
    [0.33, 0.0, 1.00],
    [0.29, 0.0, 1.00],
    [0.50, 5.0, 0.98]
]

def main():

    planner_service = PlannerService()
    result = planner_service.get_score(data = input)

    
    result = [rec for rec in result if rec[1] >= 0 and rec[2] >= 0]
    result.sort(key=lambda row: row[3])
    print("Rank\tPrice\tSolar\tConf\tResult")
    num = 1
    for row in result:
        print(f"{num}\t{row[0]}\t{row[1]}\t{row[2]}\t{row[3]}")
        num+=1
 


if __name__ == "__main__":
    main()