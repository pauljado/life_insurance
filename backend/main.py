import yaml
from data_loader import load_mortality_data
from engine import MarginOptimizer

# 1. Load Settings
with open("settings.yaml", "r") as f:
    config = yaml.safe_load(f)

# 2. Load Data
mortality_lookup = load_mortality_data("VBT_2015.xlsx", "Sheet1")

# 3. Execute Engine
optimizer_A = MarginOptimizer(config['product_A'])
best_premium = optimizer_A.solve_for_premium(target_margin=0.07)

print(f"Optimal Premium: {best_premium}")