import pyshark
import requests
import time

API_URL = "http://127.0.0.1:5000/predict"

def capture_and_predict():
    cap = pyshark.LiveCapture(interface='Wi-Fi')  # ya da 'Ethernet' / 'eth0'

    print("📡 Trafik dinleniyor... (Ctrl+C ile çık)")

    for packet in cap.sniff_continuously(packet_count=10):  # örnek 10 paket
        try:
            # Basit bir özellik vektörü (dummy örnek — değiştirilir!)
            # Gerçek sistemde bu paketlerden NSL-KDD benzeri 118 özellik üretilmeli
            features = [0] * 118

            response = requests.post(API_URL, json={"features": features})
            print("✅ API yanıtı:", response.json())
            time.sleep(1)
        except Exception as e:
            print("⚠️ Hata:", e)

capture_and_predict()
