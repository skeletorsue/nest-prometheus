from prometheus_client import start_http_server, Summary, Gauge, Info
import pyowm
import configparser
import os
import time
import sys
import nest

# Gauges
g = {
	'nest_is_online': Gauge('nest_is_online', 'Device connection status with the Nest service', ['structure', 'device']),
	'nest_has_leaf': Gauge('nest_has_leaf', 'Displayed when the thermostat is set to an energy-saving temperature', ['structure', 'device']),
	'nest_target_temp': Gauge('nest_target_temp', 'Desired temperature, in half degrees Fahrenheit (0.5°F)', ['structure', 'device']),
	'nest_current_temp': Gauge('nest_current_temp', 'Temperature, measured at the device, in half degrees Fahrenheit (0.5°F)', ['structure', 'device']),
	'nest_humidity': Gauge('nest_humidity', 'Humidity, in percent (%) format, measured at the device, rounded to the nearest 5%', ['structure', 'device']),
	'nest_state': Gauge('nest_state', 'Indicates whether HVAC system is actively heating, cooling or is off. Use this value to indicate HVAC activity state', ['structure', 'device']),
	'nest_mode': Gauge('nest_mode', 'Indicates HVAC system heating/cooling modes, like Heat•Cool for systems with heating and cooling capacity, or Eco Temperatures for energy savings', ['structure', 'device']),
	'nest_time_to_target': Gauge('nest_time_to_target', 'The time, in minutes, that it will take for the structure to reach the target temperature', ['structure', 'device']),
	'nest_is_using_emergency_heat': Gauge('nest_is_using_emergency_heat', 'If this is using emergency heat or not', ['structure', 'device']),

	'weather_current_temp': Gauge('weather_current_temp', 'Current temperature, in Fahrenheit', ['city']),
	'weather_current_humidity': Gauge('weather_current_humidity', 'Current humidity, in percent (%)', ['city']),
}

i = {
	'nest_mode': Info('nest_mode', 'Indicates HVAC system heating/cooling modes'),
	'nest_state': Info('nest_state', 'Indicates the current state of the HVAC system')
}

# Create a metric to track time spent and requests made.
REQUEST_TIME = Summary('request_processing_seconds', 'Time spent processing request')
# Decorate function with metric.
@REQUEST_TIME.time()
def polling(napi, owm, owm_city_id):
    print("%s - Polling!" % time.time())

    observation = owm.weather_at_id(int(owm_city_id))
    loc = observation.get_location()
    city = loc.get_name()
    w = observation.get_weather()

    #w.get_temperature('celsius')['temp']
    for structure in napi.structures:
        for device in structure.thermostats:
            g['nest_is_online'].labels(structure.name, device.name).set(device.online)
            g['nest_has_leaf'].labels(structure.name, device.name).set(device.has_leaf)
            g['nest_is_using_emergency_heat'].labels(structure.name, device.name).set(device.is_using_emergency_heat)
            g['nest_target_temp'].labels(structure.name, device.name).set(device.target)
            g['nest_current_temp'].labels(structure.name, device.name).set(device.temperature)
            g['nest_humidity'].labels(structure.name, device.name).set(device.humidity)
            g['nest_state'].labels(structure.name, device.name).set((0 if device.hvac_state == "off" else 1))
            g['nest_mode'].labels(structure.name, device.name).set((0 if device.mode == "off" else 1))
            g['nest_time_to_target'].labels(structure.name, device.name).set(''.join(x for x in device.time_to_target if x.isdigit()))

            i['nest_state'].info({'state': device.hvac_state, 'device': device.name, 'structure': structure.name})
            i['nest_mode'].info({'mode': device.mode, 'device': device.name, 'structure': structure.name})

    g['weather_current_temp'].labels(city).set(w.get_temperature('fahrenheit')['temp'])
    g['weather_current_humidity'].labels(city).set(w.get_humidity())


if __name__ == '__main__':
    c = configparser.ConfigParser()
    c.read(os.path.join(os.path.abspath(os.path.dirname(__file__)),'settings.ini'))

    # Setup Nest account
    start_time = time.time()

    napi = nest.Nest(client_id=c['nest']['client_id'], client_secret=c['nest']['client_secret'], access_token_cache_file=os.path.join(os.path.abspath(os.path.dirname(__file__)),c['nest']['access_token_cache_file']))
    
    resp_time = time.time() - start_time
    sys.stderr.write("Nest API: %0.3fs\n" % resp_time)

    if napi.authorization_required:
      print("Go to " + napi.authorize_url + " to authorize, then enter PIN below")
      if sys.version_info[0] < 3:
        pin = raw_input("PIN: ")
      else:
        pin = input("PIN: ")
      napi.request_token(pin)


    # Setup OpenWeatherMap account
    start_time = time.time()

    owm = pyowm.OWM(c['owm']['owm_id'])

    resp_time = time.time() - start_time
    sys.stderr.write("OpenWeatherMap API: %0.3fs\n" % resp_time)
    

    # Start up the server to expose the metrics.
    start_http_server(8000)
    sys.stdout.write("Listening on port 8000...\n")
    
    while True:
        polling(napi, owm, c['owm']['owm_city_id'])
        time.sleep(30)
