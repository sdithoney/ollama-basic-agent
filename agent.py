import json

import ollama


class OllamaAgent:
    def __init__(
        self,
        thinking_model: str,
        instructions: str,
        classifier_model: str,
        tools=None,
        max_turns: int = 15,
        num_ctx: int = 8192,
        max_history_messages: int = 8,
        keep_recent_messages: int = 2,
        max_episodes: int = 5,
    ):
        if not thinking_model:
            raise ValueError("A primary model name must be provided.")
        if not classifier_model:
            raise ValueError("A classifier model name must be provided.")
        if not isinstance(instructions, str):
            raise TypeError("Instructions must be a string.")

        self.model = thinking_model
        self.classifier_model = classifier_model
        self.instructions = instructions
        self.tools = tools if tools is not None else []
        self.max_turns = max_turns
        self.num_ctx = num_ctx

        # Context & Memory thresholds
        self.max_history_messages = max_history_messages
        self.keep_recent_messages = keep_recent_messages
        self.semantic_summary = ""

        # Episodic Memory tracking
        self.max_episodes = max_episodes
        self.episodic_memory = []  # Stores recent action/failure/rejection episodes

        self.available_tools = self.__get_available_tools__()
        self.messages = []
        self.__reset_system_context__()

    def __reset_system_context__(self):
        """Initializes or refreshes the system message with semantic and episodic memory."""
        context_blocks = [self.instructions]

        # 1. Semantic Memory (long-term conversation summary)
        if self.semantic_summary:
            context_blocks.append(f"\n[Ongoing Context & Memory Summary]:\n{self.semantic_summary}")

        # 2. Episodic Memory (records of past actions, successes, and failures)
        if self.episodic_memory:
            episodes_str = "\n".join(
                f"- Action: {ep['action']}({ep['arguments']}) | Status: {ep['status'].upper()} | Details: {ep['outcome']}"
                for ep in self.episodic_memory[-self.max_episodes:]
            )
            context_blocks.append(
                f"\n[Episodic Memory - Past Actions & Outcomes]:\n"
                f"Review past attempts below. Do NOT repeat actions that recently failed or were rejected by the user:\n"
                f"{episodes_str}"
            )

        system_message = {"role": "system", "content": "\n".join(context_blocks)}

        if not self.messages:
            self.messages = [system_message]
        else:
            self.messages[0] = system_message

    def __record_episode__(self, action: str, arguments: dict, status: str, outcome: str):
        """Records an action episode into episodic memory."""
        episode = {
            "action": action,
            "arguments": json.dumps(arguments),
            "status": status,  # "success", "failed", or "rejected"
            "outcome": str(outcome)[:250],
        }
        self.episodic_memory.append(episode)
        if len(self.episodic_memory) > self.max_episodes:
            self.episodic_memory.pop(0)

        # Refresh the system context with the new episodic awareness
        self.__reset_system_context__()

    def __get_available_tools__(self):
        return {func.__name__: func for func in self.tools if callable(func)}

    def __compress_semantic_memory__(self):
        """Compresses conversation turns into semantic summary when exceeding threshold."""
        non_system_messages = self.messages[1:]
        if len(non_system_messages) <= self.max_history_messages:
            return

        split_point = len(non_system_messages) - self.keep_recent_messages
        to_summarize = non_system_messages[:split_point]
        recent_messages = non_system_messages[split_point:]

        if to_summarize and to_summarize[-1].get("tool_calls"):
            return

        formatted_conversation = []
        for msg in to_summarize:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "tool":
                formatted_conversation.append(f"Tool Output ({msg.get('name')}): {content[:300]}...")
            elif role == "assistant" and msg.get("tool_calls"):
                calls = [tc["function"]["name"] for tc in msg["tool_calls"]]
                formatted_conversation.append(f"Assistant requested tools: {', '.join(calls)}")
            else:
                formatted_conversation.append(f"{role.capitalize()}: {content}")

        history_text = "\n".join(formatted_conversation)

        summary_prompt = (
            "You are a conversation summarizer. Distill the following past interactions "
            "into a concise, factual summary. Preserve essential details: user preferences, "
            "parameters, key entities/results, and decisions made.\n"
            f"Previous Summary (if any): {self.semantic_summary}\n\n"
            f"Recent Conversation:\n{history_text}\n\n"
            "Produce ONLY the updated summary:"
        )

        try:
            print("[Agent Memory]: Compressing past context into semantic memory...")
            res = ollama.chat(
                model=self.model,
                messages=[{"role": "user", "content": summary_prompt}],
                options={"temperature": 0.0},
            )
            self.semantic_summary = res["message"]["content"].strip()

            # Rebuild messages with preserved recent context
            self.messages = [self.messages[0]] + recent_messages
            self.__reset_system_context__()

        except Exception as e:
            print(f"[Agent Memory Warning]: Failed to compress context: {str(e)}")

    def __invoke_model__(self):
        return ollama.chat(
            model=self.model,
            messages=self.messages,
            tools=self.tools,
            options={
                "temperature": 0.0,
                "num_ctx": self.num_ctx,
            },
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
                    print(f"[tool {function_name}] : {str(tool_output)}")
                    # Record successful episode
                    self.__record_episode__(function_name, arguments, "success", "Executed successfully.")
                except Exception as e:
                    tool_output = f"Error: {str(e)}"
                    # Record failure episode
                    self.__record_episode__(function_name, arguments, "failed", str(e))
            else:
                tool_output = f"Error: Tool '{function_name}' is not available."
                self.__record_episode__(function_name, arguments, "failed", "Tool not registered.")

            msg = {
                "role": "tool",
                "content": str(tool_output),
                "name": function_name,
            }
            if call_id:
                msg["tool_call_id"] = call_id
            self.messages.append(msg)

    def __reject_tools__(self, tool_calls, reason: str):
        """Maintains valid message sequence and logs user rejections into episodic memory."""
        for tool_call in tool_calls:
            func_name = tool_call["function"]["name"]
            arguments = tool_call["function"].get("arguments", {})
            call_id = tool_call.get("id")

            # Record rejection episode
            self.__record_episode__(func_name, arguments, "rejected", reason)

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
        if not message:
            return False

        system_prompt = (
            "You are a strict intent classifier. "
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
                options={
                    "temperature": 0.0,
                    "num_predict": 2,
                },
            )
            verdict = res["message"]["content"].strip().lower()
            return "yes" in verdict
        except Exception:
            return False

    def chat(self, user_prompt: str) -> str:
        # 1. Prune/compress long conversations
        self.__compress_semantic_memory__()

        self.messages.append({"role": "user", "content": user_prompt})

        turn = 0
        while turn < self.max_turns:
            turn += 1
            response = self.__invoke_model__()
            assistant_message = response["message"]
            self.messages.append(assistant_message)

            tool_calls = assistant_message.get("tool_calls")

            # ---------------------------------------------------------
            # 1. Tool Call / Approval Flow
            # ---------------------------------------------------------
            if tool_calls:
                tools_to_run = [tc["function"]["name"] for tc in tool_calls]
                prompt = f"I want to execute: {', '.join(tools_to_run)}. Do you approve? (yes/no): "

                approval = input(f"\n[Agent]: {prompt}\n[User]: ").strip()

                if approval.lower() in ("yes", "y"):
                    self.__execute_tools__(tool_calls)
                else:
                    feedback = input("[User Feedback for Rejection (optional)]: ").strip()
                    if not feedback:
                        feedback = "User rejected this tool execution."
                    self.__reject_tools__(tool_calls, feedback)

                continue

            # ---------------------------------------------------------
            # 2. Conversation / Clarification Flow
            # ---------------------------------------------------------
            content = assistant_message.get("content", "").strip()

            if not content:
                return "Task completed."

            is_obvious_question = (
                content.endswith("?")
                or "please provide" in content.lower()
                or "could you" in content.lower()
            )

            needs_user_input = is_obvious_question or self.__decide_question_flow__(content)

            if needs_user_input:
                self.__invoke_user_prompt__(content)
                continue

            return content

        return "Agent stopped: Reached maximum conversational turns without completion."