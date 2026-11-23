# apis.py: the calls to OpenWeatherMap and Ticketmaster live here.
# Each function returns (result, error). One of the two is always None.

import os
from datetime import datetime
import requests

# API keys come from Replit Secrets. If one is missing, that box on the
# dashboard says so, and the rest of the app still works.
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
TICKETMASTER_API_KEY = os.getenv("TICKETMASTER_API_KEY")

# Event types a visitor can pick on their profile (Ticketmaster's names)
CATEGORIES = ["Music", "Sports", "Arts & Theatre", "Family", "Film"]


def split_location(location):
    """Turn "Chicago, IL" into ("Chicago", "IL"), or None if there's no comma."""
    if "," not in location:
        return None
    city, state = [part.strip() for part in location.split(",", 1)]
    return city, state


def weather_tip(temperature, conditions):
    """A short tip for going out tonight."""
    wet = ["rain", "drizzle", "snow", "thunderstorm"]
    if any(word in conditions for word in wet):
        return "Bring an umbrella, or pick an indoor event."
    if temperature < 40:
        return "Bundle up: it's cold out there."
    if temperature > 85:
        return "It's hot: an evening event might be best."
    return "Great night to go out!"


def fetch_weather(location):
    """Get the current weather for "City, ST" from OpenWeatherMap."""
    if not OPENWEATHER_API_KEY:
        return None, "Add OPENWEATHER_API_KEY in Secrets to see the weather."
    parts = split_location(location)
    if not parts:
        return None, "Enter a city and state, like New York, NY"
    city, state = parts

    try:
        # Step 1: turn the city and state into map coordinates
        geo = requests.get(
            "https://api.openweathermap.org/geo/1.0/direct",
            params={"q": f"{city},{state},US", "limit": 1,
                    "appid": OPENWEATHER_API_KEY},
            timeout=10,
        )
        if geo.status_code == 401:
            return None, "The weather API key was rejected. Check OPENWEATHER_API_KEY in Secrets."
        places = geo.json()
        if geo.status_code != 200 or not places:
            return None, f"Couldn't find {city}, {state}. Check the spelling."
        place = places[0]

        # Step 2: get the current weather at those coordinates
        current = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"lat": place["lat"], "lon": place["lon"],
                    "units": "imperial", "appid": OPENWEATHER_API_KEY},
            timeout=10,
        )
        if current.status_code != 200:
            return None, "The weather service had a problem. Try again."
        data = current.json()
    except requests.RequestException:
        return None, "The weather service didn't respond. Try again."

    temperature = round(data["main"]["temp"])
    conditions = data["weather"][0]["description"]
    weather = {
        "location": f"{place['name']}, {place.get('state', state)}",
        "temperature": temperature,
        "conditions": conditions,
        "tip": weather_tip(temperature, conditions),
    }
    return weather, None


def fetch_events(location, category=""):
    """Get the next 5 events in "City, ST" from Ticketmaster."""
    if not TICKETMASTER_API_KEY:
        return None, "Add TICKETMASTER_API_KEY in Secrets to see events."
    parts = split_location(location)
    if not parts:
        return None, "Enter a city and state, like New York, NY"
    city, state = parts

    params = {"apikey": TICKETMASTER_API_KEY,
              "city": city, "stateCode": state, "countryCode": "US",
              "sort": "date,asc", "size": 5}
    if category:
        params["classificationName"] = category  # only this type of event

    try:
        response = requests.get("https://app.ticketmaster.com/discovery/v2/events.json",
                                params=params, timeout=10)
    except requests.RequestException:
        return None, "Ticketmaster didn't respond. Try again."

    if response.status_code == 401:
        return None, "The Ticketmaster key was rejected. Check TICKETMASTER_API_KEY in Secrets."
    if response.status_code == 429:
        return None, "Too many requests to Ticketmaster. Wait a minute and try again."
    if response.status_code != 200:
        return None, "Ticketmaster had a problem. Try again."

    data = response.json()
    # If there are no events, Ticketmaster leaves out "_embedded" entirely
    found = data.get("_embedded", {}).get("events", [])

    events = []
    for event in found:
        start = event["dates"]["start"]
        day = datetime.strptime(start["localDate"], "%Y-%m-%d")
        date = f"{day:%a, %b} {day.day}"
        if "localTime" in start:
            time = datetime.strptime(start["localTime"], "%H:%M:%S")
            date += " at " + time.strftime("%I:%M %p").lstrip("0")
        venues = event.get("_embedded", {}).get("venues", [])
        events.append({
            "id": event["id"],
            "name": event["name"],
            "url": event["url"],
            "date": date,
            "venue": venues[0]["name"] if venues else "Venue TBA",
        })
    return events, None
