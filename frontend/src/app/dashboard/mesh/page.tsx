"use client";
import { useEffect, useState, useRef, useCallback } from "react";
import { useAuth } from "@/lib/store";
import { mesh, tts } from "@/lib/api";
import { Users, ArrowLeftRight, Calendar, FileInput, Radio, Shield, Bot, Play, Square, Volume2 } from "lucide-react";

const AGENT_COLORS: Record<string, { bg: string; text: string; border: string; avatar: string }> = {
  Atlas: { bg: "bg-blue-500/10", text: "text-blue-400", border: "border-blue-500/30", avatar: "bg-blue-600" },
  Nova: { bg: "bg-pink-500/10", text: "text-pink-400", border: "border-pink-500/30", avatar: "bg-pink-500" },
  Sentinel: { bg: "bg-emerald-500/10", text: "text-emerald-400", border: "border-emerald-500/30", avatar: "bg-emerald-500" },
};

const SCENARIOS = [
  { label: "Atlas + Nova: Sprint Planning", agent_a: "Atlas", agent_b: "Nova", type: "sprint_planning", context: "Planning the next 2-week sprint, need to allocate tasks and agree on priorities" },
  { label: "Nova + Sentinel: Security Review", agent_a: "Nova", agent_b: "Sentinel", type: "security_review", context: "Reviewing a new feature deployment for security compliance before launch" },
  { label: "Atlas + Sentinel: Resource Allocation", agent_a: "Atlas", agent_b: "Sentinel", type: "resource_allocation", context: "Negotiating compute resources and budget for Q1 infrastructure upgrades" },
  { label: "Atlas + Nova: Meeting Scheduling", agent_a: "Atlas", agent_b: "Nova", type: "meeting_scheduling", context: "Finding a time slot for a cross-team sync that works around deep work blocks" },
];

type DialogueLine = { speaker: string; text: string; voice: string };

export default function MeshPage() {
  const { user } = useAuth();
  const [status, setStatus] = useState<any>(null);
  const [agents, setAgents] = useState<any[]>([]);

  // Negotiation state
  const [dialogue, setDialogue] = useState<DialogueLine[]>([]);
  const [outcome, setOutcome] = useState("");
  const [loading, setLoading] = useState(false);
  const [playingIndex, setPlayingIndex] = useState<number>(-1);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackDone, setPlaybackDone] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const stopRef = useRef(false);
  const transcriptRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!user) return;
    mesh.status().then(setStatus).catch(() => {});
    mesh.agents().then(setAgents).catch(() => {});
  }, [user]);

  const startNegotiation = useCallback(async (scenario: typeof SCENARIOS[0]) => {
    setLoading(true);
    setDialogue([]);
    setOutcome("");
    setPlayingIndex(-1);
    setIsPlaying(false);
    setPlaybackDone(false);
    stopRef.current = false;

    try {
      const result = await mesh.negotiate({
        negotiation_type: scenario.type,
        agent_a: scenario.agent_a,
        agent_b: scenario.agent_b,
        context: scenario.context,
      });
      if (result.dialogue && result.dialogue.length > 0) {
        setDialogue(result.dialogue);
        setOutcome(result.outcome);
        // Start audio playback
        playSequence(result.dialogue);
      }
    } catch (e) {
      console.error("Negotiation failed:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  const playSequence = useCallback(async (lines: DialogueLine[]) => {
    setIsPlaying(true);
    for (let i = 0; i < lines.length; i++) {
      if (stopRef.current) break;
      setPlayingIndex(i);

      // Scroll the current line into view
      setTimeout(() => {
        const el = document.getElementById(`dialogue-line-${i}`);
        el?.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }, 100);

      // Play audio for this line
      const url = tts.speakUrl(lines[i].text, lines[i].voice);
      try {
        await new Promise<void>((resolve, reject) => {
          const audio = new Audio(url);
          audioRef.current = audio;
          audio.onended = () => resolve();
          audio.onerror = () => {
            console.warn(`Audio failed for line ${i}, skipping`);
            resolve();
          };
          audio.play().catch(() => resolve());
        });
      } catch {
        // continue to next line
      }
    }
    setPlayingIndex(-1);
    setIsPlaying(false);
    setPlaybackDone(true);
  }, []);

  const stopPlayback = useCallback(() => {
    stopRef.current = true;
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    setIsPlaying(false);
    setPlayingIndex(-1);
  }, []);

  if (!user) return null;

  return (
    <div className="p-8 max-w-4xl">
      <div className="mb-6 pb-5 border-b border-slate-200 dark:border-[#2d2247]">
        <h1 className="font-['DM_Serif_Display'] text-2xl text-slate-900 dark:text-white">Agent Mesh</h1>
        <p className="text-slate-400 text-sm mt-1">Multi-agent coordination across your team</p>
      </div>

      {/* Mesh Stats */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        {[
          { icon: Radio, color: 'text-violet-600 dark:text-violet-400', gradient: 'from-violet-500/[0.07] to-transparent', border: 'border-violet-500/10', label: 'Connected Agents', value: agents.length },
          { icon: ArrowLeftRight, color: 'text-violet-600 dark:text-violet-400', gradient: 'from-violet-500/[0.07] to-transparent', border: 'border-violet-500/10', label: 'Active Negotiations', value: status?.active_negotiations ?? 0 },
          { icon: Calendar, color: 'text-emerald-600 dark:text-emerald-400', gradient: 'from-emerald-500/[0.07] to-transparent', border: 'border-emerald-500/10', label: 'Pending Requests', value: status?.incoming_requests ?? 0 },
        ].map(({icon: Icon, color, gradient, border, label, value}) => (
          <div key={label} className={`kairo-card relative overflow-hidden !border ${border}`}>
            <div className={`absolute inset-0 bg-gradient-to-b ${gradient} pointer-events-none`} />
            <div className="relative z-10">
              <div className="flex items-center gap-2 mb-2"><Icon className={`w-4 h-4 ${color}`} /><span className="text-xs text-slate-400 font-medium">{label}</span></div>
              <p className={`stat-value ${color}`}>{value}</p>
            </div>
          </div>
        ))}
      </div>

      {/* How Mesh Works */}
      <div className="kairo-card mb-6">
        <h2 className="section-title mb-4">How Agent Mesh Works</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            { icon: Calendar, title: "Scheduling", desc: "Your agent negotiates meeting times with teammates' agents, respecting both schedules and deep work blocks.", color: "text-violet-600 dark:text-violet-400", bg: "bg-violet-50 dark:bg-violet-500/10" },
            { icon: FileInput, title: "Task Handoff", desc: "When a teammate is blocked, their agent requests deliverables from yours. Non-private content is shared automatically.", color: "text-blue-600 dark:text-blue-400", bg: "bg-blue-50 dark:bg-blue-500/10" },
            { icon: Shield, title: "Privacy Protocol", desc: "Only availability, energy state, and task blockers are shared. Email content, personal data, and VIP contacts stay private.", color: "text-emerald-600 dark:text-emerald-400", bg: "bg-emerald-50 dark:bg-emerald-500/10" },
          ].map(({ icon: Icon, title, desc, color, bg }, i) => (
            <div key={i} className="p-4 rounded-xl bg-slate-50 dark:bg-[#2d2247]/40 border border-slate-200 dark:border-[#2d2247] hover:border-slate-200 dark:hover:border-[#2d2247] transition-all duration-200 group">
              <div className={`w-9 h-9 rounded-lg ${bg} flex items-center justify-center mb-3 group-hover:scale-105 transition-transform`}>
                <Icon className={`w-4.5 h-4.5 ${color}`} />
              </div>
              <h3 className="text-slate-900 dark:text-white text-sm font-medium mb-1.5">{title}</h3>
              <p className="text-slate-400 text-xs leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Connected Agents */}
      <div className="kairo-card mb-6">
        <h2 className="section-title mb-4">Connected Agents</h2>
        {agents.length === 0 ? (
          <div className="text-center py-12">
            <div className="w-16 h-16 rounded-2xl bg-slate-50 dark:bg-[#2d2247]/40 border border-slate-200 dark:border-[#2d2247] flex items-center justify-center mx-auto mb-4">
              <Users className="w-7 h-7 text-slate-200 dark:text-slate-600" />
            </div>
            <p className="text-slate-400 text-sm mb-1 font-medium">No other agents in the mesh yet</p>
            <p className="text-slate-300 dark:text-slate-600 text-xs max-w-xs mx-auto">When teammates launch their Kairo agents, they&apos;ll appear here for coordination.</p>
          </div>
        ) : (
          <div className="space-y-2.5">
            {agents.map((a: any, i: number) => (
              <div key={i} className={`flex items-center justify-between p-3.5 rounded-xl border transition-all duration-200 ${a.status === 'running' ? 'bg-slate-50 dark:bg-[#2d2247]/40 border-emerald-500/15' : 'bg-slate-50 dark:bg-[#2d2247]/40 border-slate-200 dark:border-[#2d2247] hover:border-slate-200 dark:hover:border-[#2d2247]'}`}>
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center border-2 transition-all duration-300 ${a.status === 'running' ? 'bg-emerald-50 dark:bg-emerald-500/10 border-emerald-500/30' : 'bg-violet-50 dark:bg-violet-500/10 border-slate-200 dark:border-[#2d2247]'}`}>
                    <Bot className={`w-4.5 h-4.5 ${a.status === 'running' ? 'text-emerald-600 dark:text-emerald-400' : 'text-violet-600 dark:text-violet-400'}`} />
                  </div>
                  <div>
                    <p className="text-sm text-slate-900 dark:text-white font-medium">{a.agent_name}</p>
                    <p className="text-[10px] text-slate-400">{a.user_id}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`${a.status === "running" ? "badge-success" : "badge-neutral"} ${a.status === 'running' ? 'shadow-[0_0_10px_rgba(52,211,153,0.1)]' : ''}`}>
                    {a.status === 'running' && <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />}
                    {a.status}
                  </span>
                  {a.ghost_mode && <span className="badge-warning">Ghost</span>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Live Negotiation Panel */}
      <div className="kairo-card mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Volume2 className="w-4.5 h-4.5 text-violet-600 dark:text-violet-400" />
          <h2 className="section-title !mb-0">Live Negotiation</h2>
        </div>
        <p className="text-slate-400 text-xs mb-4">Listen to agents negotiate in real-time with distinct voices and personalities.</p>

        {/* Scenario Buttons */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-4">
          {SCENARIOS.map((s) => {
            const colA = AGENT_COLORS[s.agent_a] || AGENT_COLORS.Atlas;
            const colB = AGENT_COLORS[s.agent_b] || AGENT_COLORS.Nova;
            return (
              <button
                key={s.label}
                onClick={() => startNegotiation(s)}
                disabled={loading || isPlaying}
                className="flex items-center gap-3 p-3 rounded-xl bg-slate-50 dark:bg-[#2d2247]/40 border border-slate-200 dark:border-[#2d2247] hover:border-violet-500/30 dark:hover:border-violet-500/30 transition-all duration-200 text-left disabled:opacity-50 disabled:cursor-not-allowed group"
              >
                <div className="flex -space-x-2">
                  <div className={`w-7 h-7 rounded-full ${colA.avatar} flex items-center justify-center text-[10px] font-bold text-white ring-2 ring-white dark:ring-[#1a1333]`}>
                    {s.agent_a[0]}
                  </div>
                  <div className={`w-7 h-7 rounded-full ${colB.avatar} flex items-center justify-center text-[10px] font-bold text-white ring-2 ring-white dark:ring-[#1a1333]`}>
                    {s.agent_b[0]}
                  </div>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-slate-900 dark:text-white truncate group-hover:text-violet-600 dark:group-hover:text-violet-400 transition-colors">{s.label}</p>
                  <p className="text-[10px] text-slate-400 truncate">{s.type.replace(/_/g, " ")}</p>
                </div>
                <Play className="w-3.5 h-3.5 text-slate-300 dark:text-slate-600 group-hover:text-violet-400 transition-colors flex-shrink-0" />
              </button>
            );
          })}
        </div>

        {/* Loading State */}
        {loading && (
          <div className="flex items-center justify-center gap-3 py-8">
            <div className="flex gap-1">
              <div className="w-2 h-2 rounded-full bg-violet-400 animate-bounce" style={{ animationDelay: "0ms" }} />
              <div className="w-2 h-2 rounded-full bg-violet-400 animate-bounce" style={{ animationDelay: "150ms" }} />
              <div className="w-2 h-2 rounded-full bg-violet-400 animate-bounce" style={{ animationDelay: "300ms" }} />
            </div>
            <p className="text-sm text-slate-400">Agents are preparing their arguments...</p>
          </div>
        )}

        {/* Dialogue Transcript */}
        {dialogue.length > 0 && !loading && (
          <div>
            {/* Stop button */}
            {isPlaying && (
              <div className="flex justify-end mb-3">
                <button onClick={stopPlayback} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-medium hover:bg-red-500/20 transition-colors">
                  <Square className="w-3 h-3" /> Stop
                </button>
              </div>
            )}

            <div ref={transcriptRef} className="space-y-3 max-h-96 overflow-y-auto pr-2">
              {dialogue.map((line, i) => {
                const colors = AGENT_COLORS[line.speaker] || AGENT_COLORS.Atlas;
                const isCurrent = playingIndex === i;
                const isPast = playingIndex > i || playbackDone;
                return (
                  <div
                    key={i}
                    id={`dialogue-line-${i}`}
                    className={`flex items-start gap-3 p-3 rounded-xl transition-all duration-300 ${
                      isCurrent
                        ? `${colors.bg} border ${colors.border}`
                        : isPast
                          ? "opacity-100"
                          : "opacity-30"
                    }`}
                  >
                    {/* Agent avatar */}
                    <div className={`w-8 h-8 rounded-full ${colors.avatar} flex items-center justify-center text-[11px] font-bold text-white flex-shrink-0`}>
                      {line.speaker[0]}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className={`text-xs font-semibold ${colors.text}`}>{line.speaker}</span>
                        {/* Audio bars animation for currently playing */}
                        {isCurrent && (
                          <div className="flex items-end gap-[2px] h-3">
                            <div className={`w-[3px] rounded-full ${colors.avatar} animate-pulse`} style={{ height: "40%", animationDelay: "0ms" }} />
                            <div className={`w-[3px] rounded-full ${colors.avatar} animate-pulse`} style={{ height: "80%", animationDelay: "150ms" }} />
                            <div className={`w-[3px] rounded-full ${colors.avatar} animate-pulse`} style={{ height: "55%", animationDelay: "300ms" }} />
                            <div className={`w-[3px] rounded-full ${colors.avatar} animate-pulse`} style={{ height: "90%", animationDelay: "100ms" }} />
                          </div>
                        )}
                      </div>
                      <p className="text-sm text-slate-700 dark:text-slate-200 leading-relaxed">{line.text}</p>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Outcome Card */}
            {playbackDone && outcome && (
              <div className="mt-4 p-4 rounded-xl bg-gradient-to-r from-violet-500/[0.07] to-emerald-500/[0.07] border border-violet-500/15">
                <div className="flex items-center gap-2 mb-1.5">
                  <div className="w-5 h-5 rounded-md bg-emerald-500/15 flex items-center justify-center">
                    <svg className="w-3 h-3 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
                  </div>
                  <span className="text-xs font-semibold text-emerald-400">Negotiation Complete</span>
                </div>
                <p className="text-sm text-slate-700 dark:text-slate-200">{outcome}</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Recent Mesh Activity - Timeline */}
      {status?.requests?.length > 0 && (
        <div className="kairo-card">
          <h2 className="section-title mb-4">Recent Mesh Activity</h2>
          <div className="space-y-0">
            {status.requests.map((r: any, idx: number) => (
              <div key={r.id} className="timeline-item py-3 hover:bg-slate-50 dark:hover:bg-[#2d2247]/30 rounded-r-lg transition-colors">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-500 dark:text-slate-400">
                      <span className="text-slate-900 dark:text-white font-medium">{r.type.replace(/_/g, " ")}</span>
                      <span className="text-slate-300 dark:text-slate-600 mx-1.5">--</span>
                      {r.from} <span className="text-violet-600 dark:text-violet-400">-&gt;</span> {r.to}
                    </span>
                  </div>
                  <span className={`${r.status === "completed" ? "badge-success" : r.status === "pending" ? "badge-warning" : "badge-info"}`}>{r.status}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
