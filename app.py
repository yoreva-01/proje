from flask import Flask, request, jsonify, render_template, Response
import joblib
import numpy as np
import time
import psycopg2
import os
from datetime import datetime
import csv
import logging


# -------------------------------
# Flask uygulamasını başlat
app = Flask(__name__)

# -------------------------------
# Modeli yükle
model = joblib.load('model_v1.pkl')

# -------------------------------
# Veritabanı bağlantısı (Docker uyumlu)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "ai_ids_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "aa1bb2cc3")

time.sleep(5)  # Veritabanı hazır olana kadar bekle
# PostgreSQL veritabanına bağlan

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cursor = conn.cursor()

# -------------------------------
# Log dosyası
logging.basicConfig(filename="attack_log.txt", level=logging.WARNING)

# -------------------------------
# Tabloyu oluştur (yoksa)
cursor.execute("""
CREATE TABLE IF NOT EXISTS predictions (
    id SERIAL PRIMARY KEY,
    features FLOAT[],
    prediction INTEGER,
    label TEXT,
    timestamp TIMESTAMP
)
""")
conn.commit()

# -------------------------------
# Ana sayfa
@app.route('/')
def home():
    return "AI Destekli IDS Flask API çalışıyor."

# -------------------------------
# Web arayüz (dashboard)
@app.route('/dashboard')
def dashboard():
    cursor.execute("SELECT id, prediction, label, timestamp FROM predictions ORDER BY id DESC LIMIT 10")
    rows = cursor.fetchall()
    return render_template('index.html', rows=rows)

# -------------------------------
# Tahmin endpoint'i
@app.route('/predict', methods=['POST'])
def predict():
    try:
        data = request.get_json()
        features = np.array(data['features']).reshape(1, -1)
        prediction = model.predict(features)[0]
        label = 'attack' if prediction == 1 else 'normal'

        # Veritabanına kayıt
        cursor.execute("""
            INSERT INTO predictions (features, prediction, label, timestamp)
            VALUES (%s, %s, %s, %s)
        """, (list(data['features']), int(prediction), label, datetime.now()))
        conn.commit()

        # Saldırı logu
        if prediction == 1:
            logging.warning(f"Saldırı tespit edildi! Features: {data['features']}")

        return jsonify({
            'prediction': int(prediction),
            'label': label
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 400

# -------------------------------
# CSV dışa aktarma
@app.route('/export_csv')
def export_csv():
    cursor.execute("SELECT id, features, prediction, label, timestamp FROM predictions ORDER BY timestamp DESC")
    records = cursor.fetchall()

    def generate():
        data = csv.writer()
        header = ['id', 'features', 'prediction', 'label', 'timestamp']
        yield ','.join(header) + '\n'
        for row in records:
            features_str = '[' + ','.join(map(str, row[1])) + ']'
            csv_row = [str(row[0]), features_str, str(row[2]), row[3], str(row[4])]
            yield ','.join(csv_row) + '\n'

    return Response(generate(), mimetype='text/csv',
                    headers={"Content-Disposition": "attachment; filename=ids_predictions.csv"})

# -------------------------------
# Toplam sayıları döndür (dashboard için)
@app.route('/stats')
def stats():
    cursor.execute("SELECT label, COUNT(*) FROM predictions GROUP BY label")
    rows = cursor.fetchall()
    result = {'normal': 0, 'attack': 0}
    for label, count in rows:
        result[label] = count
    return jsonify(result)

# -------------------------------
# Saatlik grafik verisi
@app.route('/hourly_stats')
def hourly_stats():
    cursor.execute("""
        SELECT
            date_trunc('hour', timestamp) AS hour,
            label,
            COUNT(*) AS count
        FROM predictions
        WHERE timestamp > NOW() - INTERVAL '1 day'
        GROUP BY hour, label
        ORDER BY hour
    """)
    rows = cursor.fetchall()

    hourly_data = {}
    for hour, label, count in rows:
        hour_str = hour.strftime('%Y-%m-%d %H:%M')
        if hour_str not in hourly_data:
            hourly_data[hour_str] = {'normal': 0, 'attack': 0}
        hourly_data[hour_str][label] = count

    return jsonify(hourly_data)

# -------------------------------
# Uygulamayı başlat
if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True)
