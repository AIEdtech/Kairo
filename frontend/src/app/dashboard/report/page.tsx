"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/store";
import { dashboard, relationships } from "@/lib/api";
import { BarChart3, Clock, Target, TrendingDown, TrendingUp, AlertTriangle, Mail, MessageSquare, Users as UsersIcon, Globe } from "lucide-react";

export default function ReportPage() {
  const { user } = useAuth();
  const [report, setReport] = useState<any>(null);
  const [toneShifts, setToneShifts] = useState<any[]>([]);
  const [neglected, setNeglected] = useState<any[]>([]);

  useEffect(() => { if (!user) return; dashboard.weeklyReport().then(setReport).catch(() => {}); relationships.toneShifts().then(setToneShifts).catch(() => {}); relationships.neglected().then(setNeglected).catch(() => {}); }, [user]);
  if (!user) return null;

  const chIcon = (c: string) => ({ email: Mail, slack: MessageSquare, teams: UsersIcon }[c] || Mail);

  return (
    <div className="p-8 max-w-5xl">
      <div className="mb-6 pb-5 border-b border-slate-200 dark:border-[#2d2247]">
        <h1 className="font-['DM_Serif_Display'] text-2xl text-slate-900 dark:text-white">Weekly Report</h1>
        {report && <p className="gradient-text text-sm mt-1 font-medium">{report.headline}</p>}
      </div>

      {!report ? (
        <div className="kairo-card text-center py-16">
          <BarChart3 className="w-10 h-10 text-slate-200 dark:text-slate-600 mx-auto mb-3" />
          <p className="text-slate-400 text-sm mb-1">No report data yet</p>
          <p className="text-slate-300 dark:text-slate-600 text-xs">Your first report appears after a week of activity.</p>
        </div>
      ) : <>
        {/* Hero stat cards with gradient backgrounds */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          {[
            { icon: Clock, label: "Hours Saved", value: report.time_saved.total_hours, color: "text-emerald-600 dark:text-emerald-400", gradient: "from-emerald-500/[0.07] to-transparent", border: "border-emerald-500/10" },
            { icon: Target, label: "Auto Actions", value: report.ghost_mode.total_actions, color: "text-violet-600 dark:text-violet-400", gradient: "from-violet-500/[0.07] to-transparent", border: "border-violet-500/10" },
            { icon: BarChart3, label: "Accuracy", value: `${report.ghost_mode.accuracy}%`, color: "text-blue-600 dark:text-blue-400", gradient: "from-blue-500/[0.07] to-transparent", border: "border-blue-500/10", trend: report.ghost_mode.accuracy >= 80 },
            { icon: Target, label: "Spent", value: `$${report.spending.total}`, color: "text-amber-600 dark:text-amber-400", gradient: "from-amber-500/[0.07] to-transparent", border: "border-amber-500/10" },
          ].map(({ icon: Icon, label, value, color, gradient, border, trend }, i) => (
            <div key={i} className={`kairo-card text-center relative overflow-hidden !border ${border}`}>
              <div className={`absolute inset-0 bg-gradient-to-b ${gradient} pointer-events-none`} />
              <div className="relative z-10">
                <Icon className={`w-5 h-5 ${color} mx-auto mb-2`} />
                <div className="flex items-center justify-center gap-1">
                  <p className={`stat-value ${color}`}>{value}</p>
                  {trend !== undefined && (
                    <span className={trend ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-500 dark:text-red-400'}>{trend ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}</span>
                  )}
                </div>
                <p className="text-[10px] text-slate-400 mt-1 font-medium uppercase tracking-wider">{label}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-6">
          <div className="kairo-card">
            <h2 className="section-title mb-4">Ghost Mode Performance</h2>
            <div className="space-y-3">
              <div>
                <div className="flex justify-between text-xs mb-1.5"><span className="text-slate-500 dark:text-slate-400">Accuracy</span><span className="text-emerald-600 dark:text-emerald-400 font-semibold">{report.ghost_mode.accuracy}%</span></div>
                <div className="progress-bar"><div className="progress-bar-fill bg-gradient-to-r from-emerald-500 to-emerald-400" style={{width:`${report.ghost_mode.accuracy}%`}} /></div>
              </div>
              <div className="h-px bg-slate-200 dark:bg-[#2d2247] my-1" />
              {[{l:"Approved",v:report.ghost_mode.approved,c:"text-emerald-600 dark:text-emerald-400",bg:"bg-emerald-400"},{l:"Edited",v:report.ghost_mode.edited,c:"text-amber-600 dark:text-amber-400",bg:"bg-amber-400"},{l:"Rejected",v:report.ghost_mode.rejected,c:"text-red-500 dark:text-red-400",bg:"bg-red-400"}].map(({l,v,c,bg}) => (
                <div key={l} className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2"><div className={`w-2 h-2 rounded-full ${bg}`} /><span className="text-slate-400">{l}</span></div>
                  <span className={`font-mono font-semibold ${c}`}>{v}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="kairo-card">
            <h2 className="section-title mb-4">Channel Breakdown</h2>
            <div className="space-y-3">{Object.entries(report.channels||{}).map(([ch,ct]) => { const Icon = chIcon(ch); const max = Math.max(...Object.values(report.channels).map(Number)); const pct = Math.min(100,((ct as number)/max)*100); return (
              <div key={ch}>
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2"><Icon className="w-3.5 h-3.5 text-slate-400" /><span className="text-xs text-slate-500 dark:text-slate-400 capitalize">{ch}</span></div>
                  <span className="text-xs text-slate-900 dark:text-white font-mono font-semibold">{ct as number}</span>
                </div>
                <div className="progress-bar"><div className="progress-bar-fill bg-gradient-to-r from-violet-600 to-violet-400" style={{width:`${pct}%`}} /></div>
              </div>); })}</div>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div className="kairo-card"><div className="flex items-center gap-2 mb-3"><Globe className="w-4 h-4 text-blue-600 dark:text-blue-400" /><h2 className="section-title">Languages</h2></div>
            <div className="space-y-2.5">{Object.entries(report.languages||{}).map(([l,c]) => (
              <div key={l} className="flex items-center justify-between text-xs p-2 rounded-lg hover:bg-slate-50 dark:hover:bg-[#2d2247]/30 transition-colors">
                <span className="text-slate-500 dark:text-slate-400">{l==="en"?"English":l==="hi"?"Hindi":l}</span>
                <span className="font-mono text-slate-900 dark:text-white font-semibold">{c as number}</span>
              </div>
            ))}</div>
          </div>

          {(toneShifts.length > 0 || neglected.length > 0) && (
            <div className="kairo-card"><div className="flex items-center gap-2 mb-3"><AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400" /><h2 className="section-title">Relationship Alerts</h2></div>
              <div className="space-y-1.5">
                {toneShifts.map((t,i) => (
                  <div key={`t${i}`} className={`flex items-center justify-between text-xs p-2.5 rounded-lg border transition-all ${t.direction==="declining" ? "border-red-500/15 bg-red-500/[0.03]" : "border-emerald-500/15 bg-emerald-500/[0.03]"}`}>
                    <span className="text-slate-500 dark:text-slate-400 font-medium">{t.contact}</span>
                    <span className={`flex items-center gap-1.5 font-semibold ${t.direction==="declining"?"text-red-500 dark:text-red-400":"text-emerald-600 dark:text-emerald-400"}`}>
                      {t.direction==="declining"?<TrendingDown className="w-3.5 h-3.5"/>:<TrendingUp className="w-3.5 h-3.5"/>}{Math.abs(t.delta)}
                    </span>
                  </div>
                ))}
                {neglected.map((n,i) => (
                  <div key={`n${i}`} className="flex items-center justify-between text-xs p-2.5 rounded-lg border border-amber-500/15 bg-amber-500/[0.03]">
                    <span className="text-slate-500 dark:text-slate-400">{n.contact} <span className="text-slate-300 dark:text-slate-600">via {n.channel}</span></span>
                    <span className="text-amber-600 dark:text-amber-400 font-semibold">{n.days_since_contact}d ago</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </>}
    </div>
  );
}
