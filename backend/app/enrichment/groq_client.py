from groq import AsyncGroq

from app.enrichment.prompt_builder import build_enrichment_prompt


class GroqEnrichmentClient:
    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise ValueError("GROQ_API_KEY is not configured")
        self.model = model
        self.client = AsyncGroq(api_key=api_key)

    async def enrich(self, title: str, text: str) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": build_enrichment_prompt(title=title, text=text),
                }
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Groq returned an empty enrichment response")
        return content

