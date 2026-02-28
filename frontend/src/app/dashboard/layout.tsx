"use client";
import { useEffect, useState, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/lib/store";
import { ThemeProvider, useTheme } from "@/lib/theme";
import Link from "next/link";
import { Clock, LayoutDashboard, ScrollText, Bot, BarChart3, Settings, Users, LogOut, GitBranch, Mic, Globe, Sun, Moon, Store, CheckSquare, Forward, Heart, GitCompare, Shield, ChevronDown, Activity } from "lucide-react";
import { auth } from "@/lib/api";
import CommandBar from "@/components/CommandBar";

type NavItem = { href: string; label: string; icon: React.ComponentType<{ className?: string }> };
type NavGroup = { label: string; items: NavItem[]; collapsible: boolean };

const navGroups: NavGroup[] = [
  {
    label: "OVERVIEW",
    collapsible: false,
    items: [
      { href: "/dashboard/voice", label: "Talk to Agent", icon: Mic },
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { href: "/dashboard/agents", label: "My Agent", icon: Bot },
      { href: "/dashboard/decisions", label: "Decisions", icon: ScrollText },
    ],
  },
  {
    label: "AUTOPILOT",
    collapsible: false,
    items: [
      { href: "/dashboard/flow", label: "Focus Guard", icon: Shield },
      { href: "/dashboard/commitments", label: "Promises", icon: CheckSquare },
      { href: "/dashboard/delegation", label: "Delegate", icon: Forward },
      { href: "/dashboard/burnout", label: "Wellness", icon: Heart },
    ],
  },
  {
    label: "INSIGHTS",
    collapsible: true,
    items: [
      { href: "/dashboard/relationships", label: "Relationships", icon: GitBranch },
      { href: "/dashboard/replay", label: "What-If Replay", icon: GitCompare },
      { href: "/dashboard/report", label: "Weekly Report", icon: BarChart3 },
    ],
  },
  {
    label: "NETWORK",
    collapsible: true,
    items: [
      { href: "/dashboard/mesh", label: "Agent Mesh", icon: Users },
      { href: "/dashboard/marketplace", label: "Marketplace", icon: Store },
    ],
  },
];

const COLLAPSE_STORAGE_KEY = "kairo_sidebar_collapse";

function getInitialCollapseState(): Record<string, boolean> {
  if (typeof window === "undefined") return {};
  try {
    const stored = localStorage.getItem(COLLAPSE_STORAGE_KEY);
    if (stored) return JSON.parse(stored);
  } catch {}
  return {};
}

function DashboardLayoutInner({ children }: { children: React.ReactNode }) {
  const { user, loadUser, logout } = useAuth();
  const { theme, toggle, mounted } = useTheme();
  const router = useRouter();
  const pathname = usePathname();
  const [lang, setLang] = useState<"EN" | "HI" | "Auto">("Auto");
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>(getInitialCollapseState);

  useEffect(() => { loadUser().then(() => { if (!localStorage.getItem("kairo_token")) router.push("/auth?mode=login"); }); }, [loadUser, router]);

  const toggleGroup = useCallback((label: string) => {
    setCollapsed(prev => {
      const next = { ...prev, [label]: !prev[label] };
      try { localStorage.setItem(COLLAPSE_STORAGE_KEY, JSON.stringify(next)); } catch {}
      return next;
    });
  }, []);

  const cycleLang = () => {
    const next = lang === "EN" ? "HI" : lang === "HI" ? "Auto" : "EN";
    setLang(next);
    auth.updateProfile({ preferred_language: next.toLowerCase() }).catch(() => {});
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-[#0f0a1a] transition-colors">
      <aside className="fixed left-0 top-0 h-full w-[240px] bg-white dark:bg-[#1a1128] border-r border-slate-200 dark:border-[#2d2247] px-3 py-5 flex flex-col z-20 transition-colors">
        {/* Logo + controls */}
        <div className="flex items-center justify-between mb-7 px-2">
          <Link href="/" className="flex items-center gap-2.5">
            <Clock className="w-5 h-5 text-violet-600 dark:text-violet-400" />
            <span className="font-['DM_Serif_Display'] text-lg text-slate-900 dark:text-white">Kairo</span>
          </Link>
          <div className="flex items-center gap-1">
            <button
              onClick={toggle}
              className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-[#2d2247] transition-colors text-slate-400"
              title="Toggle theme"
            >
              {mounted ? (theme === "light" ? <Moon className="w-3.5 h-3.5" /> : <Sun className="w-3.5 h-3.5" />) : <div className="w-3.5 h-3.5" />}
            </button>
            <button
              onClick={cycleLang}
              className="flex items-center gap-1 px-2 py-1 rounded-lg hover:bg-slate-100 dark:hover:bg-[#2d2247] text-[10px] font-medium text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
              title="Language preference"
            >
              <Globe className="w-3 h-3" />
              {lang}
            </button>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto space-y-3">
          {navGroups.map((group, groupIdx) => {
            const isCollapsed = group.collapsible && collapsed[group.label];
            return (
              <div key={group.label}>
                {groupIdx > 0 && <div className="border-t border-slate-100 dark:border-[#2d2247]/60 mb-2" />}
                {group.collapsible ? (
                  <button
                    onClick={() => toggleGroup(group.label)}
                    className="flex items-center justify-between w-full px-2.5 py-1 mb-1"
                  >
                    <span className="text-[10px] uppercase tracking-[0.1em] font-semibold text-slate-400 dark:text-slate-500">{group.label}</span>
                    <ChevronDown className={`w-3 h-3 text-slate-400 dark:text-slate-500 transition-transform ${isCollapsed ? "-rotate-90" : ""}`} />
                  </button>
                ) : (
                  <div className="px-2.5 py-1 mb-1">
                    <span className="text-[10px] uppercase tracking-[0.1em] font-semibold text-slate-400 dark:text-slate-500">{group.label}</span>
                  </div>
                )}
                {!isCollapsed && (
                  <div className="space-y-0.5">
                    {group.items.map(item => {
                      const Icon = item.icon;
                      const active = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
                      return (
                        <Link key={item.href} href={item.href} className={`flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-[13px] transition-all ${
                          active
                            ? "bg-violet-50 dark:bg-violet-500/10 text-violet-700 dark:text-violet-300 font-medium"
                            : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-50 dark:hover:bg-[#2d2247]/50"
                        }`}>
                          {active && <div className="w-1 h-3.5 rounded-full bg-violet-600 dark:bg-violet-400 -ml-0.5 mr-0" />}
                          <Icon className={`w-4 h-4 flex-shrink-0 ${active ? "text-violet-600 dark:text-violet-400" : ""}`} />
                          {item.label}
                        </Link>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </nav>

        {/* Settings */}
        <div className="border-t border-slate-200 dark:border-[#2d2247] pt-3 mx-1">
          {(() => {
            const active = pathname === "/dashboard/settings";
            return (
              <Link href="/dashboard/settings" className={`flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-[13px] transition-all ${
                active
                  ? "bg-violet-50 dark:bg-violet-500/10 text-violet-700 dark:text-violet-300 font-medium"
                  : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-50 dark:hover:bg-[#2d2247]/50"
              }`}>
                {active && <div className="w-1 h-3.5 rounded-full bg-violet-600 dark:bg-violet-400 -ml-0.5 mr-0" />}
                <Settings className={`w-4 h-4 ${active ? "text-violet-600 dark:text-violet-400" : ""}`} />Settings
              </Link>
            );
          })()}
        </div>

        {/* User profile */}
        {user && (
          <div className="border-t border-slate-200 dark:border-[#2d2247] pt-4 mt-3 px-2">
            <div className="flex items-center gap-2.5 mb-3">
              <div className="w-8 h-8 rounded-lg bg-violet-100 dark:bg-violet-500/15 flex items-center justify-center text-violet-600 dark:text-violet-400 text-xs font-bold">
                {(user.full_name || user.username)?.[0]?.toUpperCase()}
              </div>
              <div className="min-w-0">
                <p className="text-sm text-slate-900 dark:text-white truncate font-medium">{user.full_name || user.username}</p>
                <p className="text-[11px] text-slate-400 truncate">{user.email}</p>
              </div>
            </div>
            <button onClick={() => { logout(); router.push("/"); }} className="flex items-center gap-2 text-xs text-slate-400 hover:text-red-500 transition-colors">
              <LogOut className="w-3.5 h-3.5" />Sign out
            </button>
          </div>
        )}
      </aside>
      <div className="ml-[260px]">
        {children}
        <CommandBar />
      </div>
    </div>
  );
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <DashboardLayoutInner>{children}</DashboardLayoutInner>
    </ThemeProvider>
  );
}
