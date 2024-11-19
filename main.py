import network
import espnow
import machine
import time
import gc

# WLAN-Interface aktivieren
sta = network.WLAN(network.STA_IF)
sta.active(True)
sta.disconnect()  # Für ESP8266, um automatische Verbindungen zu vermeiden

# ESP-NOW initialisieren
e = espnow.ESPNow()
e.active(True)

# PWM für den Lüfter auf Pin 2 initialisieren (Noctua 5V Lüfter oder ein anderer)
fan_pin = machine.Pin(2)
pwm_fan = machine.PWM(fan_pin)
pwm_fan.freq(25000)  # Frequenz auf 25 kHz setzen

# Variablen für Steuerung
last_humidity_activation = time.time()
humidity_active = False
humidity_pause_active = False
temperature_priority_speed = 0
humidity_speed = 154  # Standard Duty Cycle für Feuchtigkeitssteuerung (15%)

print("[Systemstart] Warte auf eingehende Nachrichten...")

# Funktion zur Temperatursteuerung (hat immer Vorrang)
def control_fan_temperature(temperature, min_temp=18, max_temp=22, min_duty=200):
    global temperature_priority_speed
    print(f"[Temperaturregelung] Aktuelle Temperatur: {temperature}°C")

    # Berechnung der Lüfterdrehzahl für die Temperaturregelung
    if temperature < min_temp:
        temperature_priority_speed = 0
        print(f"[Temperaturregelung] Temperatur unter Minimum ({min_temp}°C). Lüfter ausgeschaltet.")
    elif temperature >= max_temp:
        temperature_priority_speed = 1023  # Maximaler Duty Cycle (100% Geschwindigkeit)
        print(f"[Temperaturregelung] Temperatur über Maximum ({max_temp}°C). Lüfter auf maximaler Geschwindigkeit (1023).")
    else:
        delta_t = temperature - min_temp
        range_temp = max_temp - min_temp
        speed = int((delta_t / range_temp) * 1023)  # Berechne PWM zwischen 0 und 1023
        if speed < min_duty:
            speed = min_duty
        temperature_priority_speed = speed
        print(f"[Temperaturregelung] Temperatur im Zielbereich. Lüftergeschwindigkeit auf {speed} gesetzt (für Temperatur: {temperature}°C)")

# Funktion zur Feuchtigkeitssteuerung
# Die Feuchtigkeitssteuerung wird aktiviert, wenn die Temperatur mindestens 15°C erreicht hat
# Wenn die Temperatur unter 15°C sinkt, bleibt die Feuchtigkeitssteuerung inaktiv, bis die Temperatur wieder mindestens 15,5°C erreicht

def control_fan_humidity(temperature, humidity, humidity_threshold=50, min_temp_activate=15, min_temp_resume=15.5):
    global last_humidity_activation, humidity_active, humidity_speed
    current_time = time.time()

    print(f"[Luftfeuchtigkeitsregelung] Aktuelle Luftfeuchtigkeit: {humidity}%")

    # Aktivierung der Feuchtigkeitssteuerung, wenn die Temperatur mindestens 15°C erreicht hat
    if humidity > humidity_threshold and temperature >= min_temp_activate:
        print(f"[Luftfeuchtigkeitsregelung] Feuchtigkeit über {humidity_threshold}%. Lüfter für Feuchtigkeitssteuerung aktiviert.")
        humidity_speed = 154  # Setze Duty Cycle auf 15% für Feuchtigkeitsregelung
        last_humidity_activation = current_time
        humidity_active = True  # Feuchtigkeitssteuerung aktiv
    elif temperature < min_temp_activate:
        # Wenn die Temperatur unter 15°C sinkt, bleibt die Feuchtigkeitssteuerung inaktiv
        humidity_active = False
        print(f"[Luftfeuchtigkeitsregelung] Temperatur unter {min_temp_activate}°C. Feuchtigkeitssteuerung inaktiv.")
    elif temperature >= min_temp_resume:
        # Wenn die Temperatur wieder auf mindestens 15,5°C steigt, kann die Feuchtigkeitssteuerung wieder aktiviert werden
        print(f"[Luftfeuchtigkeitsregelung] Temperatur hat {min_temp_resume}°C erreicht. Feuchtigkeitssteuerung kann wieder aktiviert werden.")
        humidity_active = True

    # Neue Regelung: Wenn die Temperatur über 17°C und die Luftfeuchtigkeit über 70% ist, setze Lüftergeschwindigkeit auf 25%
    if temperature > 17 and humidity > 60:
        humidity_speed = 256  # Setze Duty Cycle auf 25%
        print(f"[Luftfeuchtigkeitsregelung] Temperatur über 17°C und Feuchtigkeit über 60%. Lüftergeschwindigkeit auf 25% gesetzt.")
    else:
        humidity_speed = 154  # Standard auf 15%
        print(f"[Luftfeuchtigkeitsregelung] Standard Lüftergeschwindigkeit auf 15% gesetzt.")

# Hauptschleife
while True:
    try:
        # Empfang der Daten
        host, msg = e.recv()
        if msg:
            message = msg.decode('utf-8')  # Nachricht dekodieren
            print(f'[Nachricht] Empfangene Nachricht von {host}: {message}')
            
            if "Temperatur" in message and "Luftfeuchtigkeit" in message:
                try:
                    # Temperatur und Luftfeuchtigkeit extrahieren
                    temp_str = message.split("Temperatur: ")[1].split("C")[0]
                    hum_str = message.split("Luftfeuchtigkeit: ")[1].split("%")[0]
                    temperature = float(temp_str)
                    humidity = float(hum_str)

                    # Temperaturregelung aufrufen (immer aktiv)
                    control_fan_temperature(temperature)
                    
                    # Feuchtigkeitssteuerung aufrufen
                    control_fan_humidity(temperature, humidity)

                except (IndexError, ValueError) as e:
                    print("[Fehler] Fehler beim Extrahieren der Temperatur oder Luftfeuchtigkeit:", e)
            
            # Entscheidung für den Lüfter-Duty-Cycle
            if humidity_active:
                # Wenn die Feuchtigkeitssteuerung aktiv ist, aber die Temperaturregelung eine höhere Geschwindigkeit benötigt
                if temperature_priority_speed > humidity_speed:
                    pwm_fan.duty(temperature_priority_speed)
                    print(f"[Lüftersteuerung] Temperaturregelung priorisiert. Lüftergeschwindigkeit auf {temperature_priority_speed} gesetzt.")
                else:
                    pwm_fan.duty(humidity_speed)
                    print(f"[Lüftersteuerung] Feuchtigkeitssteuerung aktiv. Lüftergeschwindigkeit auf {humidity_speed} gesetzt.")
            else:
                # Standardfall: Temperaturregelung hat Priorität
                pwm_fan.duty(temperature_priority_speed)
                print(f"[Lüftersteuerung] Temperaturregelung. Lüftergeschwindigkeit auf {temperature_priority_speed} gesetzt.")

            # Speicherbereinigung und Überwachung
            gc.collect()
            if time.time() % 60 == 0:  # Alle 60 Sekunden
                print("[Speicher] Freier Speicher:", gc.mem_free())
                
    except Exception as e:
        print("[Fehler] Fehler im Empfangsprozess:", e)
