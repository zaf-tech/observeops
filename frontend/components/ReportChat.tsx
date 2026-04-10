"use client";
import { useState, useRef, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  MessageSquare, X, Send, Loader2, Bot, User,
  ChevronDown, Trash2, Copy, Check,
} from "lucide-react";
import { chatStream, type ChatMessage } from "@/lib/api";
import type { LLMConfig } from "@/components/LLMSelector";

interface Props {
  jobId: string;
  reportName?: string;
  llmProvider: string;
  llmConfig?: LLMConfig;
}

const SUGGESTED_QUESTIONS = [
  "What are the top 3 critical risks I should fix first?",
  "Which findings have the highest blast radius?",
  "Draft a Jira ticket for the most critical finding",
  "What would it cost to remediate all critical issues?",
  "Summarise the security posture in 3 bullet points for my CEO",
  "Which IAM findings should I fix this week?",
  "Are there any compliance gaps with SOC 2 or CIS benchmarks?",
  "Give me the exact CLI commands to fix the top 5 issues",
];

export default function ReportChat({ jobId, reportName, llmProvider, llmConfig }: Props) {
  const [isOpen,     setIsOpen]     = useState(false);
  const [messages,   setMessages]   = useState<ChatMessage[]>([]);
  const [input,      setInput]      = useState("");
  const [streaming,  setStreaming]   = useState(false);
  const [copiedIdx,  setCopiedIdx]  = useState<number | null>(null);
  const [showSuggestions, setShowSuggestions] = useState(true);

  const bottomRef    = useRef<HTMLDivElement>(null);
  const inputRef     = useRef<HTMLTextAreaElement>(null);
  const abortRef     = useRef<boolean>(false);

  // Auto-scroll on new content
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Focus input when panel opens
  useEffect(() => {
    if (isOpen) setTimeout(() => inputRef.current?.focus(), 150);
  }, [isOpen]);

  const send = useCallback(async (text: string) => {
    const question = text.trim();
    if (!question || streaming) return;

    setShowSuggestions(false);
    setInput("");
    abortRef.current = false;

    const userMsg: ChatMessage = { role: "user", content: question };
    const assistantMsg: ChatMessage = { role: "assistant", content: "" };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setStreaming(true);

    try {
      const history = [...messages, userMsg];
      const gen = chatStream(
        jobId,
        question,
        history.slice(-10), // send last 10 for context
        llmProvider,
        (llmConfig as unknown as Record<string, unknown>) ?? {},
      );

      for await (const chunk of gen) {
        if (abortRef.current) break;
        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1] = {
            ...updated[updated.length - 1],
            content: updated[updated.length - 1].content + chunk,
          };
          return updated;
        });
      }
    } catch (err: unknown) {
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          role: "assistant",
          content: `**Error:** ${err instanceof Error ? err.message : "Something went wrong. Check backend logs."}`,
        };
        return updated;
      });
    } finally {
      setStreaming(false);
    }
  }, [streaming, messages, jobId, llmProvider, llmConfig]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  };

  const copyMessage = async (content: string, idx: number) => {
    await navigator.clipboard.writeText(content);
    setCopiedIdx(idx);
    setTimeout(() => setCopiedIdx(null), 2000);
  };

  const clearChat = () => {
    setMessages([]);
    setShowSuggestions(true);
  };

  return (
    <>
      {/* ── Floating trigger button ── */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="fixed bottom-6 right-6 z-50 flex items-center gap-2.5 px-4 py-3 bg-gradient-to-r from-teal-500 to-blue-500 text-white font-semibold rounded-full shadow-lg hover:from-teal-400 hover:to-blue-400 hover:scale-105 transition-all duration-200 glow-teal"
        >
          <MessageSquare className="w-5 h-5" />
          Ask AI about this report
        </button>
      )}

      {/* ── Slide-in chat panel ── */}
      <div
        className={`fixed bottom-0 right-0 z-50 flex flex-col transition-all duration-300 ease-in-out
          ${isOpen ? "translate-y-0 opacity-100" : "translate-y-full opacity-0 pointer-events-none"}
          w-full md:w-[480px] h-[85vh] md:h-[75vh] md:bottom-6 md:right-6 md:rounded-2xl
          border border-teal-500/30 bg-[#0f1724] shadow-2xl overflow-hidden`}
        style={{ boxShadow: "0 0 60px rgba(20,184,166,0.15)" }}
      >
        {/* Header */}
        <div className="flex items-center gap-3 px-4 py-3 bg-gradient-to-r from-slate-900 to-slate-800 border-b border-white/10 flex-shrink-0">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-teal-500 to-blue-500 flex items-center justify-center flex-shrink-0">
            <Bot className="w-4 h-4 text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-bold text-white">ObserveOps AI</p>
            <p className="text-[10px] text-gray-500 truncate">
              {reportName ? `Analysing: ${reportName}` : "Report chat assistant"}
              {" · "}{llmProvider}
            </p>
          </div>
          <div className="flex items-center gap-1">
            {messages.length > 0 && (
              <button
                onClick={clearChat}
                title="Clear chat"
                className="p-1.5 text-gray-600 hover:text-red-400 transition-colors rounded-lg hover:bg-white/5"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            )}
            <button
              onClick={() => setIsOpen(false)}
              className="p-1.5 text-gray-600 hover:text-white transition-colors rounded-lg hover:bg-white/5"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Messages area */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 min-h-0">

          {/* Welcome state */}
          {messages.length === 0 && (
            <div className="space-y-4">
              <div className="flex items-start gap-3">
                <div className="w-7 h-7 rounded-full bg-gradient-to-br from-teal-500 to-blue-500 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <Bot className="w-3.5 h-3.5 text-white" />
                </div>
                <div className="rounded-2xl rounded-tl-sm bg-white/5 border border-white/10 px-4 py-3 text-sm text-gray-300 max-w-[85%]">
                  <p>Hi! I have full access to this audit report — the findings, severity data, and executive analysis.</p>
                  <p className="mt-1.5 text-gray-400">Ask me anything: remediation steps, risk explanations, ticket drafts, CLI commands, or compliance gaps.</p>
                </div>
              </div>

              {/* Suggested questions */}
              {showSuggestions && (
                <div className="space-y-2 ml-10">
                  <p className="text-[10px] text-gray-600 uppercase tracking-wider">Suggested questions</p>
                  <div className="flex flex-col gap-1.5">
                    {SUGGESTED_QUESTIONS.slice(0, 5).map((q) => (
                      <button
                        key={q}
                        onClick={() => send(q)}
                        className="text-left text-xs text-teal-400 hover:text-teal-300 px-3 py-2 rounded-lg border border-teal-500/20 bg-teal-500/5 hover:bg-teal-500/10 hover:border-teal-500/40 transition-all duration-150"
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Conversation messages */}
          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex items-start gap-3 ${msg.role === "user" ? "flex-row-reverse" : ""}`}
            >
              {/* Avatar */}
              <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5
                ${msg.role === "user"
                  ? "bg-gradient-to-br from-blue-500 to-indigo-500"
                  : "bg-gradient-to-br from-teal-500 to-blue-500"}`}
              >
                {msg.role === "user"
                  ? <User className="w-3.5 h-3.5 text-white" />
                  : <Bot  className="w-3.5 h-3.5 text-white" />}
              </div>

              {/* Bubble */}
              <div className={`group relative max-w-[85%] rounded-2xl px-4 py-3 text-sm
                ${msg.role === "user"
                  ? "rounded-tr-sm bg-gradient-to-br from-teal-600/30 to-blue-600/30 border border-teal-500/30 text-gray-200"
                  : "rounded-tl-sm bg-white/5 border border-white/10 text-gray-300"}`}
              >
                {/* Streaming indicator */}
                {msg.role === "assistant" && !msg.content && streaming && (
                  <div className="flex gap-1 py-1">
                    <span className="w-1.5 h-1.5 bg-teal-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                    <span className="w-1.5 h-1.5 bg-teal-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                    <span className="w-1.5 h-1.5 bg-teal-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                  </div>
                )}

                {/* Content — markdown for assistant, plain for user */}
                {msg.role === "assistant" ? (
                  <div className="prose prose-invert prose-sm max-w-none chat-markdown">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                    {streaming && idx === messages.length - 1 && msg.content && (
                      <span className="inline-block w-0.5 h-3.5 bg-teal-400 animate-pulse ml-0.5 align-middle" />
                    )}
                  </div>
                ) : (
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                )}

                {/* Copy button — shows on hover for completed assistant messages */}
                {msg.role === "assistant" && msg.content && !(streaming && idx === messages.length - 1) && (
                  <button
                    onClick={() => copyMessage(msg.content, idx)}
                    className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 p-1 rounded text-gray-600 hover:text-teal-400 transition-all"
                    title="Copy"
                  >
                    {copiedIdx === idx
                      ? <Check className="w-3 h-3 text-teal-400" />
                      : <Copy  className="w-3 h-3" />}
                  </button>
                )}
              </div>
            </div>
          ))}

          {/* More suggestions after first answer */}
          {messages.length >= 2 && !streaming && (
            <div className="ml-10">
              <details className="group">
                <summary className="cursor-pointer text-[10px] text-gray-600 hover:text-gray-400 flex items-center gap-1 list-none">
                  <ChevronDown className="w-3 h-3 transition-transform group-open:rotate-180" />
                  More questions to ask
                </summary>
                <div className="mt-2 flex flex-col gap-1.5">
                  {SUGGESTED_QUESTIONS.slice(5).map((q) => (
                    <button
                      key={q}
                      onClick={() => send(q)}
                      className="text-left text-xs text-teal-400 hover:text-teal-300 px-3 py-2 rounded-lg border border-teal-500/20 bg-teal-500/5 hover:bg-teal-500/10 transition-all duration-150"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </details>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input area */}
        <div className="flex-shrink-0 px-4 py-3 border-t border-white/10 bg-slate-900/50">
          <div className="flex items-end gap-2">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about findings, risks, fixes, tickets…"
              rows={1}
              disabled={streaming}
              className="flex-1 bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 text-sm text-gray-200 placeholder-gray-600 resize-none focus:outline-none focus:border-teal-500/40 focus:bg-white/8 transition-colors disabled:opacity-50 max-h-28"
              style={{ fieldSizing: "content" } as React.CSSProperties}
            />
            <button
              onClick={() => streaming ? (abortRef.current = true) : send(input)}
              disabled={!streaming && !input.trim()}
              className={`flex-shrink-0 p-2.5 rounded-xl font-medium transition-all duration-200
                ${streaming
                  ? "bg-red-500/20 border border-red-500/30 text-red-400 hover:bg-red-500/30"
                  : "bg-teal-500/20 border border-teal-500/30 text-teal-400 hover:bg-teal-500/30 disabled:opacity-30 disabled:cursor-not-allowed"}`}
              title={streaming ? "Stop" : "Send (Enter)"}
            >
              {streaming
                ? <Loader2 className="w-4 h-4 animate-spin" />
                : <Send    className="w-4 h-4" />}
            </button>
          </div>
          <p className="text-[9px] text-gray-700 mt-1.5 text-center">
            Enter to send · Shift+Enter for new line · Answers grounded in your report data
          </p>
        </div>
      </div>

      {/* Backdrop on mobile */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-40 md:hidden"
          onClick={() => setIsOpen(false)}
        />
      )}
    </>
  );
}
