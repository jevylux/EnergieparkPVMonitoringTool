#!/usr/bin/env python3
"""
Tool to retrieve geographical coordinates for locations defined in the configuration.yaml file
@MarcDurbach 2026
"""
import yaml
import time
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

# Load the YAML file
with open('configuration_energiepark.yaml', 'r') as file:
    data = yaml.safe_load(file)

# Extract the list of pods
pods = data['pod']

# Initialize geolocator with a unique user agent
geolocator = Nominatim(user_agent="my_energy_app_luxembourg")

def get_coordinates(address):
    try:
        location = geolocator.geocode(address, timeout=10)
        print(f"Geocoding result for '{address}': {location}")
        if location:
            return location.latitude, location.longitude
        else:
            return None, None
    except (GeocoderTimedOut, GeocoderUnavailable) as e:
        print(f"Error geocoding {address}: {e}")
        return None, None

# Add coordinates to each pod, with a delay between requests
for pod in pods:
    print(f"Geocoding address: {pod['address']}")
    lat, lon = get_coordinates(pod['address'])
    pod['latitude'] = lat
    pod['longitude'] = lon
    time.sleep(3)  # 1 second delay between requests

# Print results
for pod in pods:
    print(f"ID: {pod['id']}")
    print(f"Address: {pod['address']}")
    print(f"Latitude: {pod['latitude']}")
    print(f"Longitude: {pod['longitude']}")
    print(f"Price per kWh: {pod['price_per_kWh']}")
    print(f"Peak Power: {pod['peak_power']}")
    print("---")
