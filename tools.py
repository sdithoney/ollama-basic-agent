# 1. Define your tools
def get_flight_status(flight_number: str) -> str:
    """Retrieves flight status information. Useful for tracking arrivals/departures."""
    if flight_number == "AA123":
        return "Delayed by 45 minutes due to weather."
    return "On time."

def get_weather(city: str) -> str:
    """Retrieves current weather for a city."""
    return f"The weather in {city} is currently sunny and 22°C."
