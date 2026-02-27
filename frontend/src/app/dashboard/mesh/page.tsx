"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/store";
import { mesh } from "@/lib/api";
import { Users, ArrowLeftRight, Calendar, FileInput, Radio, Shield, Bot } from "lucide-react";

export default function MeshPage() {
  const { user } = useAuth();
  const [status, setStatus] = useState<any>(null);
  const [agents, setAgents] = useState<any[]>([]);

  useEffect(() => {
    if (!user) return;
    mesh.status().then(setStatus).catch(() => {});
    mesh.agents().then(setAgents).catch(() => {});
  }, [user]);

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
                  {/* Avatar ring with status-based color */}
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
