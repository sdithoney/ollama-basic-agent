from dotenv import load_dotenv
load_dotenv()

from agent import OllamaAgent
from tools import get_job_details
from utils import read_prompt



instruction_prompt = read_prompt("./system_prompt.md")

agent = OllamaAgent(
    thinking_model="gemma4:e4b",
    instructions=instruction_prompt,
    classifier_model="phi3.5:latest",
    tools=[get_job_details]  # Simply pass a list of functions
)

result = agent.chat("Search for data science in India.")
print(f"\nFinal Answer: \n\n{result}")