import network
import socket
import time
import dht
from machine import Pin
from machine import ADC


relay = Pin(15, Pin.OUT)
relay.value(0)
soil_sensor = ADC(Pin(26))
soil = soil_sensor.read_u16()
dht_sensor = dht.DHT11(Pin(14))


ssid = 'zarizeni_sveta'
password = 'rentales'

auto_water = False
last_check = 0
check_interval = 10

def webpage(soil, temp, humidity, auto):
    auto_state = "Zapnutý" if auto else "Vypnutý"
    toggle_text = "Vypnout auto-režim" if auto else "Zapnout auto-režim"
    html = f"""
    <!DOCTYPE html>
    <html lang="cs">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Květináč web</title>

        <style>
            body {{
                font-family: sans-serif;
                background-color: #b8c0c8;
                color: #333;
                padding: 50px;
            }}

            h1 {{
                font-size: 50px;
                text-align: center;
                margin-bottom: 25px;
            }}
            h2{{
                font-size: 40px;
                text-align: center;
                margin-bottom: 25px;
            }}
            h3{{
                text-align: center;
                font-size: 35px;
            }}

            form {{
                text-align: center;
                margin: 1vw auto;
            }}

            input[type="submit"] {{
                font-size: 1.2vw;
                padding: 0.6vw 1.5vw;
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 0.5vw;
                cursor: pointer;
            }}

            input[type="submit"]:hover {{
                background-color: #45a049;
            }}

            p {{
                text-align: center;
                font-size: 1.4vw;
            }}

            strong {{
                color: #006400;
            }}
        </style>
    </head>
    <body>
        <h1>Raspberry Pi Pico Web Server</h1>
        <h2>Zap/Vyp květináč</h2>
        <form action="/toggle">
            <input type="submit" value="{toggle_text}" method="get"/>
        </form>

            <h2>Refresh hodnot</h2>
        <form action="/value">
            <input type="submit" value="Získat hodnoty" method="get"/>
        </form>
    
        <h2>Zalít květináč</h2>
        <form action="/water">
            <input type="submit" value="Zalít teď!" method="get"/>
        </form>


        <h3>Načtené hodnoty:</h3>
        <p><strong>Teplota:</strong> {temp}°C</p>
        <p><strong>Vlhkost:</strong> {humidity}%</p>
        <p><strong>Půda:</strong> {soil}</p>

    </body>
    </html>
        """
    return str(html)

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(ssid, password)

connection_timeout = 10
while connection_timeout > 0:
    if wlan.status() >= 3:
        break
    connection_timeout -= 1
    print('Waiting for network connection...')
    time.sleep(1)

if wlan.status() != 3:
    raise RuntimeError('Failed to establish a network connection')
else:
    print('Connection successful!')
    network_info = wlan.ifconfig()
    print('IP address:', network_info[0])

addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(addr)
s.listen()

print('Listening on', addr)

last_auto_water = time.ticks_ms()

soil = 0
temp = "-"
humidity = "-"

while True:
    try:
        conn, addr = s.accept()
        print('Connected from', addr)

        request = conn.recv(1024)
        print("Request raw:", repr(request))
        request = str(request)
        print('Request content = %s' % request)

        try:
            request = request.split()[1]
            print('Request:', request)
        except IndexError:
            request = '/' 

        current_time = time.ticks_ms()
        if auto_water and time.ticks_diff(current_time, last_auto_water) > 10000:
            soil_value = soil_sensor.read_u16()
            if soil_value > 50000:
                relay.value(1)
                time.sleep(2)
                relay.value(0)
                last_auto_water = current_time

        soil = 0
        temp = "-"
        humidity = "-"

        if auto_water:
            if request == '/' or request == '/value':
                soil = soil_sensor.read_u16()
                try:
                    dht_sensor.measure()
                    temp = dht_sensor.temperature()
                    humidity = dht_sensor.humidity()
                except Exception as e:
                    print("DHT11 chyba:", e)
                    temp = "chyba"
                    humidity = "chyba"

            elif request == '/water':
                print("Zalévání spuštěno")
                relay.value(1)
                time.sleep(1)
                relay.value(0)

            elif request == '/toggle':
                auto_water = not auto_water

        response = webpage(soil, temp, humidity, auto_water)

        conn.send('HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n')
        conn.send(response)
        conn.close()

    except OSError as e:
        print("Chyba připojení:", e)
        try:
            conn.close()
        except:
            pass