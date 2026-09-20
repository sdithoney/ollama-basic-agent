import ollama

class OllamaAgent:
    def __init__(self, model: str, instructions: str, tools=None):
        if tools is None:
            tools = []
        if not model:
            raise ValueError("A model name must be provided.")
        if not isinstance(instructions, str):
            raise TypeError("Instructions must be a string.")
        if not isinstance(tools, list):
            raise TypeError("Tools must be a list of functions.")

        self.model = model
        self.tools = tools
        self.instructions = instructions
        self.available_tools = self.__get_available_tools__()
        self.messages = self.__init_messages__()

    def __init_messages__(self):
        return [{"role": "system", "content": self.instructions}]

    def __get_available_tools__(self):
        return {func.__name__: func for func in self.tools if callable(func)}

    def __invoke_model__(self):
        return ollama.chat(
            model=self.model,
            messages=self.messages,
            tools=self.tools,
            options={"temperature": 0.0}  # Low temperature reduces hallucinations in tool calling
        )

    def __execute_tools__(self, response):
        tool_calls = response['message'].get('tool_calls', [])

        for tool_call in tool_calls:
            function_name = tool_call['function']['name']
            arguments = tool_call['function'].get('arguments', {})
            print(f"[Agent Decision]: Calling '{function_name}' with {arguments}")

            if function_name in self.available_tools:
                try:
                    tool_output = self.available_tools[function_name](**arguments)
                except Exception as e:
                    tool_output = f"Error: {str(e)}"

                self.messages.append({
                    "role": "tool",
                    "content": str(tool_output),
                    "name": function_name,
                    "tool_name": function_name
                })

    def chat(self, user_prompt: str):
        self.messages.append({"role": "user", "content": user_prompt})

        while True:
            response = self.__invoke_model__()
            assistant_message = response['message']
            self.messages.append(assistant_message)

            if not assistant_message.get('tool_calls'):
                content = assistant_message.get('content', '').strip()
                return content or "Task completed."

            self.__execute_tools__(response)