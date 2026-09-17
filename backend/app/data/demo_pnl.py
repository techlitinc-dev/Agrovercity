# P&L demo data — flutter-prototype/ is absent from this repo, so values are realistic
# stand-ins consistent with the prototype's Wheat/Onion P&L shape (diff if it appears).
DEMO_CROPS = [
    {
        "id": "crop-wheat",
        "name": "Wheat",
        "season": "Rabi",
        "area": 4.0,
        "yieldQuintals": 40,
        "marketAvgRate": 2275,
        "grossRevenue": 91000,
        "totalExpenses": 50000,
        "netProfit": 41000,
        "roiPercent": 82.0,
        "expensesBreakdown": [
            {"category": "seeds", "amount": 12000},
            {"category": "fertilizer", "amount": 18000},
            {"category": "labor", "amount": 15000},
            {"category": "irrigation", "amount": 5000},
        ],
    },
    {
        "id": "crop-onion",
        "name": "Onion",
        "season": "Rabi",
        "area": 2.0,
        "yieldQuintals": 30,
        "marketAvgRate": 1850,
        "grossRevenue": 55500,
        "totalExpenses": 34000,
        "netProfit": 21500,
        "roiPercent": 63.2,
        "expensesBreakdown": [
            {"category": "seeds", "amount": 8000},
            {"category": "fertilizer", "amount": 12000},
            {"category": "labor", "amount": 10000},
            {"category": "irrigation", "amount": 4000},
        ],
    },
]
