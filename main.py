from agent import OllamaAgent


# 1. Define your tools
def get_flight_status(flight_number: str) -> str:
    """Retrieves flight status information. Useful for tracking arrivals/departures."""
    if flight_number == "AA123":
        return "Delayed by 45 minutes due to weather."
    return "On time."

def get_weather(city: str) -> str:
    """Retrieves current weather for a city."""
    return f"The weather in {city} is currently sunny and 22°C."

# 2. Instantiate the agent with whatever tools this specific agent needs
agent = OllamaAgent(
    model="gemma4:e4b",
    instructions="You are a good assistance use tools if necessary.",
    tools=[get_flight_status, get_weather]  # Simply pass a list of functions
)

# 3. Run the loop
result = agent.chat("What is the weather of Patna?")
print(f"\nFinal Answer: {result}")