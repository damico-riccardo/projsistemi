// ==========================
// dashboard.js
// ==========================

// Funzioni helper
function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.innerText = text;
}

function setRiskBadge(risk) {
    const badge = document.getElementById("riskBadge");
    if (!badge) return;
    badge.innerText = risk.toUpperCase();
    badge.className = "risk " + risk.toLowerCase();
}

// Aggiorna le card con i valori in tempo reale
function updateDashboard(data) {
    setText("tempValue", data.temperature + " °C");
    setText("humValue", data.humidity + " %");
    setText("pressValue", data.pressure + " hPa");
    setText("windValue", data.wind || "-- km/h");
    setText("rainValue", data.rain || "-- mm");
    setRiskBadge(data.risk || "low");
}

// Fetch dati ultimi valori
function aggiornaValori() {
    fetch("/api/ultimo")
        .then(res => res.json())
        .then(data => {
            fetch("/api/rischio")
                .then(res => res.json())
                .then(riskData => {
                    updateDashboard({
                        temperature: data.temperature,
                        humidity: data.humidity,
                        pressure: data.pressure,
                        wind: data.wind || "--",
                        rain: data.rain,
                        risk: riskData.indice
                    });
                });
        })
        .catch(err => console.error("Errore fetch valori:", err));
}

// Fetch dati grafici
function aggiornaGrafici() {
    fetch("/api/grafici")
        .then(res => res.json())
        .then(data => {
            Plotly.react('tempGraph', [{
                x: data.timestamps,
                y: data.temperature,
                type: 'scatter',
                mode: 'lines+markers',
                line: { color: '#38bdf8' },
                name: 'Temperatura °C'
            }]);

            Plotly.react('humGraph', [{
                x: data.timestamps,
                y: data.humidity,
                type: 'scatter',
                mode: 'lines+markers',
                line: { color: '#facc15' },
                name: 'Umidità %'
            }]);

            Plotly.react('pressGraph', [{
                x: data.timestamps,
                y: data.pressure,
                type: 'scatter',
                mode: 'lines+markers',
                line: { color: '#22c55e' },
                name: 'Pressione hPa'
            }]);
        })
        .catch(err => console.error("Errore fetch grafici:", err));
}

// Inizializzazione al caricamento pagina
document.addEventListener("DOMContentLoaded", () => {
    aggiornaValori();
    aggiornaGrafici();
    setInterval(aggiornaValori, 10000);
    setInterval(aggiornaGrafici, 10000);
});
