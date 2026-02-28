"use client";
import Link from "next/link";
import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import { ThemeProvider, useTheme } from "@/lib/theme";
import { Sun, Moon, ChevronDown, ArrowRight, Shield, Zap, Users, Brain, Mic, BarChart3, Play, Pause, Volume2, CheckSquare, Forward, Heart, GitCompare, Store } from "lucide-react";

function useInView(opts = { threshold: 0.15 }) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setVisible(true); obs.disconnect(); } }, opts);
    obs.observe(el);
    return () => obs.disconnect();
  }, []);
  return { ref, visible };
}

function useCounter(end: number, duration = 1400, start = false, decimals = 0) {
  const [val, setVal] = useState(0);
  useEffect(() => {
    if (!start) return;
    let raf: number, t0: number;
    const step = (ts: number) => {
      if (!t0) t0 = ts;
      const p = Math.min((ts - t0) / duration, 1);
      setVal(parseFloat((p * end).toFixed(decimals)));
      if (p < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [start, end, duration, decimals]);
  return val;
}

function Reveal({ children, className = "", delay = 0 }: { children: React.ReactNode; className?: string; delay?: number }) {
  const { ref, visible } = useInView();
  return (
    <div ref={ref} className={className} style={{ opacity: visible ? 1 : 0, transform: visible ? "translateY(0)" : "translateY(32px)", transition: `opacity 0.7s ease ${delay}ms, transform 0.7s ease ${delay}ms` }}>
      {children}
    </div>
  );
}

/* ── Deterministic pseudo-random for waveform (avoids hydration mismatch) ── */
function seededWaveform(seed: number): number[] {
  const bars: number[] = [];
  let s = seed;
  for (let i = 0; i < 40; i++) {
    s = (s * 16807 + 7) % 2147483647;
    const r = (s % 1000) / 1000;
    bars.push(Math.sin(i * 0.4) * 0.5 + r * 0.5);
  }
  return bars;
}

/* ── Audio sample player component ── */
function AudioSample({ title, subtitle, transcript, duration, lang, seed }: {
  title: string; subtitle: string; transcript: string; duration: string; lang: string; seed: number;
}) {
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const waveform = useMemo(() => seededWaveform(seed), [seed]);

  const stopPlayback = useCallback(() => {
    if (audioRef.current) { audioRef.current.pause(); audioRef.current = null; }
    window.speechSynthesis?.cancel();
    if (intervalRef.current) clearInterval(intervalRef.current);
    setPlaying(false);
    setProgress(0);
  }, []);

  const startProgressBar = useCallback((totalMs: number) => {
    const step = 100;
    intervalRef.current = setInterval(() => {
      setProgress(prev => {
        if (prev >= 98) return prev;
        return prev + (step / totalMs) * 100;
      });
    }, step);
  }, []);

  const playWithBrowserTTS = useCallback(() => {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(transcript);
    utter.lang = lang === "Hindi" ? "hi-IN" : "en-US";
    utter.rate = 0.95;
    const voices = window.speechSynthesis.getVoices();
    const preferred = voices.find(v =>
      lang === "Hindi" ? v.lang.startsWith("hi") : (v.name.includes("Samantha") || v.name.includes("Google") || v.lang === "en-US")
    );
    if (preferred) utter.voice = preferred;
    utter.onend = () => { setPlaying(false); setProgress(100); if (intervalRef.current) clearInterval(intervalRef.current); setTimeout(() => setProgress(0), 1000); };
    utter.onerror = () => stopPlayback();
    window.speechSynthesis.speak(utter);
    const totalMs = parseInt(duration.split(":")[0]) * 60000 + parseInt(duration.split(":")[1]) * 1000;
    startProgressBar(totalMs);
  }, [transcript, lang, duration, stopPlayback, startProgressBar]);

  const togglePlay = useCallback(async () => {
    if (playing) { stopPlayback(); return; }
    setPlaying(true);
    setProgress(0);

    // Try Edge TTS backend first (AI voice), fall back to browser TTS
    const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    try {
      const langCode = lang === "Hindi" ? "hi" : "en";
      const res = await fetch(`${API}/api/tts/speak?text=${encodeURIComponent(transcript)}&lang=${langCode}`);
      if (res.ok && res.headers.get("content-type")?.includes("audio")) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        audioRef.current = audio;
        audio.onended = () => { setPlaying(false); setProgress(100); if (intervalRef.current) clearInterval(intervalRef.current); setTimeout(() => setProgress(0), 1000); URL.revokeObjectURL(url); };
        audio.onerror = () => { stopPlayback(); playWithBrowserTTS(); setPlaying(true); };
        audio.ontimeupdate = () => { if (audio.duration) setProgress((audio.currentTime / audio.duration) * 100); };
        audio.play();
        return;
      }
    } catch { /* fall through to browser TTS */ }
    playWithBrowserTTS();
  }, [playing, transcript, lang, stopPlayback, playWithBrowserTTS]);

  useEffect(() => { return () => stopPlayback(); }, [stopPlayback]);

  return (
    <div className="bg-white dark:bg-[#1e1533] rounded-2xl p-6 border border-slate-200 dark:border-[#2d2247] hover:shadow-lg hover:border-violet-200 dark:hover:border-violet-500/30 transition-all duration-300 group">
      <div className="flex items-start gap-4">
        <button onClick={togglePlay}
          className={`w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 shadow-lg transition-colors ${playing ? "bg-slate-700 shadow-slate-700/20 hover:bg-slate-800" : "bg-violet-600 shadow-violet-600/20 hover:bg-violet-700"}`}>
          {playing ? <Pause className="w-5 h-5 text-white" /> : <Play className="w-5 h-5 text-white ml-0.5" />}
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="text-slate-900 dark:text-white font-semibold text-sm">{title}</h3>
            <span className="px-2 py-0.5 rounded-full bg-violet-50 dark:bg-violet-500/10 text-violet-600 dark:text-violet-400 text-[10px] font-medium">{lang}</span>
          </div>
          <p className="text-slate-400 text-xs mb-3">{subtitle}</p>
          {/* Waveform / progress */}
          <div className="relative h-8 flex items-center gap-[2px]">
            {waveform.map((h, i) => {
              const filled = (i / 40) * 100 <= progress;
              return (
                <div key={i} className={`flex-1 rounded-full transition-colors ${filled ? "bg-violet-500" : "bg-slate-200 dark:bg-[#2d2247]"}`}
                  style={{ height: `${Math.round(Math.max(4, h * 28))}px` }} />
              );
            })}
            <span className="absolute right-0 -top-1 text-[10px] text-slate-400">{duration}</span>
          </div>
        </div>
      </div>
      <p className="mt-4 text-xs text-slate-500 dark:text-slate-400 leading-relaxed italic border-l-2 border-violet-200 dark:border-violet-500/30 pl-3">
        &ldquo;{transcript}&rdquo;
      </p>
    </div>
  );
}

const platformFeatures = [
  { icon: Brain, title: "Command Center Dashboard", problem: "No visibility into what's happening", desc: "Real-time overview of all agent activity, decisions made, and tasks in progress." },
  { icon: Zap, title: "Energy-Aware Scheduling", problem: "Meetings eat your best hours", desc: "Protects deep work hours, batches meetings during energy dips, and auto-declines conflicts." },
  { icon: Users, title: "Relationship Intelligence", problem: "People fall through the cracks", desc: "Maps every contact, tracks tone shifts, and alerts you before relationships fade." },
  { icon: Shield, title: "Ghost Mode Autopilot", problem: "Routine messages pile up", desc: "Drafts and sends messages autonomously with full reasoning traces and confidence scores." },
  { icon: Mic, title: "Bilingual Voice Agent", problem: "Switching languages is friction", desc: "Speak to Kairo in English or Hindi. Real-time voice via LiveKit with natural TTS." },
  { icon: BarChart3, title: "Weekly Self-Report", problem: "No idea where your time goes", desc: "Quantified productivity: hours saved, accuracy trends, relationship health insights." },
  { icon: CheckSquare, title: "Commitment Tracker", problem: "Promises slip through the cracks", desc: "Detects promises in your messages, tracks deadlines, and nudges before things go overdue." },
  { icon: Forward, title: "Smart Delegation", problem: "Wrong person, wrong task", desc: "Identifies the best teammate for incoming work based on expertise, bandwidth, and relationship strength." },
  { icon: Heart, title: "Burnout Shield", problem: "You don't see burnout coming", desc: "Predicts burnout risk from 90 days of patterns. Identifies peak productivity windows and generates interventions." },
  { icon: Users, title: "Agent Mesh", problem: "Coordination is manual overhead", desc: "Your agent negotiates schedules, hands off tasks, and coordinates with teammates' agents — privacy-first." },
  { icon: Store, title: "Agent Marketplace", problem: "Building from scratch every time", desc: "Browse, buy, and sell agent presets. One-click install for Ghost Mode configs, delegation rules, and more." },
];

const stats = [
  { end: 4.2, label: "Hours Saved Weekly", suffix: "h", decimals: 1 },
  { end: 91, label: "Ghost Mode Accuracy", suffix: "%", decimals: 0 },
  { end: 47, label: "Avg Flow Session (min)", suffix: "m", decimals: 0 },
  { end: 11, label: "AI Agents Working", suffix: "", decimals: 0 },
];

const audioSamples = [
  {
    title: "Morning Briefing",
    subtitle: "Kairo reads your daily summary at 7 AM",
    transcript: "Good morning. You have 4 meetings today. I replied to Mike's status update at 92% confidence. Rahul's project sync was handled in Hindi. Your CEO email is queued for review — flagged as VIP. Deep work is protected from 9 to 11.",
    duration: "0:28",
    lang: "English",
    seed: 42,
  },
  {
    title: "Ghost Mode in Action",
    subtitle: "Kairo explains what it sent on your behalf",
    transcript: "I sent three messages while you were in deep work. Mike got a status update confirming the Q3 timeline. Sarah received your calendar link for next Tuesday. I declined the 2pm call — it conflicts with your protected focus block.",
    duration: "0:22",
    lang: "English",
    seed: 137,
  },
  {
    title: "हिंदी ब्रीफिंग",
    subtitle: "Kairo delivers your briefing in Hindi",
    transcript: "सुप्रभात। आज 3 मीटिंग हैं। राहुल का Teams मेसेज हिंदी में भेज दिया गया। CEO की ईमेल review के लिए रखी है। 9 से 11 बजे तक deep work प्रोटेक्ट है।",
    duration: "0:20",
    lang: "Hindi",
    seed: 256,
  },
  {
    title: "Relationship Alert",
    subtitle: "Kairo warns about a fading connection",
    transcript: "Heads up — you haven't reached out to Priya in 18 days. Tone analysis shows her last two messages were noticeably shorter. I've drafted a casual check-in for your review. Want me to send it?",
    duration: "0:18",
    lang: "English",
    seed: 389,
  },
  {
    title: "Flow Debrief",
    subtitle: "Kairo summarizes what happened while you were in flow",
    transcript: "Nice session — 47 minutes of uninterrupted focus. I held 4 messages: Phani asked about component props, Sarah sent a status reminder, two bot notifications. Nothing urgent. Want me to batch-reply or handle them individually?",
    duration: "0:20",
    lang: "English",
    seed: 512,
  },
];

function HomeContent() {
  const { theme, toggle, mounted } = useTheme();
  const statsSection = useInView({ threshold: 0.3 });
  const [countStarted, setCountStarted] = useState(false);
  useEffect(() => { if (statsSection.visible) setCountStarted(true); }, [statsSection.visible]);

  const c0 = useCounter(stats[0].end, 1400, countStarted, 1);
  const c1 = useCounter(stats[1].end, 1400, countStarted, 0);
  const c2 = useCounter(stats[2].end, 1000, countStarted, 0);
  const c3 = useCounter(stats[3].end, 1000, countStarted, 0);
  const counts = [c0, c1, c2, c3];

  return (
    <main className="min-h-screen bg-white dark:bg-[#0f0a1a] relative overflow-hidden transition-colors">

      {/* ═══ NAV ═══ */}
      <nav className="fixed top-0 inset-x-0 z-50 bg-white/80 dark:bg-[#0f0a1a]/80 backdrop-blur-xl border-b border-slate-100 dark:border-[#2d2247]/50">
        <div className="max-w-7xl mx-auto flex items-center justify-between px-6 md:px-8 py-4">
          <Link href="/" className="flex items-center gap-2">
            <svg width="26" height="26" viewBox="0 0 26 26" fill="none"><circle cx="13" cy="13" r="12" stroke="#7c3aed" strokeWidth="2" /><path d="M13 6v7l5 3" stroke="#7c3aed" strokeWidth="2" strokeLinecap="round" /></svg>
            <span className="font-['DM_Serif_Display'] text-xl text-slate-900 dark:text-white tracking-tight">Kairo</span>
          </Link>
          <div className="hidden md:flex items-center gap-8 text-sm text-slate-500 dark:text-slate-400">
            <a href="#features" className="hover:text-slate-900 dark:hover:text-white transition-colors">Features</a>
            <a href="#listen" className="hover:text-slate-900 dark:hover:text-white transition-colors">Listen</a>
            <a href="#how" className="hover:text-slate-900 dark:hover:text-white transition-colors">How it Works</a>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={toggle} className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-[#2d2247] transition-colors text-slate-500 dark:text-slate-400" suppressHydrationWarning>
              {mounted ? (theme === "light" ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />) : <div className="w-4 h-4" />}
            </button>
            <Link href="/auth?mode=login" className="text-sm text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white transition-colors">Log in</Link>
            <Link href="/auth?mode=register" className="kairo-btn-primary text-sm">Start Free</Link>
          </div>
        </div>
      </nav>

      {/* ═══ HERO ═══ */}
      <section className="relative z-10 max-w-4xl mx-auto px-6 pt-36 md:pt-48 pb-20 text-center">
        <div className="absolute inset-0 -z-10 bg-gradient-to-b from-violet-50/50 via-transparent to-transparent dark:from-violet-950/20 dark:via-transparent" />

        <Reveal>
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-violet-50 dark:bg-violet-500/10 border border-violet-200 dark:border-violet-500/20 text-violet-600 dark:text-violet-400 text-xs font-medium mb-8 tracking-wide">
            <Mic className="w-3.5 h-3.5" />
            AI Executive Assistant &middot; English + Hindi
          </div>
        </Reveal>
        <Reveal delay={100}>
          <h1 className="text-5xl md:text-7xl font-extrabold text-slate-900 dark:text-white leading-[1.05] mb-8 tracking-tight">
            Your AI Chief of Staff.<br />Nine Agents. Zero Busywork.
          </h1>
        </Reveal>
        <Reveal delay={200}>
          <p className="text-lg md:text-xl text-slate-500 dark:text-slate-400 max-w-2xl mx-auto mb-12 leading-relaxed">
            Kairo is an AI agent that autonomously manages your emails, meetings, and relationships — so you can focus on the work that actually matters.
          </p>
        </Reveal>
        <Reveal delay={300}>
          <div className="flex flex-wrap items-center gap-4 justify-center">
            <Link href="/auth?mode=register" className="kairo-btn-primary text-base px-8 py-4 rounded-2xl shadow-lg shadow-violet-600/25">
              Get Started Free <ArrowRight className="w-4 h-4" />
            </Link>
            <a href="#listen" className="kairo-btn text-base px-8 py-4 rounded-2xl border border-slate-200 dark:border-[#2d2247] text-slate-600 dark:text-slate-300 hover:border-slate-300 dark:hover:border-[#3d3257] bg-transparent">
              <Volume2 className="w-4 h-4" /> Hear Kairo
            </a>
          </div>
        </Reveal>
        <Reveal delay={400}>
          <div className="mt-16 flex flex-col items-center text-slate-400 dark:text-slate-500 text-sm">
            <span>See what Kairo can do</span>
            <ChevronDown className="w-5 h-5 mt-1 animate-bounce" />
          </div>
        </Reveal>
      </section>

      {/* ═══ THE PROBLEM ═══ */}
      <section className="relative z-10 max-w-5xl mx-auto px-6 py-28">
        <Reveal className="text-center mb-16">
          <p className="text-xs text-red-500 dark:text-red-400 uppercase tracking-[0.2em] font-semibold mb-3">THE PROBLEM</p>
          <h2 className="text-4xl md:text-5xl font-extrabold text-slate-900 dark:text-white tracking-tight">Your Day Is Under Siege</h2>
          <p className="text-slate-500 dark:text-slate-400 mt-4 max-w-2xl mx-auto">Before you write a single line of code, close a deal, or think a creative thought — this is what&apos;s already happening.</p>
        </Reveal>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {[
            { stat: "3+ hours/day", desc: "spent on email, Slack, and Teams — before any real work begins" },
            { stat: "Silent relationship decay", desc: "missed follow-ups and broken promises erode trust before you notice" },
            { stat: "23 minutes", desc: "to refocus after every interruption. Deep work dies by a thousand pings." },
            { stat: "Burnout by Thursday", desc: "back-to-back meetings, after-hours messages, no recovery time" },
          ].map((card, i) => (
            <Reveal key={i} delay={i * 100}>
              <div className="bg-red-50/50 dark:bg-red-500/5 border border-red-100 dark:border-red-500/10 rounded-2xl p-6 hover:border-red-200 dark:hover:border-red-500/20 transition-colors">
                <p className="text-2xl font-extrabold text-red-600 dark:text-red-400 mb-2">{card.stat}</p>
                <p className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed">{card.desc}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ═══ FEATURES (THE SOLUTION) ═══ */}
      <section id="features" className="relative z-10 max-w-6xl mx-auto px-6 py-28">
        <Reveal className="text-center mb-16">
          <p className="text-xs text-violet-600 dark:text-violet-400 uppercase tracking-[0.2em] font-semibold mb-3">THE SOLUTION</p>
          <h2 className="text-4xl md:text-5xl font-extrabold text-slate-900 dark:text-white tracking-tight">Nine Agents. One Mission:<br />Protect Your Time.</h2>
          <p className="text-slate-500 dark:text-slate-400 mt-4 max-w-2xl mx-auto">Each agent targets a specific pain point — so nothing falls through the cracks while you do your best work.</p>
        </Reveal>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {platformFeatures.map((f, i) => {
            const Icon = f.icon;
            return (
              <Reveal key={i} delay={i * 80}>
                <div className="bg-white dark:bg-[#1e1533] rounded-2xl p-6 border border-slate-200 dark:border-[#2d2247] transition-all duration-300 hover:-translate-y-1 hover:shadow-lg hover:shadow-violet-500/5 hover:border-violet-200 dark:hover:border-violet-500/30 h-full group">
                  <div className="w-10 h-10 rounded-xl bg-violet-50 dark:bg-violet-500/10 flex items-center justify-center mb-4 group-hover:bg-violet-100 dark:group-hover:bg-violet-500/20 transition-colors">
                    <Icon className="w-5 h-5 text-violet-600 dark:text-violet-400" />
                  </div>
                  <p className="text-xs text-red-500 dark:text-red-400 font-medium mb-1.5">{f.problem}</p>
                  <h3 className="text-slate-900 dark:text-white font-semibold mb-2">{f.title}</h3>
                  <p className="text-sm text-slate-500 dark:text-slate-400 leading-relaxed">{f.desc}</p>
                </div>
              </Reveal>
            );
          })}
        </div>
      </section>

      {/* ═══ THE KAIRO DIFFERENCE (before/after proof) ═══ */}
      <section className="relative z-10">
        <div className="max-w-5xl mx-auto px-6 py-28">
          <Reveal className="text-center mb-16">
            <p className="text-xs text-violet-600 dark:text-violet-400 uppercase tracking-[0.2em] font-semibold mb-3">THE KAIRO DIFFERENCE</p>
            <h2 className="text-4xl md:text-5xl font-extrabold text-slate-900 dark:text-white tracking-tight">Before &amp; After Kairo</h2>
          </Reveal>
          <div className="space-y-4">
            {[
              { before: "3h+ daily on emails", after: "47 min avg focus sessions" },
              { before: "Missed commitments & broken promises", after: "93% commitment fulfillment rate" },
              { before: "Burnout by Thursday", after: "Predictive interventions before it hits" },
              { before: "\"Who should handle this?\"", after: "Smart delegation in 1 click" },
            ].map((row, i) => (
              <Reveal key={i} delay={i * 100}>
                <div className="grid grid-cols-[1fr,auto,1fr] items-center gap-4 md:gap-6">
                  <div className="text-right px-4 py-3 rounded-xl bg-red-50 dark:bg-red-500/5 border border-red-100 dark:border-red-500/10">
                    <p className="text-sm text-red-600 dark:text-red-400">{row.before}</p>
                  </div>
                  <ArrowRight className="w-5 h-5 text-violet-500 flex-shrink-0" />
                  <div className="px-4 py-3 rounded-xl bg-emerald-50 dark:bg-emerald-500/5 border border-emerald-100 dark:border-emerald-500/10">
                    <p className="text-sm text-emerald-600 dark:text-emerald-400 font-medium">{row.after}</p>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ DECISION INTELLIGENCE ═══ */}
      <section className="relative z-10 bg-slate-50 dark:bg-[#1a1128] border-y border-slate-100 dark:border-[#2d2247]/50">
        <div className="max-w-5xl mx-auto px-6 py-28">
          <Reveal className="text-center mb-16">
            <p className="text-xs text-violet-600 dark:text-violet-400 uppercase tracking-[0.2em] font-semibold mb-3">DECISION INTELLIGENCE</p>
            <h2 className="text-4xl md:text-5xl font-extrabold text-slate-900 dark:text-white tracking-tight">What If You Hadn&apos;t<br />Declined That Meeting?</h2>
            <p className="text-slate-500 dark:text-slate-400 mt-4 max-w-2xl mx-auto">Kairo&apos;s Decision Replay traces the cascade consequences of every major decision — showing you the path not taken.</p>
          </Reveal>
          <Reveal delay={150}>
            <div className="bg-white dark:bg-[#1e1533] rounded-2xl border border-slate-200 dark:border-[#2d2247] p-8 md:p-10">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {/* Actual Path */}
                <div>
                  <div className="flex items-center gap-2 mb-5">
                    <div className="w-3 h-3 rounded-full bg-emerald-500" />
                    <span className="text-sm font-semibold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider">Actual Path</span>
                  </div>
                  <div className="space-y-3 border-l-2 border-emerald-200 dark:border-emerald-500/30 pl-5">
                    {["Deep work block preserved", "Dashboard redesign shipped on time", "Sprint completed — no weekend work"].map((s, i) => (
                      <Reveal key={i} delay={300 + i * 150}>
                        <div className="bg-emerald-50 dark:bg-emerald-500/5 border border-emerald-100 dark:border-emerald-500/10 rounded-xl px-4 py-3">
                          <p className="text-sm text-emerald-700 dark:text-emerald-400">{s}</p>
                        </div>
                      </Reveal>
                    ))}
                  </div>
                </div>
                {/* Counterfactual Path */}
                <div>
                  <div className="flex items-center gap-2 mb-5">
                    <div className="w-3 h-3 rounded-full bg-amber-500" />
                    <span className="text-sm font-semibold text-amber-600 dark:text-amber-400 uppercase tracking-wider">Counterfactual</span>
                  </div>
                  <div className="space-y-3 border-l-2 border-amber-200 dark:border-amber-500/30 pl-5">
                    {["1.5 hours lost to vendor demo", "Feature delayed by 1 day", "Weekend work needed to hit sprint"].map((s, i) => (
                      <Reveal key={i} delay={300 + i * 150}>
                        <div className="bg-amber-50 dark:bg-amber-500/5 border border-amber-100 dark:border-amber-500/10 rounded-xl px-4 py-3">
                          <p className="text-sm text-amber-700 dark:text-amber-400">{s}</p>
                        </div>
                      </Reveal>
                    ))}
                  </div>
                </div>
              </div>
              <Reveal delay={800}>
                <div className="mt-8 pt-6 border-t border-slate-100 dark:border-[#2d2247] flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="px-3 py-1.5 rounded-full bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-sm font-medium">Excellent call</div>
                    <span className="text-sm text-slate-400">Confidence: 85%</span>
                  </div>
                  <span className="text-sm font-semibold text-slate-900 dark:text-white">+2.5 hours saved</span>
                </div>
              </Reveal>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ═══ HEAR KAIRO IN ACTION ═══ */}
      <section id="listen" className="relative z-10 bg-slate-50 dark:bg-[#1a1128] border-y border-slate-100 dark:border-[#2d2247]/50">
        <div className="max-w-6xl mx-auto px-6 py-28">
          <Reveal className="text-center mb-16">
            <p className="text-xs text-violet-600 dark:text-violet-400 uppercase tracking-[0.2em] font-semibold mb-3">HEAR KAIRO</p>
            <h2 className="text-4xl md:text-5xl font-extrabold text-slate-900 dark:text-white tracking-tight">Listen to Your Agent</h2>
            <p className="text-slate-500 dark:text-slate-400 mt-4 max-w-2xl mx-auto">These are real examples of what Kairo sounds like — morning briefings, ghost mode recaps, Hindi conversations, and proactive relationship alerts.</p>
          </Reveal>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {audioSamples.map((sample, i) => (
              <Reveal key={i} delay={i * 100}>
                <AudioSample {...sample} />
              </Reveal>
            ))}
          </div>
          <Reveal delay={400} className="text-center mt-10">
            <p className="text-slate-400 text-sm">Powered by Edge TTS + LiveKit &middot; Real-time bilingual voice</p>
          </Reveal>
        </div>
      </section>

      {/* ═══ REAL-TIME PROTECTION ═══ */}
      <section className="relative z-10 bg-slate-50 dark:bg-[#1a1128] border-y border-slate-100 dark:border-[#2d2247]/50">
        <div className="max-w-4xl mx-auto px-6 py-28">
          <Reveal className="text-center mb-16">
            <p className="text-xs text-violet-600 dark:text-violet-400 uppercase tracking-[0.2em] font-semibold mb-3">FLOW STATE GUARDIAN</p>
            <h2 className="text-4xl md:text-5xl font-extrabold text-slate-900 dark:text-white tracking-tight">Protect Your Focus</h2>
            <p className="text-slate-500 dark:text-slate-400 mt-4 max-w-2xl mx-auto">Kairo detects when you&apos;re in flow and shields you from interruptions. Messages are held, auto-responses sent, and everything is summarized when you surface.</p>
          </Reveal>
          <Reveal delay={150}>
            <div className="bg-white dark:bg-[#1e1533] rounded-2xl border border-slate-200 dark:border-[#2d2247] p-8 md:p-10">
              <div className="flex flex-col items-center mb-8">
                {/* Pulsing flow indicator */}
                <div className="relative w-24 h-24 mb-4">
                  <div className="absolute inset-0 rounded-full bg-violet-500/20 animate-ping" style={{ animationDuration: "2s" }} />
                  <div className="absolute inset-2 rounded-full bg-violet-500/30 animate-ping" style={{ animationDuration: "2s", animationDelay: "0.3s" }} />
                  <div className="absolute inset-4 rounded-full bg-violet-600 flex items-center justify-center">
                    <Shield className="w-8 h-8 text-white" />
                  </div>
                </div>
                <p className="text-lg font-semibold text-slate-900 dark:text-white">In Flow — 47 minutes</p>
                <p className="text-sm text-slate-400">Protection active</p>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {[
                  { label: "Messages Held", value: "4", color: "text-violet-600 dark:text-violet-400" },
                  { label: "Auto-Responses", value: "3", color: "text-blue-600 dark:text-blue-400" },
                  { label: "Meetings Declined", value: "1", color: "text-amber-600 dark:text-amber-400" },
                  { label: "Focus Saved", value: "35 min", color: "text-emerald-600 dark:text-emerald-400" },
                ].map((item, i) => (
                  <Reveal key={i} delay={300 + i * 100}>
                    <div className="text-center p-4 rounded-xl bg-slate-50 dark:bg-[#0f0a1a] border border-slate-100 dark:border-[#2d2247]">
                      <p className={`text-2xl font-bold ${item.color}`}>{item.value}</p>
                      <p className="text-xs text-slate-400 mt-1">{item.label}</p>
                    </div>
                  </Reveal>
                ))}
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ═══ STATS BAR ═══ */}
      <section ref={statsSection.ref} className="relative z-10 border-y border-slate-100 dark:border-[#2d2247]/50 bg-slate-50 dark:bg-[#1a1128]">
        <div className="max-w-6xl mx-auto px-6 py-16 grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
          {stats.map((s, i) => (
            <div key={i}>
              <p className="text-4xl md:text-5xl font-extrabold text-slate-900 dark:text-white tracking-tight">{counts[i]}{s.suffix}</p>
              <p className="text-sm text-slate-400 dark:text-slate-500 mt-2">{s.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ═══ HOW IT WORKS ═══ */}
      <section id="how" className="relative z-10 max-w-4xl mx-auto px-6 py-28">
        <Reveal className="text-center mb-16">
          <p className="text-xs text-violet-600 dark:text-violet-400 uppercase tracking-[0.2em] font-semibold mb-3">HOW IT WORKS</p>
          <h2 className="text-4xl md:text-5xl font-extrabold text-slate-900 dark:text-white tracking-tight">Four Steps to Get Started</h2>
        </Reveal>
        <div className="space-y-12">
          {[
            { n: "01", title: "Create Your Agent", desc: "Set your voice, language preference, and personality. Choose English, Hindi, or auto-detect." },
            { n: "02", title: "Connect Your World", desc: "Link Gmail, Slack, Teams, and Calendar through Composio's secure OAuth in one click." },
            { n: "03", title: "Kairo Learns You", desc: "Tracks commitments, communication patterns, productivity peaks, and relationship health across all channels." },
            { n: "04", title: "Autonomous Protection", desc: "Ghost mode replies, flow guardian shields, smart delegation, and burnout prediction — all running while you focus." },
          ].map((s, i) => (
            <Reveal key={i} delay={i * 120}>
              <div className="flex gap-6 items-start">
                <div className="w-12 h-12 rounded-2xl bg-violet-600 flex items-center justify-center text-white font-bold text-sm flex-shrink-0 shadow-lg shadow-violet-600/20">{s.n}</div>
                <div className="pt-1">
                  <h3 className="text-slate-900 dark:text-white text-lg font-semibold mb-1.5">{s.title}</h3>
                  <p className="text-slate-500 dark:text-slate-400 text-sm leading-relaxed max-w-lg">{s.desc}</p>
                </div>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ═══ CTA ═══ */}
      <section className="relative z-10 max-w-4xl mx-auto px-6 py-28 text-center">
        <Reveal>
          <div className="bg-gradient-to-br from-violet-600 to-purple-700 rounded-3xl p-12 md:p-16 text-white relative overflow-hidden">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(255,255,255,0.1),transparent_50%)]" />
            <div className="relative z-10">
              <h2 className="text-3xl md:text-4xl font-extrabold mb-4">Stop managing messages.<br />Start doing your best work.</h2>
              <p className="text-violet-200 mb-8 max-w-md mx-auto">Set up Kairo in 5 minutes. Reclaim hours every week.</p>
              <div className="flex flex-wrap items-center gap-4 justify-center">
                <Link href="/auth?mode=register" className="kairo-btn bg-white text-violet-700 hover:bg-violet-50 text-base px-8 py-3.5 rounded-2xl font-semibold shadow-lg">
                  Sign up free <ArrowRight className="w-4 h-4" />
                </Link>
              </div>
            </div>
          </div>
        </Reveal>
      </section>

      {/* ═══ FOOTER ═══ */}
      <footer className="relative z-10 border-t border-slate-100 dark:border-[#2d2247]/50">
        <div className="max-w-6xl mx-auto px-6 py-12 flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-2.5">
            <svg width="22" height="22" viewBox="0 0 26 26" fill="none"><circle cx="13" cy="13" r="12" stroke="#7c3aed" strokeWidth="2" /><path d="M13 6v7l5 3" stroke="#7c3aed" strokeWidth="2" strokeLinecap="round" /></svg>
            <span className="font-['DM_Serif_Display'] text-lg text-slate-900 dark:text-white">Kairo</span>
            <span className="text-slate-400 text-sm ml-2">The right action, at the right moment.</span>
          </div>
          <div className="flex items-center gap-6 text-sm text-slate-400">
            <a href="#features" className="hover:text-slate-900 dark:hover:text-white transition-colors">Features</a>
            <a href="#listen" className="hover:text-slate-900 dark:hover:text-white transition-colors">Listen</a>
            <a href="#how" className="hover:text-slate-900 dark:hover:text-white transition-colors">How it Works</a>
          </div>
        </div>
      </footer>
    </main>
  );
}

export default function HomePage() {
  return (
    <ThemeProvider>
      <HomeContent />
    </ThemeProvider>
  );
}
