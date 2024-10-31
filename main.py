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

print("Warte auf eingehende Nachrichten...")

# Empfangsschleife
while True:
    host, msg = e.recv()
    if msg:
        message = msg.decode('utf-8')  # Nachricht dekodieren
        print(f'Nachricht von {host}: {message}')
        
        if "Temperatur" in message:
            try:
                temp_str = message.split("Temperatur: ")[1].split("°C")[0]
                temperature = float(temp_str)
                control_fan(temperature)  # Lüfter steuern
            except (IndexError, ValueError) as e:
                print("Fehler beim Extrahieren der Temperatur:", e)
        
        # Speicherbereinigung und Überwachung nur gelegentlich
        gc.collect()
        if time.time() % 60 == 0:  # Alle 60 Sekunden
            print("Freier Speicher:", gc.mem_free())
