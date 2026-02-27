"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/store";
import { dashboard } from "@/lib/api";
import { Filter, ChevronDown, ChevronUp, Check, X, Mail, MessageSquare, Users, Calendar, Mic, CreditCard } from "lucide-react";

export default function DecisionsPage() {
  const { user } = useAuth();
  const [data, setData] = useState<any>({ actions: [], total: 0 });
  const [statusF, setStatusF] = useState("all");
  const [channelF, setChannelF] = useState("all");
  const [expanded, setExpanded] = useState<string|null>(null);

  useEffect(() => { if (user) dashboard.decisions({ limit: 50, status_filter: statusF, channel_filter: channelF }).then(setData).catch(() => {}); }, [user, statusF, channelF]);

  const feedback = async (id: string, type: string) => { await dashboard.submitFeedback(id, { type }); setData(await dashboard.decisions({ limit: 50, status_filter: statusF, channel_filter: channelF })); };
  if (!user) return null;

  const chIcon = (c: string) => ({ email: Mail, slack: MessageSquare, teams: Users, calendar: Calendar, voice: Mic, skyfire: CreditCard }[c] || Mail);
  const statusBadge = (s: string) => ({ executed: "badge-success", queued_for_review: "badge-warning", overridden: "badge-info", rejected: "badge-danger" }[s] || "badge-neutral");

  const confColor = (s: number) => s >= 0.85 ? '#34d399' : s >= 0.6 ? '#fbbf24' : '#f87171';
  const confRing = (s: number) => {
    const pct = Math.round(s * 100);
    const deg = Math.round(s * 360);
    const c = confColor(s);
    return { background: `conic-gradient(${c} ${deg}deg, #e5e7eb ${deg}deg)`, color: c };
  };

  return (
    <div className="p-8 max-w-5xl">
      {/* Gradient header */}
      <div className="flex items-center justify-between mb-6 pb-5 border-b border-slate-200 dark:border-[#2d2247]">
        <div>
          <h1 className="font-['DM_Serif_Display'] text-2xl text-slate-900 dark:text-white mb-1">Decision Log</h1>
          <p className="text-slate-400 text-sm"><span className="gradient-text font-semibold">{data.total}</span> actions recorded</p>
        </div>
      </div>

      {/* Filter pills with active glow */}
      <div className="flex gap-2 mb-6 flex-wrap">
        {[{v:"all",l:"All Status"},{v:"executed",l:"Executed"},{v:"queued_for_review",l:"Queued"},{v:"overridden",l:"Overridden"},{v:"rejected",l:"Rejected"}].map(f => (
          <button key={f.v} onClick={() => setStatusF(f.v)}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 ${statusF === f.v ? 'bg-violet-100 dark:bg-violet-500/15 text-violet-600 dark:text-violet-400 border border-violet-300 dark:border-violet-500/30 glow-pulse' : 'bg-white dark:bg-[#1e1533] text-slate-400 border border-slate-200 dark:border-[#2d2247] hover:border-slate-300 dark:hover:border-[#3d3257] hover:text-slate-500 dark:text-slate-400'}`}>
            {f.l}
          </button>
        ))}
        <div className="w-px bg-slate-100 dark:bg-[#2d2247]/50 mx-1" />
        <select className="kairo-input w-auto py-1.5 text-xs !rounded-lg" value={channelF} onChange={e => setChannelF(e.target.value)}>
          <option value="all">All Channels</option><option value="email">Email</option><option value="slack">Slack</option><option value="teams">Teams</option><option value="calendar">Calendar</option>
        </select>
      </div>

      <div className="space-y-2">
        {data.actions.length === 0 ? (
          <div className="kairo-card text-center py-16">
            <Filter className="w-8 h-8 text-slate-200 dark:text-slate-600 mx-auto mb-3" />
            <p className="text-slate-400 text-sm">No decisions yet.</p>
            <p className="text-slate-300 dark:text-slate-600 text-xs mt-1">Actions will appear here as your agent works.</p>
          </div>
        ) :
          data.actions.map((a: any) => {
            const Icon = chIcon(a.channel);
            const ring = confRing(a.confidence_score);
            return (
              <div key={a.id} className={`kairo-card-hover py-4 decision-bar-${a.status} !rounded-l-lg transition-all duration-200`}>
                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 rounded-lg bg-slate-50 dark:bg-[#2d2247]/40 flex items-center justify-center flex-shrink-0 border border-slate-200 dark:border-[#2d2247]"><Icon className="w-4 h-4 text-slate-400" /></div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1"><span className="text-sm text-slate-900 dark:text-white font-medium">{a.action_taken}</span><span className={statusBadge(a.status)}>{a.status.replace(/_/g," ")}</span></div>
                    <div className="flex items-center gap-3 text-[10px] text-slate-400">
                      <span className="text-slate-500 dark:text-slate-400">{a.target_contact}</span>
                      <span className="flex items-center gap-1"><Icon className="w-2.5 h-2.5" />{a.channel}</span>
                      {a.language_used && <span className="uppercase tracking-wide">{a.language_used}</span>}
                      {a.estimated_time_saved_minutes > 0 && <span className="text-emerald-500 font-medium">saved {a.estimated_time_saved_minutes}m</span>}
                      {a.amount_spent > 0 && <span className="text-amber-500 font-medium">${a.amount_spent}</span>}
                    </div>
                    {expanded === a.id && (
                      <div className="expand-section mt-3 p-3.5 bg-slate-50 dark:bg-[#2d2247]/40 rounded-xl text-xs space-y-2 border border-slate-200 dark:border-[#2d2247]">
                        <p className="text-slate-500 dark:text-slate-400 leading-relaxed"><span className="text-slate-400 dark:text-slate-500 font-medium">Reasoning:</span> {a.reasoning}</p>
                        {a.factors?.length > 0 && <p className="text-slate-400"><span className="text-slate-400 dark:text-slate-500 font-medium">Factors:</span> {a.factors.join(", ")}</p>}
                        {a.draft_content && <div className="mt-2 p-3 bg-slate-50 dark:bg-[#2d2247]/40 rounded-lg text-slate-500 dark:text-slate-400 border border-slate-200 dark:border-[#2d2247] font-mono text-[11px] leading-relaxed">{a.draft_content}</div>}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {/* Confidence ring */}
                    <div className="confidence-ring" style={ring}>
                      <div className="w-[26px] h-[26px] rounded-full bg-white dark:bg-[#1e1533] flex items-center justify-center text-[9px] font-bold" style={{color: ring.color}}>
                        {Math.round(a.confidence_score*100)}
                      </div>
                    </div>
                    <button onClick={() => setExpanded(expanded === a.id ? null : a.id)} className="kairo-btn-ghost !px-2 !py-1.5 !rounded-lg text-[10px]">
                      {expanded === a.id ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                    </button>
                    {(a.status === "queued_for_review" || (a.status === "executed" && !a.user_feedback)) && <>
                      <button onClick={() => feedback(a.id, "approved")} className="kairo-btn-ghost !px-2 !py-1.5 text-emerald-600 dark:text-emerald-400 hover:!bg-emerald-50 dark:hover:!bg-emerald-500/10 !rounded-lg transition-all duration-200" title="Approve">
                        <Check className="w-3.5 h-3.5" /><span className="text-[10px] hidden sm:inline">Approve</span>
                      </button>
                      <button onClick={() => feedback(a.id, "rejected")} className="kairo-btn-ghost !px-2 !py-1.5 text-red-500 dark:text-red-400 hover:!bg-red-50 dark:hover:!bg-red-500/10 !rounded-lg transition-all duration-200" title="Reject">
                        <X className="w-3.5 h-3.5" /><span className="text-[10px] hidden sm:inline">Reject</span>
                      </button>
                    </>}
                  </div>
                </div>
              </div>
            );
          })}
      </div>
    </div>
  );
}
