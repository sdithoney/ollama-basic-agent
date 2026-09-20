from pathlib import Path
from string import Template


def read_prompt(path: str):
    return Path(path).read_text(encoding="utf-8")

def load_prompt(content: str, variables :dict[str, str]):
    return Template(content).safe_substitute(variables)