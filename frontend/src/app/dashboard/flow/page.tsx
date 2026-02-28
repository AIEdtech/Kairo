"use client";
import { useEffect, useState, useCallback } from "react";
import { useAuth } from "@/lib/store";
import { flow as api } from "@/lib/api";
import { Shield, Play, Square, Clock, MessageSquare, Zap, Mail } from "lucide-react";

export default function FlowPage() {
  const { user } = useAuth();
  const [status, setStatus] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [debrief, setDebrief] = useState<any>(null);

  const load = useCallback(() => {
    api.status().then(setStatus).catch(() => {});
    api.history().then(setHistory).catch(() => {});
    api.stats().then(setStats).catch(() => {});
  }, []);

  useEffect(() => { if (user) load(); }, [user, load]);

  const handleActivate = async () => {
    await api.activate();
    load();
  };

  const handleEnd = async () => {
    const result = await api.end();
    setDebrief(result);
    load();
  };

  if (!user) return null;

  const inFlow = status?.in_flow;

  return (
    <div className="p-8 max-w-5xl">
      <div className="mb-6 pb-5 border-b border-slate-200 dark:border-[#2d2247]">
        <h1 className="font-['DM_Serif_Display'] text-2xl text-slate-900 dark:text-white">Flow State Guardian</h1>
        <p className="text-slate-400 text-sm mt-1">Detect and protect your flow state from interruptions</p>
      </div>

      {/* Flow Status */}
      <div className="kairo-card mb-8">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-5">
            <div className={`relative w-20 h-20 rounded-full flex items-center justify-center ${inFlow ? "bg-violet-500/10" : "bg-slate-50 dark:bg-[#2d2247]/40"}`}>
              {inFlow && (
                <>
                  <div className="absolute inset-0 rounded-full border-2 border-violet-500 animate-ping opacity-20" />
                  <div className="absolute inset-1 rounded-full border-2 border-violet-400 animate-pulse opacity-40" />
                </>
              )}
              <Shield className={`w-8 h-8 ${inFlow ? "text-violet-600 dark:text-violet-400" : "text-slate-300 dark:text-slate-600"}`} />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
                {inFlow ? "In Flow" : "Not in Flow"}
              </h2>
              {inFlow ? (
                <div className="text-sm text-slate-400 space-y-0.5">
                  <p>Duration: {Math.round(status.duration_minutes)} min</p>
                  <p>{status.messages_held} messages held &middot; {status.messages_escalated} escalated</p>
                </div>
              ) : (
                <p className="text-sm text-slate-400">Start a flow session to activate protection</p>
              )}
            </div>
          </div>
          {inFlow ? (
            <button onClick={handleEnd} className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-slate-100 dark:bg-[#2d2247] text-slate-600 dark:text-slate-300 text-sm font-medium hover:bg-slate-200 dark:hover:bg-[#3d3257] transition-colors">
              <Square className="w-4 h-4" />Surface
            </button>
          ) : (
            <button onClick={handleActivate} className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-violet-600 text-white text-sm font-medium hover:bg-violet-700 transition-colors shadow-lg shadow-violet-600/20">
              <Play className="w-4 h-4" />Start Flow
            </button>
          )}
        </div>
      </div>

      {/* Debrief */}
      {debrief && !debrief.error && (
        <div className="kairo-card mb-8 border-violet-200 dark:border-violet-500/20">
          <h3 className="section-title mb-3">Flow Debrief</h3>
          <p className="text-sm text-slate-600 dark:text-slate-300 mb-4">{debrief.summary}</p>
          {debrief.held_messages?.length > 0 && (
            <div className="space-y-2">
              {debrief.held_messages.map((msg: any, i: number) => (
                <div key={i} className="flex items-center gap-3 py-2 px-3 rounded-lg bg-slate-50 dark:bg-[#2d2247]/40">
                  <Mail className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-slate-900 dark:text-white truncate">{msg.from}: {msg.summary}</p>
                    <p className="text-[10px] text-slate-400">{msg.channel}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          {[
            { icon: Shield, color: "text-violet-600 dark:text-violet-400", label: "Sessions", value: stats.total_sessions },
            { icon: Clock, color: "text-blue-600 dark:text-blue-400", label: "Total Flow Hours", value: `${stats.total_flow_hours}h` },
            { icon: MessageSquare, color: "text-amber-600 dark:text-amber-400", label: "Msgs Protected", value: stats.total_messages_protected },
            { icon: Zap, color: "text-emerald-600 dark:text-emerald-400", label: "Focus Saved", value: `${stats.total_focus_saved_minutes}m` },
          ].map(({ icon: Icon, color, label, value }) => (
            <div key={label} className="kairo-card">
              <div className="flex items-center gap-2 mb-2"><Icon className={`w-4 h-4 ${color}`} /><span className="text-slate-400 text-xs">{label}</span></div>
              <p className="text-2xl font-bold text-slate-900 dark:text-white">{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* History */}
      <div className="kairo-card">
        <h2 className="section-title mb-4">Flow History</h2>
        {history.length === 0 ? (
          <div className="text-center py-12">
            <Shield className="w-8 h-8 text-slate-200 dark:text-slate-600 mx-auto mb-3" />
            <p className="text-slate-400 text-sm">No flow sessions yet</p>
          </div>
        ) : (
          <div className="space-y-2.5">
            {history.map((s: any) => (
              <div key={s.id} className="flex items-center justify-between p-3.5 rounded-xl bg-slate-50 dark:bg-[#2d2247]/40 border border-slate-200 dark:border-[#2d2247]">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-violet-50 dark:bg-violet-500/10 flex items-center justify-center">
                    <Shield className="w-4 h-4 text-violet-600 dark:text-violet-400" />
                  </div>
                  <div>
                    <p className="text-sm text-slate-900 dark:text-white font-medium">{Math.round(s.duration_minutes)} min flow session</p>
                    <p className="text-[10px] text-slate-400">
                      {s.messages_held} held &middot; {s.messages_escalated} escalated &middot; {Math.round(s.estimated_focus_saved_minutes)}m saved
                    </p>
                  </div>
                </div>
                <span className="text-[10px] text-slate-400">{s.started_at ? new Date(s.started_at).toLocaleDateString() : ""}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
