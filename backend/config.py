"""
LLM provider routing for ObserveOps.
NEVER hardcode model names in agent or plugin code — always call these helpers.

Supported providers:
  ollama        — local Ollama (free, connects to host via host.docker.internal)
  openai        — OpenAI GPT-4o / GPT-4o-mini
  gemini        — Google Gemini 2.0 Flash-Lite
  deepseek      — DeepSeek V3 (OpenAI-compat API)
  sonnet        — Anthropic Claude Sonnet
  bedrock-haiku — AWS Bedrock Claude Haiku
  groq          — Groq (Llama / Mixtral — ultra-fast)
  mistral       — Mistral AI
  azure-openai  — Azure-hosted OpenAI models
  cohere        — Cohere Command R+
"""
import os
import logging

logger = logging.getLogger(__name__)


def get_scan_llm(provider: str | None = None, llm_config: dict | None = None):
    """Return the scanning LLM. Provider + credentials come from UI or .env fallback."""
    return _build_llm(provider or os.getenv("SCAN_LLM", "ollama"), llm_config or {})


def get_report_llm(provider: str | None = None, llm_config: dict | None = None):
    """Return the report LLM. Provider + credentials come from UI or .env fallback."""
    return _build_llm(provider or os.getenv("REPORT_LLM", "ollama"), llm_config or {})


def _build_llm(provider: str, cfg: dict):
    """
    Build an LLM instance from a provider name + per-request config dict.
    cfg keys match the LLMConfig interface from the frontend.
    Falls back to .env values when a UI field is blank.
    """
    provider = (provider or "ollama").lower().strip()

    # ── Ollama ────────────────────────────────────────────────────────
    if provider == "ollama":
        try:
            from langchain_ollama import OllamaLLM
            base_url = cfg.get("ollama_url") or os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
            model    = cfg.get("ollama_model") or os.getenv("OLLAMA_MODEL", "llama3.2")
            logger.info("Ollama → %s @ %s", model, base_url)
            return OllamaLLM(model=model, base_url=base_url)
        except ImportError:
            logger.warning("langchain-ollama not installed; falling back to mock LLM")
            return _mock_llm()

    # ── OpenAI ────────────────────────────────────────────────────────
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        api_key = cfg.get("openai_api_key") or os.getenv("OPENAI_API_KEY", "")
        model   = cfg.get("openai_model") or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        if not api_key:
            raise ValueError("OpenAI: API key is required. Provide it in the UI or set OPENAI_API_KEY in .env")
        logger.info("OpenAI → %s", model)
        return ChatOpenAI(model=model, api_key=api_key)

    # ── Google Gemini ────────────────────────────────────────────────
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        api_key = cfg.get("google_api_key") or os.getenv("GOOGLE_API_KEY", "")
        model   = cfg.get("gemini_model") or os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite")
        if not api_key:
            raise ValueError("Gemini: API key is required. Provide it in the UI or set GOOGLE_API_KEY in .env")
        logger.info("Gemini → %s", model)
        return ChatGoogleGenerativeAI(model=model, google_api_key=api_key)

    # ── DeepSeek ─────────────────────────────────────────────────────
    if provider == "deepseek":
        from langchain_openai import ChatOpenAI
        api_key = cfg.get("deepseek_api_key") or os.getenv("DEEPSEEK_API_KEY", "")
        model   = cfg.get("deepseek_model") or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        if not api_key:
            raise ValueError("DeepSeek: API key is required. Provide it in the UI or set DEEPSEEK_API_KEY in .env")
        logger.info("DeepSeek → %s", model)
        return ChatOpenAI(model=model, api_key=api_key, base_url="https://api.deepseek.com")

    # ── Anthropic Claude Sonnet ───────────────────────────────────────
    if provider == "sonnet":
        from langchain_anthropic import ChatAnthropic
        api_key = cfg.get("anthropic_api_key") or os.getenv("ANTHROPIC_API_KEY", "")
        model   = cfg.get("claude_model") or os.getenv("CLAUDE_MODEL_ID", "claude-sonnet-4-6")
        if not api_key:
            raise ValueError("Claude Sonnet: API key is required. Provide it in the UI or set ANTHROPIC_API_KEY in .env")
        logger.info("Claude Sonnet → %s", model)
        return ChatAnthropic(model=model, api_key=api_key)

    # ── AWS Bedrock (Claude Haiku) ────────────────────────────────────
    if provider == "bedrock-haiku":
        import boto3
        from langchain_aws import BedrockLLM
        key_id     = cfg.get("bedrock_key_id")     or os.getenv("AWS_ACCESS_KEY_ID", "")
        secret_key = cfg.get("bedrock_secret_key") or os.getenv("AWS_SECRET_ACCESS_KEY", "")
        region     = cfg.get("bedrock_region")     or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        model_id   = cfg.get("bedrock_model")      or os.getenv("BEDROCK_HAIKU_MODEL_ID", "anthropic.claude-haiku-4-5-20251001-v1:0")
        boto_kwargs = {"region_name": region}
        if key_id and secret_key:
            boto_kwargs["aws_access_key_id"]     = key_id
            boto_kwargs["aws_secret_access_key"] = secret_key
        logger.info("Bedrock → %s @ %s", model_id, region)
        return BedrockLLM(model_id=model_id, client=boto3.client("bedrock-runtime", **boto_kwargs))

    # ── Groq ─────────────────────────────────────────────────────────
    if provider == "groq":
        try:
            from langchain_groq import ChatGroq
        except ImportError:
            raise ValueError("langchain-groq is not installed. Add it to requirements.txt")
        api_key = cfg.get("groq_api_key") or os.getenv("GROQ_API_KEY", "")
        model   = cfg.get("groq_model")   or os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        if not api_key:
            raise ValueError("Groq: API key is required. Provide it in the UI or set GROQ_API_KEY in .env")
        logger.info("Groq → %s", model)
        return ChatGroq(model=model, api_key=api_key)

    # ── Mistral ───────────────────────────────────────────────────────
    if provider == "mistral":
        try:
            from langchain_mistralai import ChatMistralAI
        except ImportError:
            raise ValueError("langchain-mistralai is not installed. Add it to requirements.txt")
        api_key = cfg.get("mistral_api_key") or os.getenv("MISTRAL_API_KEY", "")
        model   = cfg.get("mistral_model")   or os.getenv("MISTRAL_MODEL", "mistral-large-latest")
        if not api_key:
            raise ValueError("Mistral: API key is required. Provide it in the UI or set MISTRAL_API_KEY in .env")
        logger.info("Mistral → %s", model)
        return ChatMistralAI(model=model, api_key=api_key)

    # ── Azure OpenAI ──────────────────────────────────────────────────
    if provider == "azure-openai":
        from langchain_openai import AzureChatOpenAI
        api_key    = cfg.get("azure_oai_key")         or os.getenv("AZURE_OPENAI_API_KEY", "")
        endpoint   = cfg.get("azure_oai_endpoint")    or os.getenv("AZURE_OPENAI_ENDPOINT", "")
        deployment = cfg.get("azure_oai_deployment")  or os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
        api_ver    = cfg.get("azure_oai_api_version") or os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
        if not api_key or not endpoint:
            raise ValueError("Azure OpenAI: API key and endpoint are required.")
        logger.info("Azure OpenAI → deployment=%s endpoint=%s", deployment, endpoint)
        return AzureChatOpenAI(
            azure_deployment=deployment,
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_ver,
        )

    # ── Cohere ────────────────────────────────────────────────────────
    if provider == "cohere":
        try:
            from langchain_cohere import ChatCohere
        except ImportError:
            raise ValueError("langchain-cohere is not installed. Add it to requirements.txt")
        api_key = cfg.get("cohere_api_key") or os.getenv("COHERE_API_KEY", "")
        model   = cfg.get("cohere_model")   or os.getenv("COHERE_MODEL", "command-r-plus")
        if not api_key:
            raise ValueError("Cohere: API key is required. Provide it in the UI or set COHERE_API_KEY in .env")
        logger.info("Cohere → %s", model)
        return ChatCohere(model=model, cohere_api_key=api_key)

    raise ValueError(f"Unknown LLM provider: '{provider}'. Valid: ollama, openai, gemini, deepseek, sonnet, bedrock-haiku, groq, mistral, azure-openai, cohere")


class _MockLLM:
    """Fallback when no LLM is configured."""
    def invoke(self, prompt: str) -> str:
        return "[LLM not configured — select a provider and provide credentials in the UI]"


def _mock_llm() -> _MockLLM:
    return _MockLLM()
