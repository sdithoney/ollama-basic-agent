import ollama

class OllamaAgent:
    def __init__(self, thinking_model: str, instructions: str, classifier_model: str, tools=None):
        if tools is None:
            tools = []

        if not thinking_model:
            raise ValueError("A primary model name must be provided.")
        if not isinstance(instructions, str):
            raise TypeError("Instructions must be a string.")

        self.model = thinking_model
        self.tools = tools
        self.instructions = instructions
        self.classifier_model = classifier_model
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
            options={"temperature": 0.0},
        )

    def __execute_tools__(self, tool_calls):
        for tool_call in tool_calls:
            function_name = tool_call["function"]["name"]
            arguments = tool_call["function"].get("arguments", {})
            call_id = tool_call.get("id")

            print(f"[Agent Decision]: Calling '{function_name}' with {arguments}")

            if function_name in self.available_tools:
                try:
                    tool_output = self.available_tools[function_name](**arguments)
                except Exception as e:
                    tool_output = f"Error: {str(e)}"
            else:
                tool_output = f"Error: Tool '{function_name}' is not available."

            msg = {
                "role": "tool",
                "content": str(tool_output),
                "name": function_name,
            }
            if call_id:
                msg["tool_call_id"] = call_id
            self.messages.append(msg)

    def __reject_tools__(self, tool_calls, reason: str):
        """
        Satisfies API protocol by returning a 'tool' response for every tool call,
        explaining that the user aborted the action.
        """
        for tool_call in tool_calls:
            func_name = tool_call["function"]["name"]
            call_id = tool_call.get("id")

            msg = {
                "role": "tool",
                "name": func_name,
                "content": f"Tool execution rejected by human. Feedback: {reason}",
            }
            if call_id:
                msg["tool_call_id"] = call_id
            self.messages.append(msg)

    def __invoke_user_prompt__(self, question: str) -> str:
        """Prompts the user for normal conversational flow / clarifications."""
        user_answer = input(f"\n[Agent]: {question}\n[User]: ").strip()
        self.messages.append({"role": "user", "content": user_answer})
        return user_answer


    def __decide_question_flow__(self, message: str) -> bool:
        system_prompt = (
            "You are a strict intent classifier."
            "Determine if the assistant is asking the user a direct question, requesting clarification, "
            "or seeking missing data to proceed.\n"
            "Reply ONLY with 'yes' or 'no'."
        )

        try:
            res = ollama.chat(
                model=self.classifier_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Assistant response: \"{message}\""},
                ],
                options={"temperature": 0.0},
            )
            verdict = res["message"]["content"].strip().lower()
            return "yes" in verdict
        except Exception:
            return False

    def chat(self, user_prompt: str):
        self.messages.append({"role": "user", "content": user_prompt})


        while True:
            response = self.__invoke_model__()
            assistant_message = response["message"]
            self.messages.append(assistant_message)

            tool_calls = assistant_message.get("tool_calls")

            #-------------------------------------------------------------#
            # 1. TOOL CALL / APPROVAL FLOW                                #
            #-------------------------------------------------------------#

            if tool_calls:
                tools_to_run = [tc["function"]["name"] for tc in tool_calls]
                prompt = f"I want to execute: {', '.join(tools_to_run)}. Do you approve? (yes/no): "

                # Ask in terminal directly without polluting messages with a 'user' role
                approval = input(f"\n[Agent]: {prompt}\n[User]: ").strip()

                if approval.lower() in ("yes", "y"):
                    self.__execute_tools__(tool_calls)
                else:
                    feedback = input("[User Feedback for Rejection (optional)]: ").strip()
                    if not feedback:
                        feedback = "User rejected this tool execution."
                    self.__reject_tools__(tool_calls, feedback)

                continue

            #-------------------------------------------------------------#
            # 2. CONVERSATION / MISSING DATA FLOW                         #
            #-------------------------------------------------------------#

            content = assistant_message.get("content", "").strip()

            is_obvious_question = content.endswith("?") or "please provide" in content.lower()
            needs_user_input = is_obvious_question or self.__decide_question_flow__(content)

            if needs_user_input:
                self.__invoke_user_prompt__(content)
                continue

            return content or "Task completed."

