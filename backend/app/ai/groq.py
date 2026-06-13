from langchain_groq import ChatGroq


class GroqChatClient:
    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise ValueError("GROQ_API_KEY is not configured")
        self.client = ChatGroq(
            api_key=api_key,
            model=model,
            temperature=0,
            max_retries=2,
        )

    async def complete(self, prompt: str) -> str:
        response = await self.client.ainvoke(prompt)
        if not isinstance(response.content, str) or not response.content.strip():
            raise ValueError("Groq returned an empty response")
        return response.content
