"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/store";
import { commitments as api } from "@/lib/api";
import { CheckSquare, Clock, AlertTriangle, Check, X, Timer, ArrowRight } from "lucide-react";

const STATUS_COLORS: Record<string, string> = {
  active: "bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400",
  fulfilled: "bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  overdue: "bg-red-50 dark:bg-red-500/10 text-red-700 dark:text-red-400",
  broken: "bg-red-50 dark:bg-red-500/10 text-red-700 dark:text-red-400",
  cancelled: "bg-slate-100 dark:bg-slate-800/30 text-slate-500",
};

export default function CommitmentsPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [filter, setFilter] = useState("all");

  const load = () => {
    api.list({ status: filter !== "all" ? filter : undefined }).then(setItems).catch(() => {});
    api.stats().then(setStats).catch(() => {});
  };

  useEffect(() => { if (user) load(); }, [user, filter]);

  const handleFulfill = async (id: string) => { await api.fulfill(id); load(); };
  const handleCancel = async (id: string) => { await api.cancel(id); load(); };
  const handleSnooze = async (id: string) => { await api.snooze(id); load(); };

  if (!user) return null;

  return (
    <div className="p-8 max-w-5xl">
      <div className="mb-6 pb-5 border-b border-slate-200 dark:border-[#2d2247]">
        <h1 className="font-['DM_Serif_Display'] text-2xl text-slate-900 dark:text-white">Commitment Tracker</h1>
        <p className="text-slate-400 text-sm mt-1">Promises detected in your messages, tracked through fulfillment</p>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          {[
            { icon: CheckSquare, color: "text-blue-600 dark:text-blue-400", label: "Active", value: stats.active },
            { icon: AlertTriangle, color: "text-red-600 dark:text-red-400", label: "Overdue", value: stats.overdue },
            { icon: Check, color: "text-emerald-600 dark:text-emerald-400", label: "Fulfilled", value: stats.fulfilled },
            { icon: Clock, color: "text-violet-600 dark:text-violet-400", label: "Reliability", value: `${stats.reliability_score}%` },
          ].map(({ icon: Icon, color, label, value }) => (
            <div key={label} className="kairo-card">
              <div className="flex items-center gap-2 mb-2"><Icon className={`w-4 h-4 ${color}`} /><span className="text-slate-400 text-xs">{label}</span></div>
              <p className="text-2xl font-bold text-slate-900 dark:text-white">{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Reliability Score Ring */}
      {stats && (
        <div className="kairo-card mb-8 flex items-center gap-6">
          <div className="relative w-24 h-24 flex-shrink-0">
            <svg className="w-24 h-24 -rotate-90" viewBox="0 0 100 100">
              <circle cx="50" cy="50" r="42" fill="none" stroke="currentColor" strokeWidth="8" className="text-slate-100 dark:text-[#2d2247]" />
              <circle cx="50" cy="50" r="42" fill="none" stroke="currentColor" strokeWidth="8"
                className={stats.reliability_score >= 80 ? "text-emerald-500" : stats.reliability_score >= 50 ? "text-amber-500" : "text-red-500"}
                strokeDasharray={`${stats.reliability_score * 2.64} 264`} strokeLinecap="round" />
            </svg>
            <span className="absolute inset-0 flex items-center justify-center text-lg font-bold text-slate-900 dark:text-white">{stats.reliability_score}%</span>
          </div>
          <div>
            <h3 className="text-sm font-medium text-slate-900 dark:text-white mb-1">Commitment Reliability</h3>
            <p className="text-xs text-slate-400">Based on {stats.total} total commitments. {stats.fulfilled} fulfilled, {stats.overdue} overdue or broken.</p>
          </div>
        </div>
      )}

      {/* Filter */}
      <div className="flex gap-1 mb-6 p-1 bg-slate-100 dark:bg-[#1a1128] rounded-xl w-fit">
        {["all", "active", "overdue", "fulfilled", "broken"].map((f) => (
          <button key={f} onClick={() => setFilter(f)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all capitalize ${filter === f ? "bg-white dark:bg-[#2d2247] text-slate-900 dark:text-white shadow-sm" : "text-slate-400 hover:text-slate-600"}`}>
            {f}
          </button>
        ))}
      </div>

      {/* Commitment List */}
      <div className="space-y-3">
        {items.length === 0 ? (
          <div className="kairo-card text-center py-12">
            <CheckSquare className="w-8 h-8 text-slate-200 dark:text-slate-600 mx-auto mb-3" />
            <p className="text-slate-400 text-sm">No commitments found</p>
          </div>
        ) : items.map((c: any) => (
          <div key={c.id} className="kairo-card">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <p className="text-sm font-medium text-slate-900 dark:text-white truncate">{c.parsed_commitment || c.raw_text}</p>
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${STATUS_COLORS[c.status] || STATUS_COLORS.active}`}>{c.status}</span>
                </div>
                <p className="text-xs text-slate-400 mb-2">
                  To: {c.target_contact || "—"} &middot; {c.channel} &middot; {c.deadline ? new Date(c.deadline).toLocaleDateString() : "No deadline"}
                </p>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 italic border-l-2 border-slate-200 dark:border-[#2d2247] pl-2">&ldquo;{c.raw_text}&rdquo;</p>
                {c.sentiment_impact !== 0 && (
                  <p className="text-[10px] text-red-500 mt-1">Sentiment impact: {c.sentiment_impact > 0 ? "+" : ""}{c.sentiment_impact}</p>
                )}
              </div>
              {c.status === "active" || c.status === "overdue" ? (
                <div className="flex gap-1.5 flex-shrink-0">
                  <button onClick={() => handleFulfill(c.id)} className="p-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-100 dark:hover:bg-emerald-500/20 transition-colors" title="Mark fulfilled">
                    <Check className="w-3.5 h-3.5" />
                  </button>
                  <button onClick={() => handleSnooze(c.id)} className="p-1.5 rounded-lg bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400 hover:bg-amber-100 dark:hover:bg-amber-500/20 transition-colors" title="Snooze 24h">
                    <Clock className="w-3.5 h-3.5" />
                  </button>
                  <button onClick={() => handleCancel(c.id)} className="p-1.5 rounded-lg bg-slate-100 dark:bg-slate-800/30 text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700/30 transition-colors" title="Cancel">
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              ) : null}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
