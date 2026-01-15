import yaml
import sys
import os


sys.path.append(os.path.join(os.path.dirname(__file__)))

from data_loader import load_mortality_data
from engine import MarginOptimizer, LifePolicy # Import LifePolicy


current_dir = os.path.dirname(os.path.abspath(__file__))
settings_path = os.path.join(current_dir, "settings.yaml")

with open(settings_path, "r") as f:
    config = yaml.safe_load(f)


mortality_lookup = load_mortality_data("VBT_2015.xlsx", "Sheet1")


policy = LifePolicy(mortality_lookup, config['product_B'])

policy.run()

print(policy.summary_metrics(verbose=True))

optimizer_B = MarginOptimizer(policy)
best_premium = optimizer_B.solve_for_premium(target_margin=0.07)

#print(f"Optimal Premium: {best_premium}")