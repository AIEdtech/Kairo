"use client";
import { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/store";
import { auth as authApi } from "@/lib/api";
import Link from "next/link";
import { Clock, Mail, Lock, User, Globe, ArrowRight, KeyRound, CheckCircle } from "lucide-react";

export default function AuthPage() {
  return (
    <Suspense>
      <AuthPageInner />
    </Suspense>
  );
}

function AuthPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login, register, user, isLoading, error, clearError } = useAuth();
  const [mode, setMode] = useState<"login"|"register"|"forgot"|"reset">(
    (searchParams.get("mode") as "login"|"register") || "login"
  );
  const [form, setForm] = useState({ email: "", username: "", password: "", full_name: "", preferred_language: "en" });
  const [resetCode, setResetCode] = useState("");
  const [resetEmail, setResetEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [generatedCode, setGeneratedCode] = useState("");
  const [resetMsg, setResetMsg] = useState("");
  const [resetError, setResetError] = useState("");
  const [resetLoading, setResetLoading] = useState(false);

  useEffect(() => { if (user) router.push("/dashboard"); }, [user, router]);
  useEffect(() => { clearError(); setResetError(""); setResetMsg(""); }, [mode, clearError]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    mode === "login" ? await login(form.email, form.password) : await register(form);
  };

  const handleForgotSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setResetLoading(true);
    setResetError("");
    try {
      const res = await authApi.forgotPassword(resetEmail);
      setGeneratedCode(res.code);
      setMode("reset");
    } catch (err: any) {
      setResetError(err.message || "Failed to generate reset code");
    } finally {
      setResetLoading(false);
    }
  };

  const handleResetSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setResetLoading(true);
    setResetError("");
    try {
      await authApi.resetPassword(resetEmail, resetCode, newPassword);
      setResetMsg("Password reset successfully! Redirecting to login...");
      setTimeout(() => {
        setMode("login");
        setResetMsg("");
        setGeneratedCode("");
        setResetCode("");
        setNewPassword("");
      }, 2000);
    } catch (err: any) {
      setResetError(err.message || "Failed to reset password");
    } finally {
      setResetLoading(false);
    }
  };

  const inputClass = "w-full px-4 py-3 pl-11 bg-[#2d2247]/60 border border-[#3d3257] rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-violet-500 focus:ring-2 focus:ring-violet-500/20 transition-all text-sm";

  return (
    <main className="min-h-screen relative overflow-hidden flex items-center justify-center px-4"
      style={{ background: "linear-gradient(135deg, #1e1145 0%, #2d1b69 30%, #4c1d95 60%, #1e1145 100%)" }}>

      {/* Gradient orbs */}
      <div className="absolute top-0 left-1/3 w-[600px] h-[600px] bg-violet-600/20 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-0 right-1/4 w-[500px] h-[500px] bg-purple-500/15 rounded-full blur-[100px] pointer-events-none" />

      <div className="relative z-10 w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-10">
          <Link href="/" className="inline-flex items-center gap-2.5">
            <svg width="32" height="32" viewBox="0 0 26 26" fill="none"><circle cx="13" cy="13" r="12" stroke="#a78bfa" strokeWidth="2" /><path d="M13 6v7l5 3" stroke="#a78bfa" strokeWidth="2" strokeLinecap="round" /></svg>
            <span className="font-['DM_Serif_Display'] text-3xl text-white">Kairo</span>
          </Link>
        </div>

        {/* Heading */}
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-white mb-2">
            {mode === "login" ? "Welcome back" : mode === "register" ? "Create your account" : mode === "forgot" ? "Reset your password" : "Enter reset code"}
          </h1>
          <p className="text-violet-300 text-sm">
            {mode === "login" ? "Sign in to your account to continue" : mode === "register" ? "Start building with Kairo for free" : mode === "forgot" ? "We'll generate a reset code for your account" : "Enter the code and your new password"}
          </p>
        </div>

        {/* Form card */}
        <div className="bg-[#1e1533]/80 backdrop-blur-xl rounded-2xl p-8 border border-[#3d3257]/50 shadow-2xl">
          {error && (mode === "login" || mode === "register") && <div className="bg-red-500/10 border border-red-500/20 text-red-300 px-4 py-2.5 rounded-xl text-xs mb-5">{error}</div>}
          {resetError && <div className="bg-red-500/10 border border-red-500/20 text-red-300 px-4 py-2.5 rounded-xl text-xs mb-5">{resetError}</div>}
          {resetMsg && <div className="bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 px-4 py-2.5 rounded-xl text-xs mb-5 flex items-center gap-2"><CheckCircle className="w-4 h-4" />{resetMsg}</div>}

          {/* ── Login / Register Form ── */}
          {(mode === "login" || mode === "register") && (
            <form onSubmit={handleSubmit} className="space-y-5">
              {mode === "register" && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1.5">Full Name</label>
                    <div className="relative">
                      <User className="absolute left-3.5 top-3.5 w-4 h-4 text-slate-500" />
                      <input className={inputClass}
                        placeholder="Arjun Sharma" value={form.full_name} onChange={e => setForm(p => ({...p, full_name: e.target.value}))} />
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1.5">Username</label>
                    <input className="w-full px-4 py-3 bg-[#2d2247]/60 border border-[#3d3257] rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-violet-500 focus:ring-2 focus:ring-violet-500/20 transition-all text-sm"
                      placeholder="arjun" required value={form.username} onChange={e => setForm(p => ({...p, username: e.target.value}))} />
                  </div>
                </>
              )}
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">Email address</label>
                <div className="relative">
                  <Mail className="absolute left-3.5 top-3.5 w-4 h-4 text-slate-500" />
                  <input className={inputClass}
                    type="email" placeholder="you@company.com" required value={form.email} onChange={e => setForm(p => ({...p, email: e.target.value}))} />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">Password</label>
                <div className="relative">
                  <Lock className="absolute left-3.5 top-3.5 w-4 h-4 text-slate-500" />
                  <input className={inputClass}
                    type="password" placeholder="Enter your password" required minLength={6} value={form.password} onChange={e => setForm(p => ({...p, password: e.target.value}))} />
                </div>
              </div>
              {mode === "register" && (
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1.5">Language</label>
                  <div className="relative">
                    <Globe className="absolute left-3.5 top-3.5 w-4 h-4 text-slate-500" />
                    <select className="w-full px-4 py-3 pl-11 bg-[#2d2247]/60 border border-[#3d3257] rounded-xl text-white focus:outline-none focus:border-violet-500 focus:ring-2 focus:ring-violet-500/20 transition-all text-sm"
                      value={form.preferred_language} onChange={e => setForm(p => ({...p, preferred_language: e.target.value}))}>
                      <option value="en">English</option><option value="hi">Hindi</option><option value="auto">Auto-detect</option>
                    </select>
                  </div>
                </div>
              )}

              {mode === "login" && (
                <div className="flex items-center justify-between text-sm">
                  <label className="flex items-center gap-2 text-slate-400 cursor-pointer">
                    <input type="checkbox" className="w-4 h-4 rounded border-[#3d3257] bg-[#2d2247] text-violet-600 focus:ring-violet-500/20" />
                    Remember me
                  </label>
                  <button type="button" onClick={() => { setMode("forgot"); setResetEmail(form.email); }} className="text-violet-400 hover:text-violet-300 transition-colors">Forgot password?</button>
                </div>
              )}

              <button type="submit" disabled={isLoading}
                className="w-full py-3.5 rounded-xl font-semibold text-sm text-white transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                style={{ background: "linear-gradient(135deg, #7c3aed 0%, #6d28d9 50%, #4f46e5 100%)" }}>
                {isLoading ? "Please wait..." : mode === "login" ? <>Sign in <ArrowRight className="w-4 h-4" /></> : "Create Account"}
              </button>
            </form>
          )}

          {/* ── Forgot Password Form ── */}
          {mode === "forgot" && (
            <form onSubmit={handleForgotSubmit} className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">Email address</label>
                <div className="relative">
                  <Mail className="absolute left-3.5 top-3.5 w-4 h-4 text-slate-500" />
                  <input className={inputClass}
                    type="email" placeholder="you@company.com" required value={resetEmail} onChange={e => setResetEmail(e.target.value)} />
                </div>
              </div>
              <button type="submit" disabled={resetLoading}
                className="w-full py-3.5 rounded-xl font-semibold text-sm text-white transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                style={{ background: "linear-gradient(135deg, #7c3aed 0%, #6d28d9 50%, #4f46e5 100%)" }}>
                {resetLoading ? "Please wait..." : <>Generate Reset Code <KeyRound className="w-4 h-4" /></>}
              </button>
            </form>
          )}

          {/* ── Reset Password Form ── */}
          {mode === "reset" && (
            <form onSubmit={handleResetSubmit} className="space-y-5">
              {generatedCode && (
                <div className="bg-violet-500/10 border border-violet-500/20 rounded-xl p-4 text-center">
                  <p className="text-violet-300 text-xs mb-1">Your reset code (demo — no email sent)</p>
                  <p className="text-3xl font-mono font-bold text-white tracking-[0.3em]">{generatedCode}</p>
                </div>
              )}
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">Reset Code</label>
                <div className="relative">
                  <KeyRound className="absolute left-3.5 top-3.5 w-4 h-4 text-slate-500" />
                  <input className={inputClass}
                    placeholder="Enter 6-digit code" required value={resetCode} onChange={e => setResetCode(e.target.value)} />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">New Password</label>
                <div className="relative">
                  <Lock className="absolute left-3.5 top-3.5 w-4 h-4 text-slate-500" />
                  <input className={inputClass}
                    type="password" placeholder="Enter new password" required minLength={6} value={newPassword} onChange={e => setNewPassword(e.target.value)} />
                </div>
              </div>
              <button type="submit" disabled={resetLoading}
                className="w-full py-3.5 rounded-xl font-semibold text-sm text-white transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                style={{ background: "linear-gradient(135deg, #7c3aed 0%, #6d28d9 50%, #4f46e5 100%)" }}>
                {resetLoading ? "Please wait..." : <>Reset Password <ArrowRight className="w-4 h-4" /></>}
              </button>
            </form>
          )}

          <p className="text-center text-slate-500 text-sm mt-6">
            {mode === "login" ? "Don't have an account?" : mode === "register" ? "Already have an account?" : ""}{" "}
            {(mode === "forgot" || mode === "reset") ? (
              <button onClick={() => setMode("login")} className="text-violet-400 hover:text-violet-300 font-medium transition-colors">
                Back to sign in
              </button>
            ) : (
              <button onClick={() => setMode(mode === "login" ? "register" : "login")} className="text-violet-400 hover:text-violet-300 font-medium transition-colors">
                {mode === "login" ? "Sign up" : "Sign in"}
              </button>
            )}
          </p>
        </div>

        {/* Demo credentials */}
        {mode === "login" && (
          <div className="mt-4 bg-[#1e1533]/60 backdrop-blur-xl rounded-2xl p-5 border border-violet-500/20">
            <p className="text-violet-300 text-xs font-semibold uppercase tracking-wider mb-3">Try the demo</p>
            <div className="space-y-2">
              {[
                { label: "Product Manager", email: "demo@kairo.ai" },
                { label: "Backend Lead", email: "gaurav@kairo.ai" },
                { label: "Frontend Lead", email: "phani@kairo.ai" },
              ].map((demo) => (
                <button key={demo.email} type="button"
                  onClick={() => { setForm(p => ({ ...p, email: demo.email, password: "demo1234" })); login(demo.email, "demo1234"); }}
                  className="w-full flex items-center justify-between px-4 py-2.5 rounded-xl bg-[#2d2247]/60 border border-[#3d3257]/50 hover:border-violet-500/40 hover:bg-[#2d2247] transition-all group cursor-pointer">
                  <div className="text-left">
                    <span className="text-white text-sm font-medium">{demo.label}</span>
                    <span className="text-slate-500 text-xs ml-2">{demo.email}</span>
                  </div>
                  <ArrowRight className="w-3.5 h-3.5 text-slate-600 group-hover:text-violet-400 transition-colors" />
                </button>
              ))}
            </div>
            <p className="text-slate-600 text-[10px] mt-2.5 text-center">All demo accounts use password: demo1234</p>
          </div>
        )}
      </div>
    </main>
  );
}
