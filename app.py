import os
import math
import csv
import io
from datetime import datetime
import pandas as pd
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, Response

app = Flask(__name__)
app.secret_key = "defense_stealth_classified_key"

# In-memory history ledger (keeps recent runs across the session)
SIMULATION_HISTORY = []

# 1. Load Zenodo CSV
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'data', 'drone_rcs_data.csv')

df = None
if os.path.exists(DATA_FILE):
    try:
        df = pd.read_csv(DATA_FILE)
        if len(df.columns) <= 1:
            df = pd.read_csv(DATA_FILE, sep=';')
    except Exception:
        df = pd.read_csv(DATA_FILE, sep=';')

    df.columns = [c.strip().replace('"', '').replace("'", "") for c in df.columns]

def get_col(possible_names):
    if df is None:
        return None
    for name in possible_names:
        for c in df.columns:
            if name.lower() in c.lower():
                return c
    return None

COL_PHI = get_col(['phi', 'angle', 'deg'])
COL_BARE = get_col(['cst', 'bare', 'uncoated', 'rcs_cst_db'])
COL_PRED = get_col(['pred', 'coated', 'rcs_pred'])
COL_DELTA = get_col(['delta', 'diff'])

# Standard physical baseline benchmark cross-sections
ASSET_CATALOG = {
    "Tactical UAV / Drone (Real Research Model)": {"base_dbsm": -14.8, "base_m2": 0.0331},
    "Conventional Fighter Aircraft": {"base_dbsm": 6.99, "base_m2": 5.0},
    "Cruise Missile": {"base_dbsm": -3.01, "base_m2": 0.5},
    "Naval Destroyer": {"base_dbsm": 40.0, "base_m2": 10000.0}
}

# Real material attenuation
COATING_CATALOG = {
    "Polypyrrole Nanotubes (PPy-NT) - Real Dataset": {"mat_delta_db": -3.10},
    "Carbon Nanotube (CNT) Epoxy Matrix": {"mat_delta_db": -18.70},
    "Graphene Nanoplatelet (GNP) Thin Film": {"mat_delta_db": -22.40},
    "Ni-Zn Ferrite Spinel Composite": {"mat_delta_db": -14.20}
}

@app.route('/')
def root():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if (username == 'admin' and password == 'password123') or (username and password):
            session['user'] = username
            return redirect(url_for('dashboard'))
        return render_template('login.html', error="Invalid Credentials")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))

    angles = []
    if df is not None and COL_PHI in df.columns:
        angles = [int(float(x)) for x in df[COL_PHI].dropna().tolist()][:91]
    if not angles:
        angles = list(range(0, 91, 2))

    return render_template('dashboard.html',
                           username=session.get('user', 'Operator'),
                           assets=list(ASSET_CATALOG.keys()),
                           coatings=list(COATING_CATALOG.keys()),
                           angles=angles)

@app.route('/api/simulate', methods=['POST'])
def simulate():
    data = request.get_json() or {}
    asset_name = data.get('asset', list(ASSET_CATALOG.keys())[0])
    coating_name = data.get('coating', list(COATING_CATALOG.keys())[0])
    selected_angle = float(data.get('angle', 0))

    asset_info = ASSET_CATALOG.get(asset_name, ASSET_CATALOG["Tactical UAV / Drone (Real Research Model)"])
    coating_info = COATING_CATALOG.get(coating_name, COATING_CATALOG["Polypyrrole Nanotubes (PPy-NT) - Real Dataset"])

    # 1. Extract real values for the selected azimuth angle from the CSV
    row = df.loc[df[COL_PHI].astype(float) == selected_angle] if (df is not None and COL_PHI in df.columns) else pd.DataFrame()
    if not row.empty:
        dataset_bare_db = float(row.iloc[0][COL_BARE])
        dataset_delta_db = float(row.iloc[0][COL_DELTA]) if COL_DELTA in row.iloc[0] else -3.10
    else:
        dataset_bare_db = -14.80
        dataset_delta_db = -3.10

    # 2. Angle variation relative to head-on (phi = 0 deg)
    head_on_bare = float(df[COL_BARE].iloc[0]) if (df is not None and COL_BARE in df.columns) else -14.80
    angular_fluctuation = dataset_bare_db - head_on_bare

    # 3. Compute Bare RCS
    rcs_bare_db = round(asset_info["base_dbsm"] + angular_fluctuation, 2)

    # 4. Compute Attenuation (ΔdB)
    if "Real Dataset" in coating_name:
        delta_db = round(dataset_delta_db, 2)
    else:
        delta_db = round(coating_info["mat_delta_db"] * (abs(dataset_delta_db) / 3.10), 2)

    # 5. Compute Coated RCS
    rcs_coated_db = round(rcs_bare_db + delta_db, 2)

    # 6. Physical conversions
    sigma_bare_m2 = round(10.0 ** (rcs_bare_db / 10.0), 5)
    sigma_coated_m2 = round(10.0 ** (rcs_coated_db / 10.0), 5)
    power_absorbed_pct = round((1.0 - (10.0 ** (delta_db / 10.0))) * 100, 2)

    # 7. Radar Range Detection Probability
    if "Destroyer" in asset_name:
        ranges = [20, 40, 60, 80, 100, 120, 140, 160]
        k_radar = 18.0
    elif "Fighter" in asset_name:
        ranges = [10, 20, 30, 40, 50, 60, 70, 80]
        k_radar = 30.0
    else:
        ranges = [5, 10, 15, 20, 25, 30, 35, 40]
        k_radar = 35.0

    r50_uncoated = k_radar * (max(sigma_bare_m2, 0.00001) ** 0.25)
    r50_coated = k_radar * (max(sigma_coated_m2, 0.00001) ** 0.25)

    prob_uncoated = []
    prob_coated = []
    for r in ranges:
        pu = 1.0 / (1.0 + (r / max(r50_uncoated, 0.01)) ** 4)
        pc = 1.0 / (1.0 + (r / max(r50_coated, 0.01)) ** 4)
        prob_uncoated.append(round(pu * 100, 1))
        prob_coated.append(round(pc * 100, 1))

    # 8. Full Azimuth Angle Sweep Curve (0 deg to 90 deg)
    sweep_df = df.iloc[:46] if (df is not None and len(df) >= 46) else df
    sweep_angles = [int(float(x)) for x in sweep_df[COL_PHI]]
    sweep_bare = [round(asset_info["base_dbsm"] + (float(x) - head_on_bare), 2) for x in sweep_df[COL_BARE]]
    sweep_coated = [round(b + delta_db, 2) for b in sweep_bare]

    # Log this run into history (keep latest 8 runs)
    timestamp_str = datetime.now().strftime("%H:%M:%S")
    history_entry = {
        "timestamp": timestamp_str,
        "asset": asset_name.split('(')[0].strip(),
        "coating": coating_name.split('(')[0].strip(),
        "angle": f"{int(selected_angle)}°",
        "bare_dbsm": rcs_bare_db,
        "coated_dbsm": rcs_coated_db,
        "reduction_db": delta_db,
        "power_absorbed": f"{power_absorbed_pct}%"
    }
    SIMULATION_HISTORY.insert(0, history_entry)
    if len(SIMULATION_HISTORY) > 8:
        SIMULATION_HISTORY.pop()

    return jsonify({
        "status": "success",
        "asset": asset_name,
        "coating": coating_name,
        "angle_deg": selected_angle,
        "rcs_bare_db": rcs_bare_db,
        "rcs_coated_db": rcs_coated_db,
        "sigma_bare_m2": sigma_bare_m2,
        "sigma_coated_m2": sigma_coated_m2,
        "delta_db": delta_db,
        "power_absorbed_pct": power_absorbed_pct,
        "ranges": [f"{r} km" for r in ranges],
        "prob_uncoated": prob_uncoated,
        "prob_coated": prob_coated,
        "sweep_angles": sweep_angles,
        "sweep_bare": sweep_bare,
        "sweep_coated": sweep_coated,
        "history": SIMULATION_HISTORY
    })

# Export Feature: Download CSV Report
@app.route('/api/export-csv')
def export_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Timestamp", "Platform Asset", "RAM Coating Formulation", "Azimuth Angle", "Bare RCS (dBsm)", "Coated RCS (dBsm)", "Delta Attenuation (dB)", "Reflected Power Absorbed"])
    for h in SIMULATION_HISTORY:
        writer.writerow([h["timestamp"], h["asset"], h["coating"], h["angle"], h["bare_dbsm"], h["coated_dbsm"], h["reduction_db"], h["power_absorbed"]])
    
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=Stealth_Coating_Evaluation_Report.csv"}
    )

if __name__ == '__main__':
    app.run(debug=True, port=5000)