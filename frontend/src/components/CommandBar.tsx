"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { MessageSquare, Send, Mic, MicOff, X, Bell, ChevronRight } from "lucide-react";
import { nlp } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Message = {
  role: "user" | "agent";
  text: string;
  navigateTo?: string | null;
};

type Nudge = {
  type: string;
  message: string;
  navigateTo: string | null;
  priority: "high" | "medium" | "low";
};

export default function CommandBar() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [listening, setListening] = useState(false);
  const [nudges, setNudges] = useState<Nudge[]>([]);
  const [showNudge, setShowNudge] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const recognitionRef = useRef<any>(null);
  const router = useRouter();

  // Keyboard shortcut: Cmd+K / Ctrl+K
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen(prev => !prev);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // Proactive nudge polling — check every 60 seconds
  useEffect(() => {
    const fetchNudges = async () => {
      const token = typeof window !== "undefined" ? localStorage.getItem("kairo_token") : null;
      if (!token) return;
      try {
        const res = await fetch(`${API_URL}/api/nlp/nudges`, {
          headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        });
        if (res.ok) {
          const data = await res.json();
          const newNudges = data.nudges || [];
          if (newNudges.length > 0) {
            setNudges(newNudges);
            // Auto-show nudge banner if high priority
            const hasHigh = newNudges.some((n: Nudge) => n.priority === "high");
            if (hasHigh && !open) {
              setShowNudge(true);
            }
          }
        }
      } catch { /* ignore */ }
    };

    fetchNudges();
    const interval = setInterval(fetchNudges, 60000);
    return () => clearInterval(interval);
  }, [open]);

  // Focus input when opened
  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 100);
      setShowNudge(false);
      // Surface nudges as agent messages when opening
      if (nudges.length > 0 && messages.length === 0) {
        const nudgeMsgs: Message[] = nudges.map(n => ({
          role: "agent" as const,
          text: n.message,
          navigateTo: n.navigateTo,
        }));
        setMessages(nudgeMsgs);
        setNudges([]);
      }
    }
  }, [open, nudges, messages.length]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const sendCommand = useCallback(async (text: string) => {
    if (!text.trim()) return;

    const userMsg: Message = { role: "user", text: text.trim() };
    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await nlp.command({ text: text.trim() });
      const agentMsg: Message = { role: "agent", text: res.response, navigateTo: res.navigateTo };
      setMessages(prev => [...prev, agentMsg]);

      if (res.navigateTo) {
        setTimeout(() => {
          router.push(res.navigateTo!);
        }, 1200);
      }
    } catch {
      setMessages(prev => [
        ...prev,
        { role: "agent", text: "Sorry, something went wrong. Please try again." },
      ]);
    } finally {
      setLoading(false);
    }
  }, [router]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendCommand(input);
  };

  const toggleMic = useCallback(() => {
    if (listening) {
      recognitionRef.current?.stop();
      recognitionRef.current = null;
      setListening(false);
      return;
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setMessages(prev => [...prev, { role: "agent", text: "Speech recognition is not supported in this browser. Try Chrome or Edge." }]);
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = "en-US";
      recognition.maxAlternatives = 1;

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      recognition.onresult = (event: any) => {
        const result = event.results[event.results.length - 1];
        const transcript = result[0].transcript;
        setInput(transcript);
        if (result.isFinal) {
          setListening(false);
          recognitionRef.current = null;
          if (transcript.trim()) {
            sendCommand(transcript.trim());
          }
        }
      };

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      recognition.onerror = (event: any) => {
        setListening(false);
        recognitionRef.current = null;
        const errorMap: Record<string, string> = {
          "not-allowed": "Microphone access denied. Please allow mic permission in browser settings.",
          "no-speech": "No speech detected. Please try again.",
          "network": "Network error — speech recognition requires an internet connection.",
          "aborted": "Listening cancelled.",
        };
        const msg = errorMap[event.error] || `Mic error: ${event.error}. Try again.`;
        if (event.error !== "aborted") {
          setMessages(prev => [...prev, { role: "agent", text: msg }]);
        }
      };

      recognition.onend = () => {
        setListening(false);
        recognitionRef.current = null;
      };

      recognitionRef.current = recognition;
      recognition.start();
      setListening(true);
    } catch (err) {
      setMessages(prev => [...prev, { role: "agent", text: "Could not start speech recognition. Please check mic permissions." }]);
      setListening(false);
    }
  }, [listening, sendCommand]);

  const handleNudgeClick = (nudge: Nudge) => {
    setShowNudge(false);
    setOpen(true);
    setMessages(prev => [...prev, { role: "agent", text: nudge.message, navigateTo: nudge.navigateTo }]);
    if (nudge.navigateTo) {
      setTimeout(() => router.push(nudge.navigateTo!), 1500);
    }
  };

  // Nudge toast banner (shows when CommandBar is closed)
  if (!open && showNudge && nudges.length > 0) {
    const topNudge = nudges.find(n => n.priority === "high") || nudges[0];
    return (
      <div className="fixed bottom-6 right-6 z-30 flex flex-col items-end gap-2">
        {/* Nudge toast */}
        <button
          onClick={() => handleNudgeClick(topNudge)}
          className="flex items-center gap-3 px-4 py-3 max-w-xs rounded-2xl bg-white dark:bg-[#1a1128] border border-amber-400/30 dark:border-amber-500/20 shadow-lg shadow-amber-500/10 text-left transition-all hover:shadow-xl animate-in slide-in-from-bottom-2"
        >
          <div className="w-8 h-8 rounded-full bg-amber-100 dark:bg-amber-500/15 flex items-center justify-center flex-shrink-0">
            <Bell className="w-4 h-4 text-amber-600 dark:text-amber-400" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-slate-800 dark:text-white line-clamp-2">{topNudge.message}</p>
            <p className="text-[10px] text-violet-600 dark:text-violet-400 mt-0.5 flex items-center gap-0.5">
              Tap to act <ChevronRight className="w-3 h-3" />
            </p>
          </div>
          <button
            onClick={(e) => { e.stopPropagation(); setShowNudge(false); }}
            className="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-[#2d2247] text-slate-300 dark:text-slate-600"
          >
            <X className="w-3 h-3" />
          </button>
        </button>

        {/* Main pill underneath */}
        <button
          onClick={() => setOpen(true)}
          className="flex items-center gap-2 px-4 py-2.5 rounded-full bg-violet-600 hover:bg-violet-700 text-white text-sm font-medium shadow-lg shadow-violet-600/25 transition-all hover:shadow-xl hover:shadow-violet-600/30"
        >
          <MessageSquare className="w-4 h-4" />
          <span>Talk to Kairo</span>
          {nudges.length > 0 && (
            <span className="w-5 h-5 rounded-full bg-amber-400 text-[10px] font-bold text-white flex items-center justify-center">
              {nudges.length}
            </span>
          )}
          <kbd className="ml-1 text-[10px] opacity-60 bg-white/15 px-1.5 py-0.5 rounded">&#x2318;K</kbd>
        </button>
      </div>
    );
  }

  // Collapsed pill (no nudges)
  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-30 flex items-center gap-2 px-4 py-2.5 rounded-full bg-violet-600 hover:bg-violet-700 text-white text-sm font-medium shadow-lg shadow-violet-600/25 transition-all hover:shadow-xl hover:shadow-violet-600/30"
      >
        <MessageSquare className="w-4 h-4" />
        <span className="hidden sm:inline">Talk to Kairo</span>
        {nudges.length > 0 && (
          <span className="w-5 h-5 rounded-full bg-amber-400 text-[10px] font-bold text-white flex items-center justify-center">
            {nudges.length}
          </span>
        )}
        <kbd className="ml-1 text-[10px] opacity-60 bg-white/15 px-1.5 py-0.5 rounded hidden sm:inline">&#x2318;K</kbd>
      </button>
    );
  }

  // Expanded panel
  return (
    <div className="fixed bottom-6 right-6 z-30 w-[calc(100vw-3rem)] sm:w-[360px] max-h-[400px] flex flex-col bg-white dark:bg-[#1a1128] rounded-2xl border border-slate-200 dark:border-[#2d2247] shadow-2xl shadow-black/10 dark:shadow-black/30">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100 dark:border-[#2d2247]">
        <div className="flex items-center gap-2">
          <MessageSquare className="w-4 h-4 text-violet-600 dark:text-violet-400" />
          <span className="text-sm font-medium text-slate-800 dark:text-white">Talk to Kairo</span>
        </div>
        <button
          onClick={() => setOpen(false)}
          className="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-[#2d2247] text-slate-400 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Chat History */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3 min-h-[120px] max-h-[260px]">
        {messages.length === 0 && (
          <div className="text-center py-4">
            <p className="text-xs text-slate-400 dark:text-slate-500 mb-3">
              Try saying:
            </p>
            <div className="space-y-1.5">
              {[
                "Set up my agent, connect Gmail, protect mornings",
                "Toggle ghost mode",
                "My commitments",
                "Weekly report",
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => sendCommand(suggestion)}
                  className="block w-full text-left px-3 py-1.5 rounded-lg text-xs text-slate-500 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-[#2d2247]/50 transition-colors"
                >
                  &quot;{suggestion}&quot;
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] rounded-xl text-[13px] leading-relaxed ${
              msg.role === "user"
                ? "bg-violet-600 text-white rounded-br-sm px-3 py-2"
                : "bg-slate-100 dark:bg-[#2d2247] text-slate-800 dark:text-slate-200 rounded-bl-sm px-3 py-2"
            }`}>
              {msg.text}
              {msg.role === "agent" && msg.navigateTo && (
                <button
                  onClick={() => router.push(msg.navigateTo!)}
                  className="block mt-1.5 text-[11px] text-violet-600 dark:text-violet-400 hover:underline flex items-center gap-0.5"
                >
                  Go to page <ChevronRight className="w-3 h-3" />
                </button>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-slate-100 dark:bg-[#2d2247] px-3 py-2 rounded-xl rounded-bl-sm">
              <div className="flex gap-1">
                <div className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                <div className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                <div className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="flex items-center gap-2 px-3 py-3 border-t border-slate-100 dark:border-[#2d2247]">
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Type a command..."
          disabled={loading}
          className="flex-1 bg-slate-50 dark:bg-[#0f0a1a] border border-slate-200 dark:border-[#2d2247] rounded-lg px-3 py-2 text-sm text-slate-800 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-violet-500/30 focus:border-violet-500 disabled:opacity-50 transition-colors"
        />
        <button
          type="button"
          onClick={toggleMic}
          className={`relative p-2 rounded-lg transition-colors ${
            listening
              ? "bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-400"
              : "hover:bg-slate-100 dark:hover:bg-[#2d2247] text-slate-400"
          }`}
          title={listening ? "Stop listening" : "Voice input"}
        >
          {listening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
          {listening && (
            <span className="absolute inset-0 rounded-lg border-2 border-red-400 dark:border-red-500 animate-ping opacity-30" />
          )}
        </button>
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="p-2 rounded-lg bg-violet-600 hover:bg-violet-700 text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  );
}
