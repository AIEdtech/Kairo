"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/store";
import { delegation as api } from "@/lib/api";
import { Forward, Check, X, Send, Users, Zap, Clock, Target } from "lucide-react";

export default function DelegationPage() {
  const { user } = useAuth();
  const [data, setData] = useState<any>({ sent: [], received: [] });
  const [stats, setStats] = useState<any>(null);
  const [tab, setTab] = useState<"inbox" | "outbox" | "delegate">("inbox");
  const [taskInput, setTaskInput] = useState("");
  const [candidates, setCandidates] = useState<any[]>([]);
  const [searching, setSearching] = useState(false);

  const load = () => {
    api.list().then(setData).catch(() => {});
    api.stats().then(setStats).catch(() => {});
  };

  useEffect(() => { if (user) load(); }, [user]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!taskInput.trim()) return;
    setSearching(true);
    try {
      const results = await api.candidates(taskInput);
      setCandidates(results);
    } catch { setCandidates([]); }
    setSearching(false);
  };

  const handleDelegate = async (toUserId: string) => {
    await api.propose({ task: taskInput, to_user_id: toUserId });
    setTaskInput("");
    setCandidates([]);
    load();
  };

  const handleAccept = async (id: string) => { await api.accept(id); load(); };
  const handleReject = async (id: string) => { await api.reject(id); load(); };
  const handleComplete = async (id: string) => { await api.complete(id); load(); };

  if (!user) return null;

  const STATUS_COLORS: Record<string, string> = {
    proposed: "bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400",
    accepted: "bg-violet-50 dark:bg-violet-500/10 text-violet-700 dark:text-violet-400",
    in_progress: "bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-400",
    completed: "bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
    rejected: "bg-red-50 dark:bg-red-500/10 text-red-700 dark:text-red-400",
  };

  return (
    <div className="p-8 max-w-5xl">
      <div className="mb-6 pb-5 border-b border-slate-200 dark:border-[#2d2247]">
        <h1 className="font-['DM_Serif_Display'] text-2xl text-slate-900 dark:text-white">Smart Delegation</h1>
        <p className="text-slate-400 text-sm mt-1">Route tasks to the best teammate based on expertise, bandwidth, and relationship</p>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          {[
            { icon: Send, color: "text-violet-600 dark:text-violet-400", label: "Sent", value: stats.total_sent },
            { icon: Forward, color: "text-blue-600 dark:text-blue-400", label: "Received", value: stats.total_received },
            { icon: Check, color: "text-emerald-600 dark:text-emerald-400", label: "Completed", value: stats.completed },
            { icon: Target, color: "text-amber-600 dark:text-amber-400", label: "Avg Match", value: `${Math.round(stats.avg_match_score * 100)}%` },
          ].map(({ icon: Icon, color, label, value }) => (
            <div key={label} className="kairo-card">
              <div className="flex items-center gap-2 mb-2"><Icon className={`w-4 h-4 ${color}`} /><span className="text-slate-400 text-xs">{label}</span></div>
              <p className="text-2xl font-bold text-slate-900 dark:text-white">{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 mb-6 p-1 bg-slate-100 dark:bg-[#1a1128] rounded-xl w-fit">
        {(["inbox", "outbox", "delegate"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all capitalize ${tab === t ? "bg-white dark:bg-[#2d2247] text-slate-900 dark:text-white shadow-sm" : "text-slate-400 hover:text-slate-600"}`}>
            {t === "delegate" ? "New Delegation" : t}
          </button>
        ))}
      </div>

      {/* New Delegation Tab */}
      {tab === "delegate" && (
        <div className="kairo-card mb-6">
          <h3 className="section-title mb-4">Find the Best Person</h3>
          <form onSubmit={handleSearch} className="flex gap-3 mb-6">
            <input type="text" value={taskInput} onChange={(e) => setTaskInput(e.target.value)}
              placeholder="Describe the task, e.g. 'Review backend API rate limiting...'"
              className="flex-1 px-4 py-2.5 rounded-xl bg-slate-50 dark:bg-[#0f0a1a] border border-slate-200 dark:border-[#2d2247] text-sm text-slate-900 dark:text-white placeholder:text-slate-400 focus:outline-none focus:border-violet-500/50" />
            <button type="submit" disabled={searching}
              className="px-5 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-700 text-white text-sm font-medium transition-colors disabled:opacity-50">
              {searching ? "Searching..." : "Find Candidates"}
            </button>
          </form>

          {candidates.length > 0 && (
            <div className="space-y-3">
              {candidates.map((c: any) => (
                <div key={c.user_id} className="flex items-center justify-between p-4 rounded-xl bg-slate-50 dark:bg-[#2d2247]/40 border border-slate-200 dark:border-[#2d2247]">
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded-lg bg-violet-100 dark:bg-violet-500/15 flex items-center justify-center text-violet-600 dark:text-violet-400 text-sm font-bold">
                      {c.full_name?.[0]?.toUpperCase() || "?"}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-slate-900 dark:text-white">{c.full_name}</p>
                      <div className="flex items-center gap-3 mt-0.5">
                        <span className="text-[10px] text-slate-400">Match: {Math.round(c.match_score * 100)}%</span>
                        <span className="text-[10px] text-slate-400">Expertise: {Math.round(c.expertise_match * 100)}%</span>
                        <span className="text-[10px] text-slate-400">Bandwidth: {Math.round(c.bandwidth_score * 100)}%</span>
                      </div>
                      {c.match_reasons?.length > 0 && (
                        <div className="flex gap-1.5 mt-1 flex-wrap">
                          {c.match_reasons.map((r: string, i: number) => (
                            <span key={i} className="px-1.5 py-0.5 rounded text-[9px] bg-violet-50 dark:bg-violet-500/10 text-violet-600 dark:text-violet-400">{r}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                  {/* Match score bar */}
                  <div className="flex items-center gap-3">
                    <div className="w-16 h-2 bg-slate-100 dark:bg-[#2d2247] rounded-full overflow-hidden">
                      <div className="h-full bg-violet-500 rounded-full" style={{ width: `${Math.round(c.match_score * 100)}%` }} />
                    </div>
                    <button onClick={() => handleDelegate(c.user_id)}
                      className="px-3 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-700 text-white text-xs font-medium transition-colors">
                      Delegate
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Inbox */}
      {tab === "inbox" && (
        <div className="kairo-card">
          <h3 className="section-title mb-4">Received Delegations</h3>
          {(data.received || []).length === 0 ? (
            <div className="text-center py-12">
              <Forward className="w-8 h-8 text-slate-200 dark:text-slate-600 mx-auto mb-3" />
              <p className="text-slate-400 text-sm">No delegations received</p>
            </div>
          ) : (data.received || []).map((d: any) => (
            <div key={d.id} className="flex items-center justify-between p-3.5 rounded-xl bg-slate-50 dark:bg-[#2d2247]/40 border border-slate-200 dark:border-[#2d2247] mb-2.5">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <p className="text-sm text-slate-900 dark:text-white font-medium truncate">{d.task_description}</p>
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${STATUS_COLORS[d.status] || ""}`}>{d.status}</span>
                </div>
                <p className="text-[10px] text-slate-400">From: {d.from_user_id} &middot; Match: {Math.round(d.match_score * 100)}%</p>
              </div>
              <div className="flex gap-1.5 flex-shrink-0">
                {d.status === "proposed" && (
                  <>
                    <button onClick={() => handleAccept(d.id)} className="p-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 hover:bg-emerald-100 transition-colors"><Check className="w-3.5 h-3.5" /></button>
                    <button onClick={() => handleReject(d.id)} className="p-1.5 rounded-lg bg-red-50 dark:bg-red-500/10 text-red-600 hover:bg-red-100 transition-colors"><X className="w-3.5 h-3.5" /></button>
                  </>
                )}
                {d.status === "in_progress" && (
                  <button onClick={() => handleComplete(d.id)} className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-medium transition-colors">Complete</button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Outbox */}
      {tab === "outbox" && (
        <div className="kairo-card">
          <h3 className="section-title mb-4">Sent Delegations</h3>
          {(data.sent || []).length === 0 ? (
            <div className="text-center py-12">
              <Send className="w-8 h-8 text-slate-200 dark:text-slate-600 mx-auto mb-3" />
              <p className="text-slate-400 text-sm">No delegations sent</p>
            </div>
          ) : (data.sent || []).map((d: any) => (
            <div key={d.id} className="flex items-center justify-between p-3.5 rounded-xl bg-slate-50 dark:bg-[#2d2247]/40 border border-slate-200 dark:border-[#2d2247] mb-2.5">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <p className="text-sm text-slate-900 dark:text-white font-medium truncate">{d.task_description}</p>
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${STATUS_COLORS[d.status] || ""}`}>{d.status}</span>
                </div>
                <p className="text-[10px] text-slate-400">To: {d.to_user_id} &middot; Match: {Math.round(d.match_score * 100)}%</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
