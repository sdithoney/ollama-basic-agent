from agent import OllamaAgent
from tools import get_flight_status, get_weather
from utils import read_prompt


instruction_prompt = read_prompt("./system_prompt.md")

agent = OllamaAgent(
    thinking_model="gemma4:e4b",
    instructions=instruction_prompt,
    classifier_model="phi3.5:latest",
    tools=[get_flight_status, get_weather]  # Simply pass a list of functions
)

result = agent.chat("What is the weather of Patna and why is the aeroplane delayed??")
print(f"\nFinal Answer: {result}")