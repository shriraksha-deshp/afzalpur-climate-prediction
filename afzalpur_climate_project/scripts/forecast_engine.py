import os
import json
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from scipy.stats import norm, gamma

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "public", "data", "raw")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "public", "data", "climate_projections_1996_2055.json")

def classify_drought(val):
    if val is None or np.isnan(val): return "Not available"
    if val >= 2.00: return "Extremely wet"
    elif val >= 1.50: return "Very wet"
    elif val >= 1.00: return "Moderately wet"
    elif val > -1.00: return "Near normal"
    elif val > -1.50: return "Moderate drought"
    elif val > -2.00: return "Severe drought"
    else: return "Extreme drought"

def cdf_to_norminv(p):
    """Standard normal inverse transformation."""
    if p <= 0.000001: return -3.0
    if p >= 0.999999: return 3.0
    return float(norm.ppf(p))

def compute_spei_glo(x, xi, alpha, kappa):
    """Computes SPEI using Generalized Logistic (GLO) distribution CDF."""
    try:
        y = 1.0 - (kappa / alpha) * (x - xi)
        if y <= 0:
            return 3.0 if kappa < 0 else -3.0
        cdf = 1.0 / (1.0 + (y ** (1.0 / kappa)))
        return round(float(cdf_to_norminv(cdf)), 3)
    except:
        return 0.0

def compute_spi_gamma(r, alpha_g, beta_g, q):
    """Computes SPI using 2-parameter Gamma distribution with zero-precip probability q."""
    try:
        if r <= 0:
            return round(float(cdf_to_norminv(q)), 3)
        g_x = gamma.cdf(r, a=alpha_g, scale=beta_g)
        h_x = q + (1.0 - q) * g_x
        return round(float(cdf_to_norminv(h_x)), 3)
    except:
        return 0.0

def train_monthly_rf(df_hist, target_col):
    """Trains a Random Forest regressor with harmonic month features and temporal lags."""
    df = df_hist[['YEAR', 'MONTH', target_col]].copy()
    df['Sin_Month'] = np.sin(2 * np.pi * df['MONTH'] / 12)
    df['Cos_Month'] = np.cos(2 * np.pi * df['MONTH'] / 12)
    df['Lag_1'] = df[target_col].shift(1)
    df['Lag_12'] = df[target_col].shift(12)
    df.dropna(inplace=True)

    X = df[['Sin_Month', 'Cos_Month', 'Lag_1', 'Lag_12']]
    y = df[target_col]

    model = RandomForestRegressor(n_estimators=250, max_depth=8, random_state=42)
    model.fit(X, y)

    # 360-month recursive forecasting (2026-2055)
    history = list(df_hist[target_col].values)
    future_vals = []
    
    for yr in range(2026, 2056):
        for m in range(1, 13):
            sin_m = np.sin(2 * np.pi * m / 12)
            cos_m = np.cos(2 * np.pi * m / 12)
            l1 = history[-1]
            l12 = history[-12]
            
            x_step = pd.DataFrame([[sin_m, cos_m, l1, l12]], columns=['Sin_Month', 'Cos_Month', 'Lag_1', 'Lag_12'])
            pred = float(model.predict(x_step)[0])
            pred = max(0.0, pred) if target_col == 'Rainfall' else pred
            
            future_vals.append({'YEAR': yr, 'MONTH': m, f'Pred_{target_col}': round(pred, 2)})
            history.append(pred)

    return pd.DataFrame(future_vals)

def main():
    spei_file = os.path.join(DATA_DIR, "SPEI_Final_1996_2025.xlsx")
    comp_file = os.path.join(DATA_DIR, "SPI_vs_SPEI_Comparison_Afzalpur_1996_2025.xlsx")

    print("[1/5] Ingesting historical monthly readings and distribution parameters...")
    df_input = pd.read_excel(spei_file, sheet_name="Input_Data")
    df_params = pd.read_excel(spei_file, sheet_name="Parameters")

    df_hist = pd.DataFrame({
        'DATE': df_input['DATE'].astype(str),
        'YEAR': pd.to_datetime(df_input['DATE']).dt.year,
        'MONTH': df_input['MONTH'],
        'Rainfall': df_input['MONTHLY RAINFALL'],
        'ETo': df_input['ETo (mm/month)'],
        'Water_Balance': df_input['WATER BALANCE']
    })

    print("[2/5] Training Random Forest models & forecasting monthly Rainfall and ETo (2026-2055)...")
    fut_rain = train_monthly_rf(df_hist, 'Rainfall')
    fut_eto = train_monthly_rf(df_hist, 'ETo')

    fut_df = fut_rain.merge(fut_eto, on=['YEAR', 'MONTH'])
    fut_df['Pred_Water_Balance'] = fut_df['Pred_Rainfall'] - fut_df['Pred_ETo']
    fut_df['DATE'] = fut_df.apply(lambda r: f"{int(r['YEAR'])}-{int(r['MONTH']):02d}-01", axis=1)

    # Combined continuous series for rectangular rolling accumulation
    comb_wb = list(df_hist['Water_Balance'].values) + list(fut_df['Pred_Water_Balance'].values)
    comb_rain = list(df_hist['Rainfall'].values) + list(fut_df['Pred_Rainfall'].values)

    print("[3/5] Calculating monthly SPEI across 1, 3, 6, 12 timescales from predicted water balance...")
    param_dict = {}
    for _, r in df_params.iterrows():
        param_dict[(int(r['Scale']), int(r['Month']))] = (r['XI'], r['ALPHA'], r['KAPPA'])

    scales = [1, 3, 6, 12]
    for k in scales:
        spei_vals = []
        for i in range(360, 720):
            acc_wb = sum(comb_wb[i - k + 1 : i + 1])
            m = fut_df.loc[i - 360, 'MONTH']
            xi, alpha, kappa = param_dict[(k, m)]
            val = compute_spei_glo(acc_wb, xi, alpha, kappa)
            spei_vals.append(val)
        fut_df[f'SPEI_{k}'] = spei_vals
        fut_df[f'SPEI_{k}_Class'] = [classify_drought(v) for v in spei_vals]

    # Calculate empirical SPI values based on rolling cumulative rainfall standardized against baseline
    print("[4/5] Calculating monthly SPI across 1, 3, 6, 12 timescales from predicted rainfall...")
    for k in scales:
        spi_vals = []
        hist_acc_k = [sum(comb_rain[j - k + 1 : j + 1]) for j in range(k - 1, 360)]
        mean_base = np.mean(hist_acc_k)
        std_base = np.std(hist_acc_k, ddof=1)
        
        for i in range(360, 720):
            acc_rain = sum(comb_rain[i - k + 1 : i + 1])
            spi_val = (acc_rain - mean_base) / std_base if std_base > 0 else 0.0
            spi_vals.append(round(float(spi_val), 3))
        fut_df[f'SPI_{k}'] = spi_vals
        fut_df[f'SPI_{k}_Class'] = [classify_drought(v) for v in spi_vals]

    # Read historical comparison workbook
    hist_compare = {}
    for k in scales:
        df_c = pd.read_excel(comp_file, sheet_name=f'Compare_{k}')
        hist_compare[k] = df_c

    # Build historical monthly dictionary
    hist_monthly = []
    for i in range(len(df_hist)):
        row_dict = {
            'DATE': df_hist.loc[i, 'DATE'],
            'YEAR': int(df_hist.loc[i, 'YEAR']),
            'MONTH': int(df_hist.loc[i, 'MONTH']),
            'Rainfall': round(float(df_hist.loc[i, 'Rainfall']), 2),
            'ETo': round(float(df_hist.loc[i, 'ETo']), 2),
            'Water_Balance': round(float(df_hist.loc[i, 'Water_Balance']), 2)
        }
        for k in scales:
            val_spei = hist_compare[k].loc[i, 'SPEI']
            val_spi = hist_compare[k].loc[i, 'SPI']
            row_dict[f'SPEI_{k}'] = round(float(val_spei), 3) if pd.notnull(val_spei) else None
            row_dict[f'SPI_{k}'] = round(float(val_spi), 3) if pd.notnull(val_spi) else None
            row_dict[f'SPEI_{k}_Class'] = classify_drought(val_spei) if pd.notnull(val_spei) else "Not available"
            row_dict[f'SPI_{k}_Class'] = classify_drought(val_spi) if pd.notnull(val_spi) else "Not available"
        hist_monthly.append(row_dict)

    # Build annual aggregations (December end-of-year indicators)
    future_annual = []
    for yr, group in fut_df.groupby('YEAR'):
        dec_row = group[group['MONTH'] == 12].iloc[0]
        future_annual.append({
            'YEAR': int(yr),
            'Pred_Rainfall_mm': round(group['Pred_Rainfall'].sum(), 2),
            'Pred_ETo_mm': round(group['Pred_ETo'].sum(), 2),
            'Pred_Water_Balance_mm': round(group['Pred_Water_Balance'].sum(), 2),
            'SPEI_1': dec_row['SPEI_1'],
            'SPEI_3': dec_row['SPEI_3'],
            'SPEI_6': dec_row['SPEI_6'],
            'SPEI_12': dec_row['SPEI_12'],
            'SPI_1': dec_row['SPI_1'],
            'SPI_3': dec_row['SPI_3'],
            'SPI_6': dec_row['SPI_6'],
            'SPI_12': dec_row['SPI_12'],
            'SPEI_12_Class': dec_row['SPEI_12_Class'],
            'SPI_12_Class': dec_row['SPI_12_Class']
        })

    hist_annual = []
    hist_comp12 = hist_compare[12][hist_compare[12]['MONTH'] == 12].sort_values('YEAR')
    for yr, group in df_hist.groupby('YEAR'):
        spei12_val = hist_comp12[hist_comp12['YEAR'] == yr]['SPEI'].values[0]
        spi12_val = hist_comp12[hist_comp12['YEAR'] == yr]['SPI'].values[0]
        hist_annual.append({
            'YEAR': int(yr),
            'Rainfall_mm': round(group['Rainfall'].sum(), 2),
            'ETo_mm': round(group['ETo'].sum(), 2),
            'Water_Balance_mm': round(group['Water_Balance'].sum(), 2),
            'SPEI_12': round(float(spei12_val), 3) if pd.notnull(spei12_val) else None,
            'SPI_12': round(float(spi12_val), 3) if pd.notnull(spi12_val) else None,
            'SPEI_12_Class': classify_drought(spei12_val),
            'SPI_12_Class': classify_drought(spi12_val)
        })

    print("[5/5] Compiling unified data payload...")
    payload = {
        "metadata": {
            "study_area": "Afzalpur Taluk, Kalaburagi District, Karnataka",
            "coordinates": {"latitude": 17.20, "longitude": 76.36},
            "methodology": "Direct GLO Distribution calculation from RF-predicted monthly water balances",
            "timescales": [1, 3, 6, 12],
            "historical_period": "1996 - 2025 (360 months)",
            "projected_period": "2026 - 2055 (360 months)"
        },
        "historical_annual": hist_annual,
        "future_annual": future_annual,
        "historical_monthly": hist_monthly,
        "future_monthly": fut_df.round(3).to_dict(orient="records")
    }

    with open(OUTPUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Calculations completed and written to: {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
