"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/store";
import { auth as authApi, agents as agentsApi } from "@/lib/api";
import { User, Mic, Zap, Ghost, Plug, Save, Check, ExternalLink, Mail, Calendar, MessageSquare, Users as UsersIcon, Github } from "lucide-react";

export default function SettingsPage() {
  const { user, loadUser } = useAuth();
  const [agent, setAgent] = useState<any>(null);
  const [profile, setProfile] = useState({ full_name: "", preferred_language: "en", timezone: "Asia/Kolkata" });
  const [saved, setSaved] = useState("");

  useEffect(() => { loadUser(); }, [loadUser]);
  useEffect(() => { if (user) { setProfile({ full_name: user.full_name, preferred_language: user.preferred_language, timezone: user.timezone }); agentsApi.list().then(a => { if (a.length) setAgent(a[0]); }).catch(() => {}); } }, [user]);

  const save = async (section: string) => { setSaved(section); setTimeout(() => setSaved(""), 2000); };
  const saveProfile = async () => { await authApi.updateProfile(profile); save("profile"); };
  const updateAgent = async (u: any) => { if (agent) { const r = await agentsApi.update(agent.id, u); setAgent(r); } };

  if (!user) return null;

  const integrations = [
    { key: "gmail", label: "Gmail", icon: Mail, desc: "Read and send emails" },
    { key: "calendar", label: "Google Calendar", icon: Calendar, desc: "Manage events and scheduling" },
    { key: "slack", label: "Slack", icon: MessageSquare, desc: "Send and receive messages" },
    { key: "teams", label: "Microsoft Teams", icon: UsersIcon, desc: "Teams chat and channels" },
    { key: "github", label: "GitHub", icon: Github, desc: "PRs, issues, and notifications" },
  ];

  const confVal = Math.round((agent?.ghost_mode?.confidence_threshold||0.85)*100);

  return (
    <div className="p-8 max-w-3xl">
      <div className="mb-6 pb-5 border-b border-slate-200 dark:border-[#2d2247]">
        <h1 className="font-['DM_Serif_Display'] text-2xl text-slate-900 dark:text-white">Settings</h1>
        <p className="text-slate-400 text-sm mt-1">Personalize your Kairo experience</p>
      </div>

      {/* Profile */}
      <section className="kairo-card mb-5">
        <div className="flex items-center gap-2 mb-1"><User className="w-4 h-4 text-violet-600 dark:text-violet-400" /><h2 className="section-title">Profile</h2></div>
        <p className="text-slate-400 text-xs mb-4">Your identity and preferences</p>
        <div className="h-px bg-gradient-to-r from-slate-200 dark:from-[#2d2247] via-slate-300 dark:via-[#3d3257] to-slate-200 dark:to-[#2d2247] mb-4" />
        <div className="space-y-4">
          <div><label className="kairo-label">Full Name</label><input className="kairo-input" value={profile.full_name} onChange={e => setProfile(p => ({...p, full_name: e.target.value}))} /></div>
          <div><label className="kairo-label">Email</label><input className="kairo-input opacity-50 cursor-not-allowed" value={user.email} disabled /></div>
          <div className="grid grid-cols-2 gap-4">
            <div><label className="kairo-label">Language</label><select className="kairo-input" value={profile.preferred_language} onChange={e => setProfile(p => ({...p, preferred_language: e.target.value}))}><option value="en">English</option><option value="hi">Hindi</option><option value="auto">Auto-detect</option></select></div>
            <div><label className="kairo-label">Timezone</label><select className="kairo-input" value={profile.timezone} onChange={e => setProfile(p => ({...p, timezone: e.target.value}))}><option value="Asia/Kolkata">IST (India)</option><option value="America/Los_Angeles">PST</option><option value="America/New_York">EST</option><option value="Europe/London">GMT</option></select></div>
          </div>
          <button onClick={saveProfile} className={`kairo-btn-primary transition-all duration-300 ${saved === "profile" ? "!bg-emerald-600 !shadow-emerald-500/20" : ""}`}>
            {saved === "profile" ? <span className="save-success inline-flex items-center gap-2"><Check className="w-4 h-4" />Saved</span> : <><Save className="w-4 h-4" />Save Profile</>}
          </button>
        </div>
      </section>

      {agent && <>
        {/* Voice */}
        <section className="kairo-card mb-5">
          <div className="flex items-center gap-2 mb-1"><Mic className="w-4 h-4 text-violet-600 dark:text-violet-400" /><h2 className="section-title">Voice Settings</h2></div>
          <p className="text-slate-400 text-xs mb-4">How your agent speaks and briefs you</p>
          <div className="h-px bg-gradient-to-r from-slate-200 dark:from-[#2d2247] via-slate-300 dark:via-[#3d3257] to-slate-200 dark:to-[#2d2247] mb-4" />
          <div className="grid grid-cols-2 gap-4">
            <div><label className="kairo-label">Voice Language</label><select className="kairo-input" value={agent.voice?.language||"auto"} onChange={e => updateAgent({voice_language: e.target.value})}><option value="auto">Auto-detect</option><option value="en">English</option><option value="hi">Hindi</option></select></div>
            <div><label className="kairo-label">Voice</label><select className="kairo-input" value={agent.voice?.gender||"female"} onChange={e => updateAgent({voice_gender: e.target.value})}><option value="female">Female (Aria / Swara)</option><option value="male">Male (Guy / Madhur)</option></select></div>
            <div><label className="kairo-label">Briefing Time</label><input type="time" className="kairo-input" value={agent.voice?.briefing_time||"07:00"} onChange={e => updateAgent({briefing_time: e.target.value})} /></div>
            <div className="flex items-end pb-1">
              <label className="flex items-center gap-3 cursor-pointer text-xs text-slate-500 dark:text-slate-400">
                <input type="checkbox" checked={agent.voice?.briefing_enabled??true} onChange={e => updateAgent({briefing_enabled: e.target.checked})} className="toggle-switch" />
                Enable morning briefing
              </label>
            </div>
          </div>
        </section>

        {/* Deep Work */}
        <section className="kairo-card mb-5">
          <div className="flex items-center gap-2 mb-1"><Zap className="w-4 h-4 text-emerald-600 dark:text-emerald-400" /><h2 className="section-title">Deep Work Protection</h2></div>
          <p className="text-slate-400 text-xs mb-4">Protect your focus time from interruptions</p>
          <div className="h-px bg-gradient-to-r from-slate-200 dark:from-[#2d2247] via-slate-300 dark:via-[#3d3257] to-slate-200 dark:to-[#2d2247] mb-4" />
          <div className="grid grid-cols-2 gap-4">
            <div><label className="kairo-label">Start</label><input type="time" className="kairo-input" value={agent.scheduling?.deep_work_start||"09:00"} onChange={e => updateAgent({deep_work_start: e.target.value})} /></div>
            <div><label className="kairo-label">End</label><input type="time" className="kairo-input" value={agent.scheduling?.deep_work_end||"11:00"} onChange={e => updateAgent({deep_work_end: e.target.value})} /></div>
            <div><label className="kairo-label">Max Meetings/Day</label><input type="number" className="kairo-input" min={1} max={12} value={agent.scheduling?.max_meetings_per_day||6} onChange={e => updateAgent({max_meetings_per_day: parseInt(e.target.value)})} /></div>
            <div className="flex items-end pb-1">
              <label className="flex items-center gap-3 cursor-pointer text-xs text-slate-500 dark:text-slate-400">
                <input type="checkbox" checked={agent.scheduling?.auto_decline_enabled??false} onChange={e => updateAgent({auto_decline_enabled: e.target.checked})} className="toggle-switch" />
                Auto-decline conflicts
              </label>
            </div>
          </div>
        </section>

        {/* Ghost Mode */}
        <section className="kairo-card mb-5">
          <div className="flex items-center gap-2 mb-1"><Ghost className="w-4 h-4 text-violet-600 dark:text-violet-400" /><h2 className="section-title">Ghost Mode Guardrails</h2></div>
          <p className="text-slate-400 text-xs mb-4">Control how autonomously your agent operates</p>
          <div className="h-px bg-gradient-to-r from-slate-200 dark:from-[#2d2247] via-slate-300 dark:via-[#3d3257] to-slate-200 dark:to-[#2d2247] mb-4" />
          <div className="space-y-4">
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="kairo-label !mb-0">Confidence Threshold</label>
                <span className="text-sm font-semibold gradient-text">{confVal}%</span>
              </div>
              <div className="relative">
                <input type="range" min="50" max="99" className="kairo-range w-full" value={confVal} onChange={e => updateAgent({ghost_mode_confidence_threshold: parseInt(e.target.value)/100})} />
                <div className="flex justify-between text-[10px] text-slate-300 dark:text-slate-600 mt-1"><span>50% More autonomous</span><span>99% More cautious</span></div>
              </div>
              <p className="text-[10px] text-slate-400 mt-2">Only auto-act above this confidence level.</p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div><label className="kairo-label">Max Per Action ($)</label><input type="number" className="kairo-input" min={0} step={5} value={agent.ghost_mode?.max_spend_per_action||25} onChange={e => updateAgent({ghost_mode_max_spend_per_action: parseFloat(e.target.value)})} /></div>
              <div><label className="kairo-label">Max Per Day ($)</label><input type="number" className="kairo-input" min={0} step={10} value={agent.ghost_mode?.max_spend_per_day||100} onChange={e => updateAgent({ghost_mode_max_spend_per_day: parseFloat(e.target.value)})} /></div>
            </div>
          </div>
        </section>

        {/* Integrations */}
        <section className="kairo-card">
          <div className="flex items-center gap-2 mb-1"><Plug className="w-4 h-4 text-blue-600 dark:text-blue-400" /><h2 className="section-title">Integrations</h2></div>
          <p className="text-slate-400 text-xs mb-4">Connect your tools for seamless automation</p>
          <div className="h-px bg-gradient-to-r from-slate-200 dark:from-[#2d2247] via-slate-300 dark:via-[#3d3257] to-slate-200 dark:to-[#2d2247] mb-4" />
          <div className="space-y-2.5">
            {integrations.map(intg => {
              const Icon = intg.icon;
              const connected = agent.integrations?.[intg.key];
              return (
                <div key={intg.key} className={`flex items-center justify-between p-3.5 rounded-xl border transition-all duration-200 ${connected ? 'bg-emerald-500/[0.03] dark:bg-emerald-500/[0.05] border-emerald-500/15' : 'bg-slate-50 dark:bg-[#2d2247]/40 border-slate-200 dark:border-[#2d2247] hover:border-slate-200 dark:hover:border-[#2d2247]'}`}>
                  <div className="flex items-center gap-3">
                    <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${connected ? 'bg-emerald-50 dark:bg-emerald-500/10' : 'bg-slate-50 dark:bg-[#2d2247]/40'}`}>
                      <Icon className={`w-4 h-4 ${connected ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-400'}`} />
                    </div>
                    <div>
                      <div className="flex items-center gap-2"><p className="text-sm text-slate-900 dark:text-white">{intg.label}</p>{connected && <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.4)]" />}</div>
                      <p className="text-[10px] text-slate-400">{intg.desc}</p>
                    </div>
                  </div>
                  <button onClick={async () => { 
                    if (connected) return; 
                    try { 
                      const r = await agentsApi.connectIntegration(agent.id, intg.key); 
                      if (r.auth_url) {
                        const popup = window.open(r.auth_url, "_blank", "width=600,height=700");
                        // Poll for popup close, then sync connection status
                        const checkPopup = setInterval(async () => {
                          if (popup?.closed) {
                            clearInterval(checkPopup);
                            // Wait for Composio to save, then sync status to DB and refresh
                            await new Promise(res => setTimeout(res, 2000));
                            await agentsApi.integrationStatus(agent.id);
                            const agents = await agentsApi.list();
                            if (agents.length) setAgent(agents[0]);
                          }
                        }, 500);
                      }
                    } catch {} 
                  }}
                    className={connected ? "badge-success cursor-default" : "kairo-btn-secondary !text-xs !px-3.5 !py-1.5 hover:!border-violet-300 dark:hover:!border-violet-500/30 hover:!text-violet-600 dark:hover:!text-violet-400 transition-all duration-200"}>
                    {connected ? <><Check className="w-3 h-3" />Connected</> : <><ExternalLink className="w-3 h-3" />Connect</>}
                  </button>
                </div>
              );
            })}
          </div>
          <p className="text-[10px] text-slate-300 dark:text-slate-600 mt-4">OAuth managed by Composio. Connects open in a popup window.</p>
        </section>
      </>}
    </div>
  );
}
