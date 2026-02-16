from flask import Flask, render_template, jsonify
from datetime import datetime, timedelta
import random
from threading import Thread
import time

app = Flask(__name__)

# ==============================
# MEMORIA STORICA RISCHIO FRANA
# ==============================

risk_history = []          # lista di dizionari
MAX_RISK_POINTS = 360      # ~1 ora (10s * 360)


# =====================
# DATI SIMULATI
# =====================
dati_giorno = []

def genera_misurazione():
    """Genera una misurazione casuale"""
    return {
        "timestamp": datetime.now(),
        "temperature": round(random.uniform(18, 28), 1),
        "humidity": round(random.uniform(50, 80), 1),
        "pressure": round(random.uniform(1005, 1020), 1),
        "rain": round(random.uniform(0, 5), 1)  # mm di pioggia
    }

# Riempio dati iniziali simulando misurazioni distribuite nell'arco della giornata
for i in range(50):
    m = genera_misurazione()
    m["timestamp"] = datetime.now() - timedelta(minutes=(50 - i) * 10)
    dati_giorno.append(m)

# =====================
# FUNZIONI UTILI
# =====================
def calcola_medi(dati):
    if not dati:
        return {"temperature": 0, "humidity": 0, "pressure": 0, "rain": 0}

    n = len(dati)
    media_temp = round(sum(d["temperature"] for d in dati) / n, 1)
    media_hum = round(sum(d["humidity"] for d in dati) / n, 1)
    media_press = round(sum(d["pressure"] for d in dati) / n, 1)
    totale_rain = round(sum(d["rain"] for d in dati), 1)

    return {
        "temperature": media_temp,
        "humidity": media_hum,
        "pressure": media_press,
        "rain": totale_rain
    }

def calcola_rischio(medie):
    score = 0

    if medie["temperature"] > 26 or medie["temperature"] < 19:
        score += 1
    if medie["humidity"] > 75:
        score += 1
    if medie["rain"] > 10:
        score += 1

    if score == 0:
        indice = "LOW"
        spiegazione = "Temperature nella norma, bassa umidità e poca pioggia."
    elif score == 1 or score == 2:
        indice = "MEDIUM"
        spiegazione = "Condizioni leggermente critiche: una o due variabili fuori soglia."
    else:
        indice = "HIGH"
        spiegazione = "Condizioni critiche: più variabili fuori soglia, rischio elevato."

    return {"indice": indice, "spiegazione": spiegazione}

def calcola_rischio_istantaneo(dati, finestra=4):
    if len(dati) < 2:
        return {
            "indice": "LOW",
            "spiegazione": "Dati insufficienti per una valutazione istantanea affidabile."
        }

    ultimi = dati[-finestra:]

    temp_media = sum(d["temperature"] for d in ultimi) / len(ultimi)
    hum_media = sum(d["humidity"] for d in ultimi) / len(ultimi)
    rain_tot = sum(d["rain"] for d in ultimi)

    score = 0
    if temp_media > 26 or temp_media < 19:
        score += 1
    if hum_media > 75:
        score += 1
    if rain_tot > 3:
        score += 1

    if score == 0:
        indice = "LOW"
    elif score == 1:
        indice = "MEDIUM"
    else:
        indice = "HIGH"

    spiegazione = (
        f"Il rischio istantaneo è valutato come {indice} sulla base "
        f"delle ultime {len(ultimi)} misurazioni. "
        f"In questo intervallo la temperatura media è stata {temp_media:.1f} °C, "
        f"l'umidità media {hum_media:.1f} % e le precipitazioni cumulate {rain_tot:.1f} mm. "
        "Questa analisi riflette condizioni locali recenti e può variare rapidamente nel tempo."
    )

    return {"indice": indice, "spiegazione": spiegazione}

def calcola_trend(dati, finestra=6):
    if len(dati) < finestra * 2:
        return {"temperature": "→", "humidity": "→", "pressure": "→"}

    recenti = dati[-finestra:]
    precedenti = dati[-2*finestra:-finestra]

    def trend(v_recenti, v_precedenti):
        diff = sum(v_recenti)/len(v_recenti) - sum(v_precedenti)/len(v_precedenti)
        if diff > 0.3:
            return "↑"
        elif diff < -0.3:
            return "↓"
        else:
            return "→"

    return {
        "temperature": trend(
            [d["temperature"] for d in recenti],
            [d["temperature"] for d in precedenti]
        ),
        "humidity": trend(
            [d["humidity"] for d in recenti],
            [d["humidity"] for d in precedenti]
        ),
        "pressure": trend(
            [d["pressure"] for d in recenti],
            [d["pressure"] for d in precedenti]
        )
    }

def get_meteo_external_probability():
    return random.randint(20, 80)

def stima_probabilita_pioggia(medie):
    prob_api = get_meteo_external_probability()

    fattore_locale = 0
    if medie["humidity"] > 75:
        fattore_locale += 10
    if medie["pressure"] < 1010:
        fattore_locale += 10
    if medie["rain"] > 2:
        fattore_locale += 15

    prob_finale = min(prob_api + fattore_locale, 100)

    spiegazione = (
        f"La probabilità di pioggia stimata per la giornata è del {prob_finale}%. "
        f"Il valore deriva dall'integrazione di previsioni meteo esterne ({prob_api}%) "
        "con le condizioni locali misurate dalla stazione."
    )

    return {"probabilita": prob_finale, "spiegazione": spiegazione}

def calcola_probabilita_frana(dati_correnti, rischio_precedente=None):
    pioggia = dati_correnti["rain"]
    umidita = dati_correnti["humidity"]
    pressione = dati_correnti["pressure"]

    p_pioggia = min(pioggia / 100.0, 1.0)
    p_umidita = max((umidita - 60) / 40, 0)
    p_pressione = max((1015 - pressione) / 20, 0)

    probabilita = 0.5 * p_pioggia + 0.3 * p_umidita + 0.2 * p_pressione

    if rischio_precedente is not None:
        probabilita = 0.7 * rischio_precedente + 0.3 * probabilita

    probabilita = max(0, min(probabilita, 1))
    probabilita_pct = probabilita * 100

    if probabilita_pct < 33:
        classe = "LOW"
    elif probabilita_pct < 66:
        classe = "MEDIUM"
    else:
        classe = "HIGH"

    return probabilita_pct, classe


# =====================
# ROUTES
# =====================
@app.route("/")
def home():
    medie = calcola_medi(dati_giorno)
    rischio = calcola_rischio(medie)
    trend = calcola_trend(dati_giorno)
    pioggia_prevista = stima_probabilita_pioggia(medie)

    return render_template(
        "home.html",
        medie=medie,
        rischio=rischio,
        trend=trend,
        pioggia_prevista=pioggia_prevista
    )

@app.route("/dashboard")
def dashboard():
    ultimo = dati_giorno[-1] if dati_giorno else genera_misurazione()

    timestamps = [d["timestamp"].strftime("%H:%M:%S") for d in dati_giorno]
    temperature = [d["temperature"] for d in dati_giorno]
    humidity = [d["humidity"] for d in dati_giorno]
    pressure = [d["pressure"] for d in dati_giorno]
    rain = [d["rain"] for d in dati_giorno]

    return render_template(
        "dashboard.html",
        ultimo=ultimo,
        grafici={
            "timestamps": timestamps,
            "temperature": temperature,
            "humidity": humidity,
            "pressure": pressure,
            "rain": rain
        }
    )

@app.route("/risk")
def risk():
    medie = calcola_medi(dati_giorno)
    rischio = calcola_rischio(medie)
    rischio_istantaneo = calcola_rischio_istantaneo(dati_giorno)
    return render_template(
        "risk.html",
        medie=medie,
        rischio=rischio,
        rischio_istantaneo=rischio_istantaneo
    )

@app.route("/info")
def info():
    medie = calcola_medi(dati_giorno)
    ultimo = dati_giorno[-1] if dati_giorno else genera_misurazione()
    report = []

    if medie["temperature"] > 26:
        report.append("La temperatura media della giornata è elevata.")
    elif medie["temperature"] < 20:
        report.append("La temperatura media è bassa.")
    else:
        report.append("La temperatura media si mantiene nella norma.")

    if medie["humidity"] > 75:
        report.append("L'umidità relativa elevata aumenta la saturazione superficiale del terreno.")
    else:
        report.append("L'umidità media non presenta criticità particolari.")

    if medie["rain"] > 10:
        report.append(f"Le precipitazioni accumulate ({medie['rain']} mm) aumentano il rischio.")
    else:
        report.append(f"Le precipitazioni sono contenute ({medie['rain']} mm).")

    rischio_frana = calcola_rischio(medie)["indice"]

    return render_template(
        "info.html",
        medie=medie,
        ultimo=ultimo,
        analisi=report,
        rischio_frana=rischio_frana
    )

# =====================
# API JSON
# =====================
@app.route("/api/ultimo")
def api_ultimo():
    return jsonify(dati_giorno[-1] if dati_giorno else {})

@app.route("/api/medie")
def api_medie():
    return jsonify(calcola_medi(dati_giorno))

@app.route("/api/rischio")
def api_rischio():
    return jsonify(calcola_rischio(calcola_medi(dati_giorno)))

@app.route("/api/grafici")
def api_grafici():
    return jsonify({
        "timestamps": [d["timestamp"].strftime("%H:%M:%S") for d in dati_giorno],
        "temperature": [d["temperature"] for d in dati_giorno],
        "humidity": [d["humidity"] for d in dati_giorno],
        "pressure": [d["pressure"] for d in dati_giorno],
        "rain": [d["rain"] for d in dati_giorno]
    })

# ======= AGGIUNTO: API TREND RISCHIO FRANA =======
@app.route("/api/rischio/trend")
def api_trend_rischio():
    return jsonify(risk_history)

# =====================
# THREAD BACKGROUND
# =====================
def aggiorna_dati_simulati():
    while True:
        nuovo_dato = genera_misurazione()
        dati_giorno.append(nuovo_dato)
        if len(dati_giorno) > 100:
            dati_giorno.pop(0)

        # ======= AGGIUNTO: aggiornamento rischio frana =======
        rischio_precedente = (
            risk_history[-1]["probabilita"] / 100
            if risk_history else None
        )

        probabilita, classe = calcola_probabilita_frana(
            nuovo_dato,
            rischio_precedente
        )

        risk_history.append({
            "timestamp": nuovo_dato["timestamp"].strftime("%H:%M:%S"),
            "probabilita": probabilita,
            "classe": classe
        })

        if len(risk_history) > MAX_RISK_POINTS:
            risk_history.pop(0)

        time.sleep(10)

# =====================
# RUN SERVER
# =====================
if __name__ == "__main__":
    Thread(target=aggiorna_dati_simulati, daemon=True).start()
    app.run(debug=True)

