"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/store";
import { replay as api } from "@/lib/api";
import { GitCompare, Clock, Users, Zap, ChevronDown, ChevronUp } from "lucide-react";

export default function ReplayPage() {
  const { user } = useAuth();
  const [replays, setReplays] = useState<any[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    api.list().then(setReplays).catch(() => {});
  }, [user]);

  if (!user) return null;

  return (
    <div className="p-8 max-w-5xl">
      <div className="mb-6 pb-5 border-b border-slate-200 dark:border-[#2d2247]">
        <h1 className="font-['DM_Serif_Display'] text-2xl text-slate-900 dark:text-white">Decision Replay</h1>
        <p className="text-slate-400 text-sm mt-1">What-if analysis of your past decisions with cascade consequences</p>
      </div>

      {replays.length === 0 ? (
        <div className="kairo-card text-center py-16">
          <GitCompare className="w-10 h-10 text-slate-200 dark:text-slate-600 mx-auto mb-4" />
          <p className="text-slate-400 text-sm font-medium">No decision replays yet</p>
          <p className="text-slate-300 dark:text-slate-600 text-xs mt-1">Replays are generated automatically for significant decisions</p>
        </div>
      ) : (
        <div className="space-y-4">
          {replays.map((r: any) => {
            const isExpanded = expanded === r.id;
            const isGoodCall = (r.verdict || "").toLowerCase().includes("good") || (r.verdict || "").toLowerCase().includes("excellent");
            return (
              <div key={r.id} className="kairo-card">
                {/* Header */}
                <button onClick={() => setExpanded(isExpanded ? null : r.id)} className="w-full text-left">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-slate-900 dark:text-white mb-1">{r.original_decision}</p>
                      <div className="flex items-center gap-3 flex-wrap">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${isGoodCall ? "bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400" : "bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-400"}`}>
                          {r.verdict}
                        </span>
                        {r.time_impact_minutes !== 0 && (
                          <span className="flex items-center gap-1 text-[10px] text-slate-400">
                            <Clock className="w-3 h-3" />{r.time_impact_minutes > 0 ? "+" : ""}{Math.round(r.time_impact_minutes)}m
                          </span>
                        )}
                        <span className="text-[10px] text-slate-400">
                          Confidence: {Math.round((r.confidence || 0) * 100)}%
                        </span>
                      </div>
                    </div>
                    {isExpanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
                  </div>
                </button>

                {/* Expanded: Cascade View */}
                {isExpanded && (
                  <div className="mt-5 pt-5 border-t border-slate-100 dark:border-[#2d2247]">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      {/* Actual Path */}
                      <div>
                        <h4 className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider mb-3">Actual Path</h4>
                        <div className="space-y-2 relative">
                          <div className="absolute left-3 top-3 bottom-3 w-px bg-emerald-200 dark:bg-emerald-500/20" />
                          <div className="relative pl-8">
                            <div className="absolute left-1.5 top-1.5 w-3 h-3 rounded-full bg-emerald-500 ring-2 ring-emerald-100 dark:ring-emerald-500/20" />
                            <p className="text-xs text-slate-600 dark:text-slate-300 font-medium">{r.original_decision}</p>
                          </div>
                          <div className="relative pl-8">
                            <div className="absolute left-2 top-1.5 w-2 h-2 rounded-full bg-emerald-300" />
                            <p className="text-xs text-slate-500 dark:text-slate-400">{r.original_outcome}</p>
                          </div>
                          {r.time_impact_minutes > 0 && (
                            <div className="relative pl-8">
                              <div className="absolute left-2 top-1.5 w-2 h-2 rounded-full bg-emerald-200" />
                              <p className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">Net: +{Math.round(r.time_impact_minutes)} min saved</p>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Counterfactual Path */}
                      <div>
                        <h4 className="text-xs font-semibold text-amber-600 dark:text-amber-400 uppercase tracking-wider mb-3">What If: {r.counterfactual_decision}</h4>
                        <div className="space-y-2 relative">
                          <div className="absolute left-3 top-3 bottom-3 w-px bg-amber-200 dark:bg-amber-500/20" />
                          {(r.counterfactual_cascade || []).map((step: any, i: number) => (
                            <div key={i} className="relative pl-8">
                              <div className={`absolute left-2 top-1.5 w-2 h-2 rounded-full ${i === 0 ? "bg-amber-500 w-3 h-3 left-1.5 ring-2 ring-amber-100 dark:ring-amber-500/20" : "bg-amber-300"}`} />
                              <p className="text-xs text-slate-500 dark:text-slate-400">{step.consequence}</p>
                              <span className="text-[9px] text-slate-300 dark:text-slate-600">{Math.round((step.confidence || 0) * 100)}% confidence</span>
                            </div>
                          ))}
                          {r.time_impact_minutes > 0 && (
                            <div className="relative pl-8">
                              <div className="absolute left-2 top-1.5 w-2 h-2 rounded-full bg-amber-200" />
                              <p className="text-xs text-red-500 font-medium">Net: -{Math.round(r.time_impact_minutes)} min lost</p>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Impact Summary */}
                    <div className="mt-5 pt-4 border-t border-slate-100 dark:border-[#2d2247] flex items-center gap-4 flex-wrap">
                      {Object.entries(r.relationship_impact || {}).map(([contact, delta]: [string, any]) => (
                        <span key={contact} className="flex items-center gap-1 text-[10px] text-slate-400">
                          <Users className="w-3 h-3" />{contact}: {delta > 0 ? "+" : ""}{delta}
                        </span>
                      ))}
                      <span className="flex items-center gap-1 text-[10px] text-slate-400">
                        <Zap className="w-3 h-3" />Productivity: {r.productivity_impact > 0 ? "+" : ""}{r.productivity_impact}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
