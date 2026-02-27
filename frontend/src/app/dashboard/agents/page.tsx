"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/store";
import { agents as agentsApi } from "@/lib/api";
import Link from "next/link";
import { Bot, Play, Pause, Square, Ghost, Mic, Shield, Zap, Clock, Settings, Trash2, Plus, Plug } from "lucide-react";

export default function AgentsPage() {
  const { user } = useAuth();
  const [agent, setAgent] = useState<any>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ name: "My Kairo Agent", voice_language: "auto", voice_gender: "female" });

  useEffect(() => { if (user) agentsApi.list().then(a => { if (a.length) setAgent(a[0]); }).catch(() => {}); }, [user]);
  if (!user) return null;

  const create = async () => { setCreating(true); try { setAgent(await agentsApi.create(form)); } finally { setCreating(false); } };
  const statusMap: Record<string,{badge:string;icon:any}> = { draft: {badge:"badge-neutral",icon:Bot}, running: {badge:"badge-success",icon:Play}, paused: {badge:"badge-warning",icon:Pause}, stopped: {badge:"badge-danger",icon:Square} };

  return (
    <div className="p-8 max-w-3xl">
      <div className="mb-6 pb-5 border-b border-slate-200 dark:border-[#2d2247]">
        <h1 className="font-['DM_Serif_Display'] text-2xl text-slate-900 dark:text-white">My Agent</h1>
        <p className="text-slate-400 text-sm mt-1">Configure and manage your cognitive co-processor</p>
      </div>

      {!agent ? (
        <div className="kairo-card text-center py-16 relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-b from-violet-500/[0.03] to-transparent pointer-events-none" />
          <div className="relative z-10">
            <div className="w-16 h-16 rounded-2xl bg-violet-50 dark:bg-violet-500/10 flex items-center justify-center mx-auto mb-6 border border-violet-200 dark:border-violet-500/20"><Bot className="w-8 h-8 text-violet-600 dark:text-violet-400" /></div>
            <h2 className="font-['DM_Serif_Display'] text-xl text-slate-900 dark:text-white mb-2">Create Your Kairo Agent</h2>
            <p className="text-slate-400 text-sm mb-8 max-w-sm mx-auto">Your cognitive co-processor. It learns your relationships, protects your time, and acts on your behalf.</p>
            <div className="max-w-sm mx-auto space-y-4 text-left mb-8 p-5 rounded-xl bg-slate-50 dark:bg-[#2d2247]/40 border border-slate-200 dark:border-[#2d2247]">
              <div><label className="kairo-label">Agent Name</label><input className="kairo-input" value={form.name} onChange={e => setForm(p => ({...p, name: e.target.value}))} /></div>
              <div><label className="kairo-label">Voice Language</label><select className="kairo-input" value={form.voice_language} onChange={e => setForm(p => ({...p, voice_language: e.target.value}))}><option value="auto">Auto-detect (EN + HI)</option><option value="en">English</option><option value="hi">Hindi</option></select></div>
              <div><label className="kairo-label">Voice</label><select className="kairo-input" value={form.voice_gender} onChange={e => setForm(p => ({...p, voice_gender: e.target.value}))}><option value="female">Female (Aria / Swara)</option><option value="male">Male (Guy / Madhur)</option></select></div>
            </div>
            <button onClick={create} disabled={creating} className="kairo-btn-primary px-10 py-3 text-base"><Plus className="w-4 h-4" />{creating ? "Creating..." : "Create Agent"}</button>
          </div>
        </div>
      ) : (
        <div className="space-y-5">
          {/* Agent status card with gradient accent when running */}
          <div className={`kairo-card relative overflow-hidden ${agent.status === 'running' ? 'running-glow !border-emerald-500/20' : ''}`}>
            {agent.status === 'running' && <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-emerald-400 to-transparent" />}
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-3">
                <div className={`w-11 h-11 rounded-xl flex items-center justify-center transition-all duration-300 ${agent.status === 'running' ? 'bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-500/20' : 'bg-violet-50 dark:bg-violet-500/10 border border-violet-200 dark:border-violet-500/20'}`}>
                  <Bot className={`w-5 h-5 ${agent.status === 'running' ? 'text-emerald-600 dark:text-emerald-400' : 'text-violet-600 dark:text-violet-400'}`} />
                </div>
                <div><h2 className="text-slate-900 dark:text-white font-semibold text-lg">{agent.name}</h2>
                  <div className={`${statusMap[agent.status]?.badge} mt-1`}><div className={`w-1.5 h-1.5 rounded-full ${agent.status === "running" ? "bg-emerald-400 animate-pulse" : ""}`} />{agent.status}{agent.ghost_mode?.enabled ? " · Ghost" : ""}</div>
                </div>
              </div>
            </div>
            <div className="flex gap-2 flex-wrap">
              {agent.status !== "running" && <button onClick={async () => { const r = await agentsApi.launch(agent.id); setAgent(r.agent); }} className="kairo-btn-primary"><Play className="w-4 h-4" />Launch</button>}
              {agent.status === "running" && <button onClick={async () => { const r = await agentsApi.pause(agent.id); setAgent(r.agent); }} className="kairo-btn-secondary"><Pause className="w-4 h-4" />Pause</button>}
              {!["stopped","draft"].includes(agent.status) && <button onClick={async () => { const r = await agentsApi.stop(agent.id); setAgent(r.agent); }} className="kairo-btn-danger"><Square className="w-4 h-4" />Stop</button>}
              <button onClick={async () => { const r = await agentsApi.toggleGhostMode(agent.id); setAgent({...agent, ghost_mode: {...agent.ghost_mode, enabled: r.ghost_mode_enabled}}); }}
                className={`kairo-btn-secondary transition-all duration-200 ${agent.ghost_mode?.enabled ? "!border-violet-500 !text-violet-600 dark:!text-violet-400 glow-pulse" : ""}`}><Ghost className="w-4 h-4" />{agent.ghost_mode?.enabled ? "Disable" : "Enable"} Ghost Mode</button>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-4">
            {[
              { icon: Mic, color: 'text-violet-600 dark:text-violet-400', bg: 'bg-violet-50 dark:bg-violet-500/10', label: 'Voice', main: `${agent.voice?.language || "auto"} · ${agent.voice?.gender === "male" ? "Madhur" : "Swara"}`, sub: `Briefing: ${agent.voice?.briefing_time}` },
              { icon: Zap, color: 'text-emerald-600 dark:text-emerald-400', bg: 'bg-emerald-50 dark:bg-emerald-500/10', label: 'Deep Work', main: `${agent.scheduling?.deep_work_start}–${agent.scheduling?.deep_work_end}`, sub: `Max ${agent.scheduling?.max_meetings_per_day} mtgs/day` },
              { icon: Shield, color: 'text-blue-600 dark:text-blue-400', bg: 'bg-blue-50 dark:bg-blue-500/10', label: 'Ghost Mode', main: `${Math.round((agent.ghost_mode?.confidence_threshold||0.85)*100)}% threshold`, sub: `$${agent.ghost_mode?.max_spend_per_day}/day limit` },
            ].map(({icon: I, color, bg, label, main, sub}) => (
              <div key={label} className="kairo-card hover:border-slate-300 dark:hover:border-[#3d3257] transition-all duration-200">
                <div className="flex items-center gap-2 mb-3"><div className={`w-7 h-7 rounded-lg ${bg} flex items-center justify-center`}><I className={`w-3.5 h-3.5 ${color}`} /></div><span className="text-xs text-slate-400 font-medium">{label}</span></div>
                <p className="text-xs text-slate-900 dark:text-white font-medium">{main}</p><p className="text-[10px] text-slate-400 mt-1">{sub}</p>
              </div>
            ))}
          </div>

          {/* Integration status grid with connected/disconnected visual states */}
          <div className="kairo-card">
            <div className="flex items-center gap-2 mb-4"><Plug className="w-4 h-4 text-slate-400" /><span className="text-sm text-slate-900 dark:text-white font-medium">Integrations</span></div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {Object.entries(agent.integrations||{}).map(([k,v]) => (
                <div key={k} className={`flex items-center gap-2.5 p-2.5 rounded-lg border transition-all duration-200 ${v ? 'bg-emerald-50 dark:bg-emerald-500/10 border-emerald-500/15' : 'bg-slate-50 dark:bg-[#2d2247]/40 border-slate-200 dark:border-[#2d2247]'}`}>
                  <div className={`w-2 h-2 rounded-full flex-shrink-0 ${v ? 'bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.4)]' : 'bg-slate-300 dark:bg-slate-600'}`} />
                  <span className={`text-xs capitalize ${v ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-400'}`}>{k}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="flex gap-2">
            <Link href="/dashboard/settings" className="kairo-btn-secondary"><Settings className="w-4 h-4" />Configure</Link>
            <button onClick={async () => { await agentsApi.delete(agent.id); setAgent(null); }} className="kairo-btn-danger"><Trash2 className="w-4 h-4" />Delete</button>
          </div>
        </div>
      )}
    </div>
  );
}
