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
def control_fan_humidity(temperature, humidity, humidity_threshold=60, min_temp=15, humidity_duty=154):
    global last_humidity_activation, humidity_active, humidity_pause_active
    current_time = time.time()

    print(f"[Luftfeuchtigkeitsregelung] Aktuelle Luftfeuchtigkeit: {humidity}%")

    # Aktivierung der Feuchtigkeitssteuerung, wenn Bedingungen erfüllt sind
    if humidity > humidity_threshold and temperature >= min_temp and not humidity_active and not humidity_pause_active:
        print(f"[Luftfeuchtigkeitsregelung] Feuchtigkeit über {humidity_threshold}% und Temperatur über {min_temp}°C. Lüfter für 2 Minuten auf 15% Leistung.")
        pwm_fan.duty(humidity_duty)  # Setze Duty Cycle auf 15% für Feuchtigkeitsregelung
        last_humidity_activation = current_time
        humidity_active = True  # Feuchtigkeitssteuerung aktiv

    # Nach 2 Minuten Feuchtigkeitssteuerung den Lüfter ausschalten und Pause beginnen
    elif humidity_active and current_time - last_humidity_activation >= 120:
        print("[Luftfeuchtigkeitsregelung] Lüfter für Feuchtigkeitssteuerung ausgeschaltet. Beginne 2 Minuten Pause.")
        last_humidity_activation = current_time  # Pausezeit starten
        humidity_active = False
        humidity_pause_active = True  # Pause aktivieren

    # Nach der 2-minütigen Pause kann die Feuchtigkeitssteuerung wieder aktiviert werden
    elif humidity_pause_active and current_time - last_humidity_activation >= 120:
        print("[Luftfeuchtigkeitsregelung] 2-Minuten-Pause beendet. Feuchtigkeitssteuerung kann erneut aktiviert werden.")
        humidity_pause_active = False

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
                    
                    # Feuchtigkeitssteuerung aufrufen, wenn keine Pause aktiv ist
                    control_fan_humidity(temperature, humidity)

                except (IndexError, ValueError) as e:
                    print("[Fehler] Fehler beim Extrahieren der Temperatur oder Luftfeuchtigkeit:", e)
            
            # Entscheidung für den Lüfter-Duty-Cycle
            if humidity_active:
                # Wenn die Feuchtigkeitssteuerung aktiv ist, aber die Temperaturregelung eine höhere Geschwindigkeit benötigt
                if temperature_priority_speed > 154:
                    pwm_fan.duty(temperature_priority_speed)
                    print(f"[Lüftersteuerung] Temperaturregelung priorisiert. Lüftergeschwindigkeit auf {temperature_priority_speed} gesetzt.")
                else:
                    # Feuchtigkeitssteuerung übernimmt bei niedrigerer Temperaturanforderung
                    pwm_fan.duty(154)
                    print("[Lüftersteuerung] Feuchtigkeitssteuerung bei 15% aktiv.")
            elif humidity_pause_active:
                # Wenn die Feuchtigkeitssteuerung pausiert, Lüfter nur ausschalten, wenn Temperaturregelung keine Geschwindigkeit vorgibt
                if temperature_priority_speed > 0:
                    pwm_fan.duty(temperature_priority_speed)
                    print(f"[Lüftersteuerung] Temperaturregelung aktiv während Feuchtigkeitspause. Lüftergeschwindigkeit auf {temperature_priority_speed} gesetzt.")
                else:
                    pwm_fan.duty(0)
                    print("[Lüftersteuerung] Feuchtigkeitspause aktiv, Lüfter ausgeschaltet.")
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
