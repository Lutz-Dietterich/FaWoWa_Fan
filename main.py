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

# Funktion zum Steuern des PWM-Lüfters basierend auf der Temperatur
def control_fan(temperature, min_temp=18, max_temp=22, min_duty=200):
    if temperature < min_temp:
        pwm_fan.duty(0)
        print(f"Lüfter ausgeschaltet, Temperatur: {temperature}°C")
    elif temperature >= max_temp:
        pwm_fan.duty(1023)  # Maximaler Duty Cycle (100% Geschwindigkeit)
        print(f"Lüfter auf maximaler Geschwindigkeit (1023) bei Temperatur: {temperature}°C")
    else:
        delta_t = temperature - min_temp
        range_temp = max_temp - min_temp
        speed = int((delta_t / range_temp) * 1023)  # Berechne PWM zwischen 0 und 1023
        # Mindestgeschwindigkeit setzen
        if speed < min_duty:
            speed = min_duty
        pwm_fan.duty(speed)
        print(f"Lüftergeschwindigkeit gesetzt auf: {speed} (für Temperatur: {temperature}°C)")

# Funktion zur Steuerung des Lüfters basierend auf Luftfeuchtigkeit und Temperaturbedingungen
def control_humidity(temperature, humidity, humidity_threshold=60, min_temp=15, max_humidity_duty=154):
    if humidity > humidity_threshold and temperature >= min_temp:
        print(f"Luftfeuchtigkeit {humidity}% über Schwellwert bei {temperature}°C. Lüfter für 20 Sekunden auf 15% Leistung.")
        pwm_fan.duty(max_humidity_duty)  # Setze Duty Cycle auf 10%
        time.sleep(20)  # Lüfter für 20 Sekunden laufen lassen
        pwm_fan.duty(0)  # Lüfter ausschalten
        print("Lüfter ausgeschaltet für 5 Minuten Wartezeit.")
        time.sleep(180)  # Warte 3 Minuten
    else:
        print(f"Keine Regelung notwendig. Luftfeuchtigkeit: {humidity}%, Temperatur: {temperature}°C")

print("Warte auf eingehende Nachrichten...")

# Empfangsschleife
while True:
    try:
        host, msg = e.recv()
        if msg:
            message = msg.decode('utf-8')  # Nachricht dekodieren
            print(f'Nachricht von {host}: {message}')
            
            if "Temperatur" in message and "Luftfeuchtigkeit" in message:
                try:
                    # Temperatur und Luftfeuchtigkeit extrahieren
                    temp_str = message.split("Temperatur: ")[1].split("C")[0]
                    hum_str = message.split("Luftfeuchtigkeit: ")[1].split("%")[0]
                    temperature = float(temp_str)
                    humidity = float(hum_str)

                    # Lüftersteuerung auf Grundlage der Temperatur
                    control_fan(temperature)
                    
                    # Luftfeuchtigkeitssteuerung
                    control_humidity(temperature, humidity)

                except (IndexError, ValueError) as e:
                    print("Fehler beim Extrahieren der Temperatur oder Luftfeuchtigkeit:", e)
            
            # Speicherbereinigung und Überwachung nur gelegentlich
            gc.collect()
            if time.time() % 60 == 0:  # Alle 60 Sekunden
                print("Freier Speicher:", gc.mem_free())
                
    except Exception as e:
        print("Fehler im Empfangsprozess:", e)
