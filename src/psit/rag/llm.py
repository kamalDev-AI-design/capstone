"""Optional LLM layer. DEFAULT IS EXTRACTIVE / LOCAL. OpenRouter is opt-in (env key + explicit setting) and only
ever receives the user question plus already-retrieved *synthetic* evidence snippets - never DB contents, PII or keys
in logs. Output is validated against the supplied evidence; any problem falls back to the extractive answer."""
import os
import re

import httpx

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
SUGGESTED_MODELS = ["openai/gpt-4o-mini", "anthropic/claude-3.5-haiku", "google/gemini-2.0-flash-001",
                    "meta-llama/llama-3.1-8b-instruct"]
MODEL_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.:-]+$")

SYSTEM_PROMPT = (
    "You summarize fictional training evidence for a pharmaceutical safety intake assistant. Rules: use ONLY the numbered "
    "evidence passages provided; cite every factual statement with its passage number like [1]; if the evidence does not "
    "answer the question reply exactly INSUFFICIENT_EVIDENCE; never use outside knowledge; never assess causality, "
    "seriousness, expectedness, listedness or reportability; never give medical or treatment advice; do not treat a "
    "historical report as a procedure (SOP). Be concise (max 6 sentences).")

CLASSIFIER_PROMPT = ("Classify the user's message into exactly one label from: DIRECT_RESPONSE, REPORT_LOOKUP, SOP_LOOKUP, "
                     "HYBRID_KNOWLEDGE_LOOKUP, PROHIBITED_REQUEST. PROHIBITED_REQUEST = asks for causality, seriousness, "
                     "expectedness, reportability, treatment or regulatory advice. Reply with the label only.")


class LLMUnavailable(Exception):
    pass


class OpenRouterProvider:
    name = "openrouter"

    def __init__(self, model: str, api_key: str, client: httpx.Client | None = None):
        self.model, self._key = model, api_key
        self._client = client or httpx.Client(timeout=20)

    def _chat(self, system: str, user: str, max_tokens: int) -> str:
        try:
            r = self._client.post(
                OPENROUTER_URL, headers={"Authorization": f"Bearer {self._key}", "X-Title": "PSIT Agent (training prototype)"},
                json={"model": self.model, "temperature": 0, "top_p": 0.1, "max_tokens": max_tokens,
                      "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
            r.raise_for_status()
            return (r.json()["choices"][0]["message"]["content"] or "").strip()
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
            raise LLMUnavailable(type(e).__name__) from None      # never include the key or response body

    def answer(self, question: str, passages: list[str]) -> str:
        body = "\n\n".join(f"[{i}] {p}" for i, p in enumerate(passages, 1))
        return self._chat(SYSTEM_PROMPT, f"Question: {question}\n\nEvidence:\n{body}", 450)

    def classify(self, message: str) -> str:
        return self._chat(CLASSIFIER_PROMPT, message[:500], 8).strip().upper()


def validate_generated(text: str, n_evidence: int) -> bool:
    cites = [int(x) for x in re.findall(r"\[(\d+)\]", text)]
    return bool(text) and bool(cites) and all(1 <= c <= n_evidence for c in cites)


class LlmGate:
    """Decides per request whether a provider may be used; owns settings lookup. Extractive unless fully enabled."""

    def __init__(self, uow, client: httpx.Client | None = None):
        self.uow, self._client = uow, client

    def settings(self) -> dict:
        with self.uow.begin() as tx:
            provider = tx.rag.get_setting("llm_provider", "EXTRACTIVE")
            model = tx.rag.get_setting("llm_model", os.getenv("PSIT_OPENROUTER_MODEL", SUGGESTED_MODELS[0]))
        return {"provider": provider, "model": model, "key_configured": bool(os.getenv("OPENROUTER_API_KEY")),
                "suggested_models": SUGGESTED_MODELS}

    def _provider(self) -> OpenRouterProvider | None:
        s, key = self.settings(), os.getenv("OPENROUTER_API_KEY")
        if s["provider"] != "OPENROUTER" or not key:
            return None
        return OpenRouterProvider(s["model"], key, self._client)

    def refine(self, query: str, evidence: list, resp: dict) -> dict:
        p = self._provider()
        if p is None:
            return {}
        passages = [f"({c.chunk.source_type}, {c.chunk.source_id}) {c.chunk.text}" for c in evidence]
        try:
            text = p.answer(query, passages)
        except LLMUnavailable as e:
            return {"llm_notice": f"OpenRouter unavailable ({e}); showing the extractive answer instead."}
        if text.strip().upper().startswith("INSUFFICIENT_EVIDENCE"):
            from .context import ABSTAIN_MESSAGE
            return {"abstained": True, "abstain_reason": "INSUFFICIENT_EVIDENCE", "answer": ABSTAIN_MESSAGE,
                    "citations": [], "answer_mode": "openrouter"}
        if not validate_generated(text, len(evidence)):
            return {"llm_notice": "Generated answer failed citation validation; showing the extractive answer instead."}
        return {"answer": text, "answer_mode": f"openrouter:{p.model}"}

    def classify(self, message: str) -> str:
        p = self._provider()
        if p is None:
            return ""
        try:
            return p.classify(message)
        except LLMUnavailable:
            return ""
