"use client";
import { useEffect, useState, useMemo } from "react";
import { useAuth } from "@/lib/store";
import { dashboard, agents as agentsApi, relationships, commitments as commitmentsApi, flow as flowApi, burnout as burnoutApi } from "@/lib/api";
import Link from "next/link";
import { Clock, Zap, Target, DollarSign, ArrowRight, Play, Pause, Ghost, Volume2, CalendarDays, AlertTriangle, CheckSquare, Shield, Heart } from "lucide-react";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const HOURS = Array.from({ length: 24 }, (_, i) => i);

function generateEnergyData(): number[][] {
  return DAYS.map((_, dayIdx) => {
    return HOURS.map((hour) => {
      if (hour < 6 || hour > 22) return 0;
      if (dayIdx >= 5) return Math.random() * 0.3;
      if (hour >= 9 && hour <= 11) return 0.5 + Math.random() * 0.5;
      if (hour >= 14 && hour <= 16) return 0.4 + Math.random() * 0.5;
      if (hour >= 12 && hour <= 13) return 0.1 + Math.random() * 0.2;
      return 0.1 + Math.random() * 0.4;
    });
  });
}

function energyColor(v: number): string {
  if (v === 0) return "bg-slate-100 dark:bg-slate-800/30";
  if (v < 0.2) return "bg-emerald-100 dark:bg-emerald-900/40";
  if (v < 0.4) return "bg-emerald-200 dark:bg-emerald-700/40";
  if (v < 0.6) return "bg-amber-200 dark:bg-amber-600/30";
  if (v < 0.8) return "bg-orange-200 dark:bg-orange-500/40";
  return "bg-red-200 dark:bg-red-500/40";
}

function energyLabel(v: number): string {
  if (v === 0) return "Free";
  if (v < 0.3) return "Deep work";
  if (v < 0.6) return "Light";
  if (v < 0.8) return "Busy";
  return "Heavy meetings";
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [stats, setStats] = useState<any>(null);
  const [decisions, setDecisions] = useState<any[]>([]);
  const [agent, setAgent] = useState<any>(null);
  const [relationshipAlerts, setRelationshipAlerts] = useState(0);
  const [commitStats, setCommitStats] = useState<any>(null);
  const [flowStatus, setFlowStatus] = useState<any>(null);
  const [burnoutScore, setBurnoutScore] = useState<number | null>(null);
  const energyData = useMemo(() => generateEnergyData(), []);

  useEffect(() => {
    if (!user) return;
    Promise.all([
      dashboard.stats().catch(() => null),
      dashboard.decisions({ limit: 8 }).catch(() => ({ actions: [] })),
      agentsApi.list().catch(() => []),
      relationships.toneShifts().catch(() => []),
    ]).then(([s, d, a, ts]) => {
      setStats(s);
      setDecisions(d?.actions || []);
      if (a?.length) setAgent(a[0]);
      const shifts = Array.isArray(ts) ? ts : ts?.shifts || [];
      setRelationshipAlerts(shifts.length);
    });
    commitmentsApi.stats().then(setCommitStats).catch(() => {});
    flowApi.status().then(setFlowStatus).catch(() => {});
    burnoutApi.current().then((b: any) => setBurnoutScore(b?.burnout_risk_score ?? null)).catch(() => {});
  }, [user]);

  if (!user) return null;
  const h = new Date().getHours();
  const greeting = h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
  const meetingCount = stats?.meetings_today ?? 3;
  const pendingDecisions = stats?.pending_decisions ?? decisions.filter((d: any) => d.status === "queued_for_review").length;

  return (
    <div className="p-8 max-w-6xl">
      {/* Morning Briefing */}
      <div className="relative overflow-hidden rounded-2xl mb-8 p-6 bg-white dark:bg-[#1e1533] border border-slate-200 dark:border-[#2d2247] shadow-sm transition-colors">
        <div className="absolute top-0 right-0 w-64 h-64 bg-violet-500/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" />
        <div className="relative">
          <div className="flex items-start justify-between">
            <div>
              <h1 className="font-semibold text-2xl text-slate-900 dark:text-white">
                {greeting}, {user.full_name?.split(" ")[0] || user.username}
              </h1>
              <p className="text-slate-400 text-sm mt-1">Here&apos;s your briefing for today.</p>
            </div>
            {agent && (
              <div className={`${agent.status === "running" ? "badge-success" : agent.status === "paused" ? "badge-warning" : "badge-neutral"}`}>
                <div className={`w-1.5 h-1.5 rounded-full ${agent.status === "running" ? "bg-emerald-500 animate-pulse" : agent.status === "paused" ? "bg-amber-500" : "bg-slate-400"}`} />
                {agent.status}{agent.ghost_mode?.enabled ? " \u00b7 Ghost" : ""}
              </div>
            )}
          </div>
          <div className="grid grid-cols-3 gap-4 mt-5">
            {[
              { icon: CalendarDays, color: "text-blue-500", val: meetingCount, label: "Meetings today" },
              { icon: Target, color: "text-amber-500", val: pendingDecisions, label: "Pending decisions" },
              { icon: AlertTriangle, color: "text-red-500", val: relationshipAlerts, label: "Relationship alerts" },
            ].map(({ icon: Icon, color, val, label }, i) => (
              <div key={i} className="flex items-center gap-3 px-4 py-3 rounded-xl bg-slate-50 dark:bg-[#2d2247]/40 border border-slate-100 dark:border-[#2d2247]">
                <Icon className={`w-4 h-4 ${color} flex-shrink-0`} />
                <div>
                  <p className="text-slate-900 dark:text-white text-sm font-medium">{val}</p>
                  <p className="text-slate-400 text-[10px]">{label}</p>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-4">
            <Link href="/dashboard/voice" className="kairo-btn bg-violet-50 dark:bg-violet-500/10 text-violet-600 dark:text-violet-400 border border-violet-200 dark:border-violet-500/20 hover:bg-violet-100 dark:hover:bg-violet-500/20 text-xs">
              <Volume2 className="w-3.5 h-3.5" />Listen to briefing
            </Link>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        {[
          { icon: Clock, label: "Hours Saved", value: stats?.time_saved_hours ?? "\u2014", color: "text-emerald-600 dark:text-emerald-400" },
          { icon: Zap, label: "Actions Taken", value: stats?.auto_handled ?? "\u2014", color: "text-violet-600 dark:text-violet-400" },
          { icon: Target, label: "Accuracy", value: stats?.ghost_mode_accuracy ? `${stats.ghost_mode_accuracy}%` : "\u2014", color: "text-blue-600 dark:text-blue-400" },
          { icon: DollarSign, label: "Spent", value: stats?.money_spent ? `$${stats.money_spent}` : "$0", color: "text-amber-600 dark:text-amber-400" },
        ].map(({ icon: Icon, label, value, color }, i) => (
          <div key={i} className="kairo-card">
            <div className="flex items-center gap-2 mb-2"><Icon className={`w-4 h-4 ${color}`} /><span className="text-slate-400 text-xs">{label}</span></div>
            <p className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white">{value}</p>
          </div>
        ))}
      </div>

      {/* Decisions + Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 mb-8">
        <div className="lg:col-span-3 kairo-card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="section-title">Recent Decisions</h2>
            <Link href="/dashboard/decisions" className="text-violet-600 dark:text-violet-400 text-xs hover:underline flex items-center gap-1">View all <ArrowRight className="w-3 h-3" /></Link>
          </div>
          <div className="space-y-2">
            {decisions.length === 0 ? <p className="text-slate-400 text-sm py-4">No actions yet. Launch your agent to get started.</p> :
              decisions.slice(0, 6).map((d: any) => (
                <div key={d.id} className="flex items-center gap-3 py-2 px-3 rounded-lg hover:bg-slate-50 dark:hover:bg-[#2d2247]/30 transition-colors">
                  <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${d.status === "executed" ? "bg-emerald-500" : d.status === "queued_for_review" ? "bg-amber-500" : "bg-red-500"}`} />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-slate-900 dark:text-white truncate">{d.action_taken}</p>
                    <p className="text-[10px] text-slate-400">{d.channel} &middot; {d.language_used?.toUpperCase()} &middot; {Math.round(d.confidence_score * 100)}%</p>
                  </div>
                </div>
              ))}
          </div>
        </div>
        <div className="lg:col-span-2 kairo-card">
          <h2 className="section-title mb-4">Quick Actions</h2>
          <div className="space-y-2.5">
            {!agent ? <Link href="/dashboard/agents" className="kairo-btn-primary w-full">Create Your Agent</Link> : <>
              {agent.status !== "running" && <button onClick={async () => { await agentsApi.launch(agent.id); setAgent({...agent, status: "running"}); }} className="kairo-btn-primary w-full"><Play className="w-4 h-4" />Launch Agent</button>}
              {agent.status === "running" && <button onClick={async () => { await agentsApi.pause(agent.id); setAgent({...agent, status: "paused"}); }} className="kairo-btn-secondary w-full"><Pause className="w-4 h-4" />Pause Agent</button>}
              <button onClick={async () => { const r = await agentsApi.toggleGhostMode(agent.id); setAgent({...agent, ghost_mode: {...agent.ghost_mode, enabled: r.ghost_mode_enabled}}); }}
                className={`kairo-btn-secondary w-full ${agent.ghost_mode?.enabled ? "!border-violet-500 !text-violet-600 dark:!text-violet-400" : ""}`}>
                <Ghost className="w-4 h-4" />{agent.ghost_mode?.enabled ? "Disable" : "Enable"} Ghost Mode
              </button>
              <Link href="/dashboard/settings" className="kairo-btn-ghost w-full">Configure Agent</Link>
            </>}
          </div>
        </div>
      </div>

      {/* New Feature Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <Link href="/dashboard/commitments" className="kairo-card hover:border-violet-500/20 transition-all group">
          <div className="flex items-center gap-2 mb-2">
            <CheckSquare className="w-4 h-4 text-blue-600 dark:text-blue-400" />
            <span className="text-slate-400 text-xs">Commitments</span>
          </div>
          <p className="text-lg font-bold text-slate-900 dark:text-white">
            {commitStats ? `${commitStats.active} active, ${commitStats.overdue} overdue` : "—"}
          </p>
          <p className="text-[10px] text-slate-400 mt-1">
            {commitStats ? `Reliability: ${commitStats.reliability_score}%` : "Track your promises"}
          </p>
        </Link>
        <Link href="/dashboard/flow" className="kairo-card hover:border-violet-500/20 transition-all group">
          <div className="flex items-center gap-2 mb-2">
            <Shield className="w-4 h-4 text-violet-600 dark:text-violet-400" />
            <span className="text-slate-400 text-xs">Flow Guardian</span>
          </div>
          <p className="text-lg font-bold text-slate-900 dark:text-white">
            {flowStatus?.in_flow ? `In Flow — ${Math.round(flowStatus.duration_minutes)}m` : "Not in flow"}
          </p>
          <p className="text-[10px] text-slate-400 mt-1">
            {flowStatus?.in_flow ? `${flowStatus.messages_held} msgs held` : "Start a flow session to focus"}
          </p>
        </Link>
        <Link href="/dashboard/burnout" className="kairo-card hover:border-violet-500/20 transition-all group">
          <div className="flex items-center gap-2 mb-2">
            <Heart className="w-4 h-4 text-pink-600 dark:text-pink-400" />
            <span className="text-slate-400 text-xs">Wellness</span>
          </div>
          <p className={`text-lg font-bold ${burnoutScore !== null ? (burnoutScore < 30 ? "text-emerald-600 dark:text-emerald-400" : burnoutScore < 60 ? "text-amber-600 dark:text-amber-400" : "text-red-600 dark:text-red-400") : "text-slate-900 dark:text-white"}`}>
            {burnoutScore !== null ? `Risk: ${Math.round(burnoutScore)}` : "—"}
          </p>
          <p className="text-[10px] text-slate-400 mt-1">
            {burnoutScore !== null ? (burnoutScore < 30 ? "Low risk" : burnoutScore < 60 ? "Moderate — check interventions" : "High risk — take action") : "Burnout prediction"}
          </p>
        </Link>
      </div>

      {/* Energy Map */}
      <div className="kairo-card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="section-title">Energy Map</h2>
          <p className="text-[10px] text-slate-400">Weekly meeting density &amp; focus time</p>
        </div>
        <div className="overflow-x-auto">
          <div className="min-w-[600px]">
            <div className="flex ml-10 mb-1">
              {HOURS.filter((h) => h % 3 === 0).map((hour) => (
                <div key={hour} className="text-[9px] text-slate-400" style={{ width: `${100 / 24 * 3}%` }}>
                  {hour === 0 ? "12a" : hour < 12 ? `${hour}a` : hour === 12 ? "12p" : `${hour - 12}p`}
                </div>
              ))}
            </div>
            {DAYS.map((day, dayIdx) => (
              <div key={day} className="flex items-center gap-2 mb-1">
                <span className="text-[10px] text-slate-400 w-8 text-right flex-shrink-0">{day}</span>
                <div className="flex-1 flex gap-[2px]">
                  {HOURS.map((hour) => {
                    const val = energyData[dayIdx][hour];
                    return (
                      <div key={hour} className={`flex-1 h-5 rounded-[3px] ${energyColor(val)} transition-colors hover:ring-1 hover:ring-violet-500/50 cursor-default`}
                        title={`${day} ${hour}:00 — ${energyLabel(val)}`} />
                    );
                  })}
                </div>
              </div>
            ))}
            <div className="flex items-center gap-4 mt-3 ml-10">
              {[
                { color: "bg-emerald-200 dark:bg-emerald-700/40", label: "Deep work" },
                { color: "bg-amber-200 dark:bg-amber-600/30", label: "Light" },
                { color: "bg-orange-200 dark:bg-orange-500/40", label: "Busy" },
                { color: "bg-red-200 dark:bg-red-500/40", label: "Heavy" },
                { color: "bg-slate-100 dark:bg-slate-800/30", label: "Free" },
              ].map(({ color, label }) => (
                <div key={label} className="flex items-center gap-1.5">
                  <div className={`w-3 h-3 rounded-[2px] ${color}`} />
                  <span className="text-[9px] text-slate-400">{label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
