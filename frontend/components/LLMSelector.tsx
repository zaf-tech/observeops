"use client";
import { Cpu, ChevronDown, Eye, EyeOff, RefreshCw, Check, Loader2 } from "lucide-react";
import { useState, useCallback } from "react";

// ── Provider catalogue ───────────────────────────────────────────────
export interface LLMOption {
  value:   string;
  label:   string;
  desc:    string;
  badge:   string;
  icon:    string;
  fields?: AuthField[];    // extra auth inputs
  note?:   string;         // helper text shown below fields
}

interface AuthField {
  key:         string;          // maps to LLMConfig key
  label:       string;
  placeholder?: string;
  type?:       "text" | "password" | "url";
  required?:   boolean;
}

export const LLM_OPTIONS: LLMOption[] = [
  {
    value: "ollama",
    label: "Ollama (Local)",
    desc:  "Free · private · runs on your machine",
    badge: "FREE",
    icon:  "🦙",
    fields: [
      { key: "ollama_url",   label: "Ollama Base URL", placeholder: "http://host.docker.internal:11434", type: "url" },
      { key: "ollama_model", label: "Model",           placeholder: "llama3.2 (pick from list below)" },
    ],
    note: "Leave blank to use defaults from .env — or paste your URL and click Refresh.",
  },
  {
    value: "openai",
    label: "OpenAI",
    desc:  "GPT-4o, GPT-4o-mini — industry standard",
    badge: "API KEY",
    icon:  "🟢",
    fields: [
      { key: "openai_api_key", label: "API Key",  placeholder: "sk-...", type: "password", required: true },
      { key: "openai_model",   label: "Model",    placeholder: "gpt-4o-mini" },
    ],
    note: "Get your key at platform.openai.com → API keys",
  },
  {
    value: "gemini",
    label: "Google Gemini",
    desc:  "Gemini 2.0 Flash-Lite — fast & cheap",
    badge: "LOW COST",
    icon:  "🌀",
    fields: [
      { key: "google_api_key", label: "Google API Key", placeholder: "AIza...", type: "password", required: true },
      { key: "gemini_model",   label: "Model",          placeholder: "gemini-2.0-flash-lite" },
    ],
    note: "Get key at aistudio.google.com → Get API key",
  },
  {
    value: "deepseek",
    label: "DeepSeek",
    desc:  "DeepSeek V3 — strong reasoning, low cost",
    badge: "LOW COST",
    icon:  "🔷",
    fields: [
      { key: "deepseek_api_key", label: "API Key", placeholder: "sk-...", type: "password", required: true },
      { key: "deepseek_model",   label: "Model",   placeholder: "deepseek-chat" },
    ],
    note: "Get key at platform.deepseek.com",
  },
  {
    value: "sonnet",
    label: "Claude Sonnet (Anthropic)",
    desc:  "Best quality executive reports",
    badge: "PREMIUM",
    icon:  "⚡",
    fields: [
      { key: "anthropic_api_key", label: "API Key",      placeholder: "sk-ant-...", type: "password", required: true },
      { key: "claude_model",      label: "Model",        placeholder: "claude-sonnet-4-6" },
    ],
    note: "Get key at console.anthropic.com → API Keys",
  },
  {
    value: "bedrock-haiku",
    label: "AWS Bedrock (Claude Haiku)",
    desc:  "~$0.001/run · uses your AWS credentials",
    badge: "AWS",
    icon:  "☁️",
    fields: [
      { key: "bedrock_key_id",     label: "AWS Access Key ID",     placeholder: "AKIA...",   type: "password", required: true },
      { key: "bedrock_secret_key", label: "AWS Secret Access Key", placeholder: "••••••••", type: "password", required: true },
      { key: "bedrock_region",     label: "AWS Region",            placeholder: "us-east-1" },
      { key: "bedrock_model",      label: "Model ID",              placeholder: "anthropic.claude-haiku-4-5-20251001-v1:0" },
    ],
    note: "Bedrock must be enabled in your AWS account for the chosen region.",
  },
  {
    value: "groq",
    label: "Groq",
    desc:  "Ultra-fast inference — Llama / Mixtral",
    badge: "FAST",
    icon:  "⚡",
    fields: [
      { key: "groq_api_key", label: "API Key", placeholder: "gsk_...", type: "password", required: true },
      { key: "groq_model",   label: "Model",   placeholder: "llama-3.1-8b-instant" },
    ],
    note: "Get key at console.groq.com — free tier available.",
  },
  {
    value: "mistral",
    label: "Mistral AI",
    desc:  "Mistral Large / Small — European provider",
    badge: "API KEY",
    icon:  "🌪️",
    fields: [
      { key: "mistral_api_key", label: "API Key", placeholder: "••••••••", type: "password", required: true },
      { key: "mistral_model",   label: "Model",   placeholder: "mistral-large-latest" },
    ],
    note: "Get key at console.mistral.ai",
  },
  {
    value: "azure-openai",
    label: "Azure OpenAI",
    desc:  "OpenAI models via Microsoft Azure",
    badge: "ENTERPRISE",
    icon:  "🔷",
    fields: [
      { key: "azure_oai_key",        label: "API Key",          placeholder: "••••••••",                          type: "password", required: true },
      { key: "azure_oai_endpoint",   label: "Endpoint URL",     placeholder: "https://my-resource.openai.azure.com", type: "url", required: true },
      { key: "azure_oai_deployment", label: "Deployment Name",  placeholder: "gpt-4o" },
      { key: "azure_oai_api_version",label: "API Version",      placeholder: "2024-02-01" },
    ],
    note: "Create a resource in Azure Portal → Azure AI services → Azure OpenAI.",
  },
  {
    value: "cohere",
    label: "Cohere",
    desc:  "Command R+ — great for summarisation",
    badge: "API KEY",
    icon:  "🌊",
    fields: [
      { key: "cohere_api_key", label: "API Key", placeholder: "••••••••", type: "password", required: true },
      { key: "cohere_model",   label: "Model",   placeholder: "command-r-plus" },
    ],
    note: "Get key at dashboard.cohere.com",
  },
];

// ── Types shared with page.tsx ────────────────────────────────────────
export interface LLMConfig {
  provider: string;
  // Ollama
  ollama_url?:    string;
  ollama_model?:  string;
  // OpenAI
  openai_api_key?: string;
  openai_model?:  string;
  // Gemini
  google_api_key?: string;
  gemini_model?:  string;
  // DeepSeek
  deepseek_api_key?: string;
  deepseek_model?:  string;
  // Anthropic / Sonnet
  anthropic_api_key?: string;
  claude_model?:      string;
  // Bedrock
  bedrock_key_id?:     string;
  bedrock_secret_key?: string;
  bedrock_region?:     string;
  bedrock_model?:      string;
  // Groq
  groq_api_key?: string;
  groq_model?:   string;
  // Mistral
  mistral_api_key?: string;
  mistral_model?:   string;
  // Azure OpenAI
  azure_oai_key?:         string;
  azure_oai_endpoint?:    string;
  azure_oai_deployment?:  string;
  azure_oai_api_version?: string;
  // Cohere
  cohere_api_key?: string;
  cohere_model?:   string;
}

// ── Component ────────────────────────────────────────────────────────
interface Props {
  label:    string;
  config:   LLMConfig;
  onChange: (cfg: LLMConfig) => void;
}

export default function LLMSelector({ label, config, onChange }: Props) {
  const [open,      setOpen]      = useState(false);
  const [showKeys,  setShowKeys]  = useState<Set<string>>(new Set());
  const [ollamaModels, setOllamaModels] = useState<string[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [modelsError,   setModelsError]   = useState<string | null>(null);

  const selected = LLM_OPTIONS.find((o) => o.value === config.provider) ?? LLM_OPTIONS[0];

  const setProvider = (v: string) => {
    onChange({ ...config, provider: v });
    setOpen(false);
    setOllamaModels([]);
    setModelsError(null);
  };

  const setField = (key: string, value: string) => {
    onChange({ ...config, [key]: value });
  };

  const toggleShow = (key: string) =>
    setShowKeys((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });

  const loadOllamaModels = useCallback(async () => {
    const base = (config.ollama_url || "http://host.docker.internal:11434").replace(/\/$/, "");
    setLoadingModels(true);
    setModelsError(null);
    setOllamaModels([]);
    try {
      const res = await fetch(`${base}/api/tags`, { signal: AbortSignal.timeout(5000) });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const names: string[] = (data.models || []).map((m: { name: string }) => m.name);
      if (names.length === 0) {
        setModelsError("No models installed. Run: ollama pull llama3.2");
      } else {
        setOllamaModels(names);
      }
    } catch (e: unknown) {
      setModelsError(e instanceof Error ? e.message : "Could not reach Ollama");
    } finally {
      setLoadingModels(false);
    }
  }, [config.ollama_url]);

  return (
    <div className="space-y-3">
      <label className="block text-sm text-gray-400">{label}</label>

      {/* Provider dropdown trigger */}
      <div className="relative">
        <button
          type="button"
          onClick={() => setOpen((p) => !p)}
          className="w-full flex items-center justify-between gap-3 px-4 py-3 bg-white/5 border border-teal-500/20 rounded-xl hover:border-teal-500/40 transition-colors text-left"
        >
          <div className="flex items-center gap-3">
            <span className="text-lg leading-none">{selected.icon}</span>
            <div>
              <p className="text-sm text-white font-medium">{selected.label}</p>
              <p className="text-xs text-gray-500">{selected.desc}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <BadgePill text={selected.badge} />
            <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform ${open ? "rotate-180" : ""}`} />
          </div>
        </button>

        {open && (
          <div className="absolute z-50 top-full mt-1 left-0 right-0 bg-gray-900 border border-teal-500/30 rounded-xl shadow-2xl overflow-hidden max-h-80 overflow-y-auto">
            {LLM_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setProvider(opt.value)}
                className={`w-full flex items-center gap-3 px-4 py-3 hover:bg-teal-500/10 transition-colors text-left
                  ${opt.value === config.provider ? "bg-teal-500/15 border-l-2 border-teal-400" : ""}`}
              >
                <span className="text-base leading-none flex-shrink-0">{opt.icon}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-white font-medium">{opt.label}</p>
                  <p className="text-xs text-gray-500 truncate">{opt.desc}</p>
                </div>
                <BadgePill text={opt.badge} />
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Auth fields for selected provider */}
      {selected.fields && selected.fields.length > 0 && (
        <div className="rounded-xl border border-white/8 bg-white/3 p-4 space-y-3">

          {/* Ollama: URL + refresh + model picker */}
          {config.provider === "ollama" && (
            <>
              <AuthInput
                field={selected.fields[0]}
                value={config.ollama_url ?? ""}
                showKeys={showKeys}
                onToggleShow={toggleShow}
                onChange={(v) => setField("ollama_url", v)}
              />
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs text-gray-400">
                    Model
                  </label>
                  <button
                    type="button"
                    onClick={loadOllamaModels}
                    disabled={loadingModels}
                    className="flex items-center gap-1 text-xs text-teal-400 hover:text-teal-300 disabled:opacity-50 transition-colors"
                  >
                    {loadingModels
                      ? <Loader2 className="w-3 h-3 animate-spin" />
                      : <RefreshCw className="w-3 h-3" />}
                    {loadingModels ? "Loading…" : "Refresh models"}
                  </button>
                </div>

                {ollamaModels.length > 0 ? (
                  <div className="space-y-1">
                    {ollamaModels.map((m) => (
                      <button
                        key={m}
                        type="button"
                        onClick={() => setField("ollama_model", m)}
                        className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-all
                          ${config.ollama_model === m
                            ? "bg-teal-500/20 border border-teal-500/40 text-teal-300"
                            : "bg-white/5 border border-white/8 text-gray-300 hover:border-teal-500/30"}`}
                      >
                        <span className="font-mono text-xs">{m}</span>
                        {config.ollama_model === m && <Check className="w-3.5 h-3.5 text-teal-400" />}
                      </button>
                    ))}
                  </div>
                ) : (
                  <input
                    type="text"
                    placeholder="llama3.2 (or click Refresh models)"
                    value={config.ollama_model ?? ""}
                    onChange={(e) => setField("ollama_model", e.target.value)}
                    className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-white placeholder-gray-600 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/30 transition-colors"
                    autoComplete="off"
                  />
                )}

                {modelsError && (
                  <p className="text-xs text-red-400 mt-1">{modelsError}</p>
                )}
              </div>
            </>
          )}

          {/* All other providers: render auth fields normally */}
          {config.provider !== "ollama" && selected.fields.map((field) => (
            <AuthInput
              key={field.key}
              field={field}
              value={((config as unknown) as Record<string, string>)[field.key] ?? ""}
              showKeys={showKeys}
              onToggleShow={toggleShow}
              onChange={(v) => setField(field.key, v)}
            />
          ))}

          {selected.note && (
            <p className="text-xs text-gray-600 pt-1">{selected.note}</p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Auth input field ─────────────────────────────────────────────────
function AuthInput({
  field, value, showKeys, onToggleShow, onChange,
}: {
  field: AuthField;
  value: string;
  showKeys: Set<string>;
  onToggleShow: (key: string) => void;
  onChange: (v: string) => void;
}) {
  const isPassword = field.type === "password";
  const visible    = showKeys.has(field.key);

  return (
    <div>
      <label className="block text-xs text-gray-400 mb-1">
        {field.label}
        {field.required && <span className="text-teal-400 ml-1">*</span>}
      </label>
      <div className="relative">
        <input
          type={isPassword && !visible ? "password" : "text"}
          placeholder={field.placeholder}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full px-3 py-2 pr-9 bg-white/5 border border-white/10 rounded-lg text-sm text-white placeholder-gray-600 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/30 transition-colors font-mono"
          autoComplete="off"
          spellCheck={false}
        />
        {isPassword && (
          <button
            type="button"
            onClick={() => onToggleShow(field.key)}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
          >
            {visible ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        )}
      </div>
    </div>
  );
}

// ── Badge pill ───────────────────────────────────────────────────────
function BadgePill({ text }: { text: string }) {
  const map: Record<string, string> = {
    FREE:       "bg-green-500/20 text-green-400",
    "LOW COST": "bg-teal-500/20 text-teal-400",
    "API KEY":  "bg-blue-500/20 text-blue-400",
    FAST:       "bg-yellow-500/20 text-yellow-400",
    AWS:        "bg-orange-500/20 text-orange-400",
    PREMIUM:    "bg-purple-500/20 text-purple-400",
    ENTERPRISE: "bg-indigo-500/20 text-indigo-400",
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium whitespace-nowrap flex-shrink-0 ${map[text] ?? "bg-gray-500/20 text-gray-400"}`}>
      {text}
    </span>
  );
}
