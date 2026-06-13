ENRICHMENT_PROMPT = """You are an AI/ML engineering intelligence analyst. Given the article below, produce a structured JSON analysis.

Rules:
- summary: exactly 2 sentences. First sentence: what happened or what was built. Second sentence: why it matters for AI engineers.
- category: exactly one of: "models", "research", "tools", "cloud", "industry", "other"
  - models: new model releases, benchmarks, model comparisons
  - research: papers, novel techniques, theoretical advances
  - tools: frameworks, libraries, developer tools, IDEs
  - cloud: AWS/GCP/Azure AI services, infrastructure, MLOps platforms
  - industry: company news, funding, acquisitions, policy
  - other: everything else
- importance: integer 1-5
  - 5: paradigm-shifting (new GPT-4-class model, major framework release)
  - 4: highly significant (important benchmark, major company move)
  - 3: notable (useful tool, interesting paper, meaningful update)
  - 2: minor (incremental update, niche tool)
  - 1: low signal (blog fluff, minor announcement)
- entities: extract only explicitly named entities
  - models: list of model names
  - companies: list of company names
  - techniques: list of ML techniques
  - datasets: list of dataset names
- keywords: 5-8 lowercase keywords for search indexing

Return ONLY a JSON object. Do not use markdown fences, a preamble, or an explanation.

Article title: {title}
Article text: {text}

JSON:"""


def build_enrichment_prompt(title: str, text: str) -> str:
    return ENRICHMENT_PROMPT.format(title=title, text=text)
