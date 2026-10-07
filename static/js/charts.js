let barChart = null;
let rangeChart = null;
let sweepChart = null;

function initCharts() {
    // 1. RCS Bar Chart
    const ctxBar = document.getElementById('barChart').getContext('2d');
    barChart = new Chart(ctxBar, {
        type: 'bar',
        data: {
            labels: ['Bare Asset (Uncoated)', 'RAM Coated Asset'],
            datasets: [{
                label: 'Radar Cross Section (dBsm)',
                data: [0, 0],
                backgroundColor: ['#ef4444', '#10b981'],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: { title: { display: true, text: 'RCS in dBsm (Lower is Stealther)' } }
            }
        }
    });

    // 2. Detection Probability vs Range Curve
    const ctxRange = document.getElementById('rangeChart').getContext('2d');
    rangeChart = new Chart(ctxRange, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Uncoated',
                    data: [],
                    borderColor: '#ef4444',
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    fill: true,
                    tension: 0.3
                },
                {
                    label: 'With Stealth Coating',
                    data: [],
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    fill: true,
                    tension: 0.3
                }
            ]
        },
        options: {
            responsive: true,
            scales: {
                y: { beginAtZero: true, max: 100, title: { display: true, text: 'Detection Probability (%)' } },
                x: { title: { display: true, text: 'Radar Range' } }
            }
        }
    });

    // 3. Angular Sweep Response Curve (Locked to compact container height)
    const ctxSweep = document.getElementById('sweepChart').getContext('2d');
    sweepChart = new Chart(ctxSweep, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Bare CST Solver Curve',
                    data: [],
                    borderColor: '#f97316',
                    borderWidth: 2,
                    pointRadius: 2,
                    fill: false
                },
                {
                    label: 'Coated Response',
                    data: [],
                    borderColor: '#38bdf8',
                    borderWidth: 2,
                    pointRadius: 2,
                    fill: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false, // Prevents excessive height stretching
            scales: {
                x: { title: { display: true, text: 'Azimuth Angle (Degrees)' } },
                y: { title: { display: true, text: 'RCS (dBsm)' } }
            }
        }
    });
}

function updateHistoryTable(historyList) {
    const tbody = document.getElementById('historyTableBody');
    if (!historyList || historyList.length === 0) return;

    tbody.innerHTML = '';
    historyList.forEach(item => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><code>${item.timestamp}</code></td>
            <td><strong>${item.asset}</strong></td>
            <td>${item.coating}</td>
            <td>${item.angle}</td>
            <td><span class="badge">${item.bare_dbsm} dBsm</span></td>
            <td><span class="badge badge-success">${item.coated_dbsm} dBsm</span></td>
            <td><span class="badge badge-accent">${item.reduction_db} dB</span></td>
            <td><strong style="color: #10b981;">${item.power_absorbed}</strong></td>
        `;
        tbody.appendChild(tr);
    });
}

async function runSimulation() {
    const asset = document.getElementById('assetSelect').value;
    const coating = document.getElementById('coatingSelect').value;
    const angle = document.getElementById('angleSelect').value;

    try {
        const response = await fetch('/api/simulate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ asset: asset, coating: coating, angle: angle })
        });
        const res = await response.json();

        if (res.status === 'success') {
            // Update Metric Badges
            document.getElementById('mBare').textContent = res.rcs_bare_db + ' dBsm';
            document.getElementById('mCoated').textContent = res.rcs_coated_db + ' dBsm';
            document.getElementById('mDelta').textContent = res.delta_db + ' dB';
            document.getElementById('mAbs').textContent = res.power_absorbed_pct + ' %';
            document.getElementById('mArea').textContent = res.sigma_coated_m2 + ' m²';

            // 1. Update Bar Chart
            barChart.data.datasets[0].data = [res.rcs_bare_db, res.rcs_coated_db];
            barChart.update();

            // 2. Update Range Curve
            rangeChart.data.labels = res.ranges;
            rangeChart.data.datasets[0].data = res.prob_uncoated;
            rangeChart.data.datasets[1].data = res.prob_coated;
            rangeChart.update();

            // 3. Update Azimuth Sweep Curve
            if (res.sweep_angles && res.sweep_angles.length > 0) {
                sweepChart.data.labels = res.sweep_angles.map(a => a + '°');
                sweepChart.data.datasets[0].data = res.sweep_bare;
                sweepChart.data.datasets[1].data = res.sweep_coated;
                sweepChart.update();
            }

            // 4. Update History Table
            updateHistoryTable(res.history);
        }
    } catch (err) {
        console.error("Simulation error:", err);
    }
}

function exportDataCSV() {
    window.location.href = '/api/export-csv';
}

window.onload = () => {
    initCharts();
    runSimulation();
};