"use client";
import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/lib/store";
import { ThemeProvider, useTheme } from "@/lib/theme";
import Link from "next/link";
import { Clock, LayoutDashboard, ScrollText, Bot, BarChart3, Settings, Users, LogOut, GitBranch, Mic, Globe, Sun, Moon, Store } from "lucide-react";
import { useState } from "react";
import { auth } from "@/lib/api";

function DashboardLayoutInner({ children }: { children: React.ReactNode }) {
  const { user, loadUser, logout } = useAuth();
  const { theme, toggle, mounted } = useTheme();
  const router = useRouter();
  const pathname = usePathname();
  const [lang, setLang] = useState<"EN" | "HI" | "Auto">("Auto");

  useEffect(() => { loadUser().then(() => { if (!localStorage.getItem("kairo_token")) router.push("/auth?mode=login"); }); }, [loadUser, router]);

  const nav = [
    { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
    { href: "/dashboard/decisions", label: "Decision Log", icon: ScrollText },
    { href: "/dashboard/relationships", label: "Relationships", icon: GitBranch },
    { href: "/dashboard/agents", label: "My Agent", icon: Bot },
    { href: "/dashboard/mesh", label: "Agent Mesh", icon: Users },
    { href: "/dashboard/marketplace", label: "Marketplace", icon: Store },
    { href: "/dashboard/voice", label: "Voice", icon: Mic },
    { href: "/dashboard/report", label: "Weekly Report", icon: BarChart3 },
    { href: "/dashboard/settings", label: "Settings", icon: Settings },
  ];

  const cycleLang = () => {
    const next = lang === "EN" ? "HI" : lang === "HI" ? "Auto" : "EN";
    setLang(next);
    auth.updateProfile({ preferred_language: next.toLowerCase() }).catch(() => {});
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-[#0f0a1a] transition-colors">
      <aside className="fixed left-0 top-0 h-full w-60 bg-white dark:bg-[#1a1128] border-r border-slate-200 dark:border-[#2d2247] p-5 flex flex-col z-20 transition-colors">
        <div className="flex items-center justify-between mb-8">
          <Link href="/" className="flex items-center gap-2">
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
        <nav className="space-y-0.5 flex-1">
          {nav.map(item => {
            const Icon = item.icon;
            const active = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
            return (
              <Link key={item.href} href={item.href} className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] transition-colors ${
                active
                  ? "bg-violet-50 dark:bg-violet-500/10 text-violet-700 dark:text-violet-300 font-medium"
                  : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-50 dark:hover:bg-[#2d2247]/50"
              }`}>
                <Icon className={`w-4 h-4 ${active ? "text-violet-600 dark:text-violet-400" : ""}`} />{item.label}
              </Link>
            );
          })}
        </nav>
        {user && (
          <div className="border-t border-slate-200 dark:border-[#2d2247] pt-4">
            <div className="flex items-center gap-2.5 mb-3">
              <div className="w-7 h-7 rounded-lg bg-violet-100 dark:bg-violet-500/15 flex items-center justify-center text-violet-600 dark:text-violet-400 text-xs font-bold">
                {(user.full_name || user.username)?.[0]?.toUpperCase()}
              </div>
              <div className="min-w-0">
                <p className="text-xs text-slate-900 dark:text-white truncate">{user.full_name || user.username}</p>
                <p className="text-[10px] text-slate-400 truncate">{user.email}</p>
              </div>
            </div>
            <button onClick={() => { logout(); router.push("/"); }} className="flex items-center gap-2 text-[11px] text-slate-400 hover:text-red-500 transition-colors">
              <LogOut className="w-3 h-3" />Sign out
            </button>
          </div>
        )}
      </aside>
      <div className="ml-60">{children}</div>
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
