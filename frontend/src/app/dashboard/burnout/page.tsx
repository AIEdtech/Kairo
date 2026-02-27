"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/store";
import { burnout as api } from "@/lib/api";
import { Heart, TrendingUp, Clock, AlertTriangle, Zap, UserX } from "lucide-react";

export default function BurnoutPage() {
  const { user } = useAuth();
  const [snapshot, setSnapshot] = useState<any>(null);
  const [trend, setTrend] = useState<any[]>([]);
  const [coldContacts, setColdContacts] = useState<any[]>([]);

  useEffect(() => {
    if (!user) return;
    api.current().then(setSnapshot).catch(() => {});
    api.trend().then(setTrend).catch(() => {});
    api.coldContacts().then(setColdContacts).catch(() => {});
  }, [user]);

  const handleApply = async (id: string) => {
    await api.applyIntervention(id);
    api.current().then(setSnapshot).catch(() => {});
  };

  if (!user) return null;

  const risk = snapshot?.burnout_risk_score ?? 0;
  const riskColor = risk < 30 ? "text-emerald-500" : risk < 60 ? "text-amber-500" : "text-red-500";
  const riskBg = risk < 30 ? "stroke-emerald-500" : risk < 60 ? "stroke-amber-500" : "stroke-red-500";

  return (
    <div className="p-8 max-w-5xl">
      <div className="mb-6 pb-5 border-b border-slate-200 dark:border-[#2d2247]">
        <h1 className="font-['DM_Serif_Display'] text-2xl text-slate-900 dark:text-white">Wellness & Burnout Shield</h1>
        <p className="text-slate-400 text-sm mt-1">Predictive burnout analysis with actionable interventions</p>
      </div>

      {/* Burnout Risk Gauge + Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="kairo-card flex flex-col items-center py-6">
          <div className="relative w-32 h-16 mb-3">
            <svg className="w-32 h-16" viewBox="0 0 120 60">
              <path d="M 10 55 A 50 50 0 0 1 110 55" fill="none" stroke="currentColor" strokeWidth="8" strokeLinecap="round" className="text-slate-100 dark:text-[#2d2247]" />
              <path d="M 10 55 A 50 50 0 0 1 110 55" fill="none" strokeWidth="8" strokeLinecap="round" className={riskBg}
                strokeDasharray={`${risk * 1.57} 157` } />
            </svg>
            <span className={`absolute bottom-0 left-1/2 -translate-x-1/2 text-2xl font-bold ${riskColor}`}>{Math.round(risk)}</span>
          </div>
          <p className="text-xs text-slate-400">Burnout Risk Score</p>
          <p className="text-[10px] text-slate-300 dark:text-slate-600 mt-1">
            {risk < 30 ? "Low risk — keep it up!" : risk < 60 ? "Moderate — consider interventions" : "High risk — take action"}
          </p>
        </div>

        <div className="kairo-card">
          <h3 className="section-title mb-3">Key Factors</h3>
          <div className="space-y-3">
            {[
              { label: "Avg Meetings/Day", value: snapshot?.avg_daily_meetings, icon: Clock },
              { label: "Messages/Day", value: snapshot?.messages_sent_daily, icon: TrendingUp },
              { label: "After-Hours %", value: snapshot?.after_hours_activity_pct ? `${Math.round(snapshot.after_hours_activity_pct)}%` : "—", icon: AlertTriangle },
              { label: "Workload", value: snapshot?.workload_trajectory || "stable", icon: Zap },
            ].map(({ label, value, icon: Icon }) => (
              <div key={label} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Icon className="w-3.5 h-3.5 text-slate-400" />
                  <span className="text-xs text-slate-500 dark:text-slate-400">{label}</span>
                </div>
                <span className="text-xs font-medium text-slate-900 dark:text-white">{value ?? "—"}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="kairo-card">
          <h3 className="section-title mb-3">Productivity Windows</h3>
          <div className="space-y-2">
            {Object.entries(snapshot?.productivity_multipliers || {}).map(([range, mult]: [string, any]) => {
              const barWidth = Math.round(Math.min(100, mult * 50));
              const color = mult >= 1.2 ? "bg-emerald-500" : mult >= 0.8 ? "bg-amber-400" : "bg-slate-300 dark:bg-slate-600";
              return (
                <div key={range} className="flex items-center gap-2">
                  <span className="text-[10px] text-slate-400 w-14 flex-shrink-0">{range}</span>
                  <div className="flex-1 h-2 bg-slate-100 dark:bg-[#2d2247] rounded-full overflow-hidden">
                    <div className={`h-full rounded-full ${color}`} style={{ width: `${barWidth}%` }} />
                  </div>
                  <span className="text-[10px] text-slate-400 w-8 text-right">{mult}x</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Trend */}
      {trend.length > 1 && (
        <div className="kairo-card mb-8">
          <h2 className="section-title mb-4">Burnout Trend (Weekly)</h2>
          <div className="flex items-end gap-3 h-32">
            {trend.map((s: any, i: number) => {
              const h = Math.max(8, (s.burnout_risk_score / 100) * 120);
              const color = s.burnout_risk_score < 30 ? "bg-emerald-400" : s.burnout_risk_score < 60 ? "bg-amber-400" : "bg-red-400";
              return (
                <div key={s.id || i} className="flex-1 flex flex-col items-center gap-1">
                  <span className="text-[9px] text-slate-400">{Math.round(s.burnout_risk_score)}</span>
                  <div className={`w-full rounded-t-md ${color}`} style={{ height: `${Math.round(h)}px` }} />
                  <span className="text-[8px] text-slate-300 dark:text-slate-600">
                    {s.snapshot_date ? new Date(s.snapshot_date).toLocaleDateString(undefined, { month: "short", day: "numeric" }) : ""}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Cold Contacts */}
      {coldContacts.length > 0 && (
        <div className="kairo-card mb-8">
          <h2 className="section-title mb-4">Cold Contact Alerts</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {coldContacts.map((c: any, i: number) => (
              <div key={i} className="flex items-center gap-3 p-3 rounded-xl bg-red-50/50 dark:bg-red-500/5 border border-red-100 dark:border-red-500/10">
                <UserX className="w-4 h-4 text-red-500 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-slate-900 dark:text-white">{c.contact}</p>
                  <p className="text-[10px] text-slate-400">Gap: {c.current_interaction_gap} days &middot; Goes cold in ~{c.days_until_cold} days</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Interventions */}
      {snapshot?.recommended_interventions?.length > 0 && (
        <div className="kairo-card">
          <h2 className="section-title mb-4">Recommended Interventions</h2>
          <div className="space-y-3">
            {snapshot.recommended_interventions.map((int: any) => (
              <div key={int.id} className="p-4 rounded-xl bg-slate-50 dark:bg-[#2d2247]/40 border border-slate-200 dark:border-[#2d2247]">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <p className="text-sm font-medium text-slate-900 dark:text-white mb-1">{int.action}</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mb-1">{int.reason}</p>
                    <p className="text-[10px] text-emerald-600 dark:text-emerald-400 font-medium">{int.impact}</p>
                  </div>
                  <button onClick={() => handleApply(int.id)}
                    className="px-3 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-700 text-white text-xs font-medium transition-colors flex-shrink-0">
                    Apply
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
