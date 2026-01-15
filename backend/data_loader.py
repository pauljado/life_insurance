import pandas as pd
from pathlib import Path

# Loads data from provided VBT Excel file and creates a map of Age/Policy duration -> Mortality
def load_mortality_data(file_name, sheet_name):

  data_dir = Path("C:/Users/paula/PythonCoding/life_insurance/data")
  file_path = data_dir / file_name

  df_raw_vbt = pd.read_excel(file_path, sheet_name=sheet_name, header=None)

  header_row_idx = df_raw_vbt[df_raw_vbt[0] == r"Row\Column"].index[0]
  df_vbt = pd.read_excel(file_path, sheet_name=sheet_name, header = header_row_idx)

  df_vbt = df_vbt.rename(columns={r"Row\Column": "Issue_Age"})
  df_vbt = df_vbt[pd.to_numeric(df_vbt["Issue_Age"], errors='coerce').notnull()]

  df_vbt["Issue_Age"] = df_vbt["Issue_Age"].astype(int)
  df_vbt = df_vbt.dropna()

  df_long = df_vbt.melt(
    id_vars=["Issue_Age"],
    var_name="Duration",
    value_name="Mortality_Rate"
  )

  df_long["Duration"] = pd.to_numeric(df_long["Duration"], errors='coerce')
  # Convert Mortality_Rate to numeric type
  df_long["Mortality_Rate"] = pd.to_numeric(df_long["Mortality_Rate"], errors='coerce')

  mortality_map = df_long.set_index(["Issue_Age", "Duration"])["Mortality_Rate"].to_dict()

  print(f"Loading data from {file_name}...")
  return mortality_map