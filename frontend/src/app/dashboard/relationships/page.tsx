"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import * as d3 from "d3";
import { relationships, commitments } from "@/lib/api";
import { AlertTriangle, Star, Network, ArrowLeft, Shield, ShieldCheck, Clock, MessageSquare, Hash, ChevronRight } from "lucide-react";

// -- Types --

interface GraphNode extends d3.SimulationNodeDatum {
  id: string;
  name: string;
  type: string;
  importance: number;
  sentiment: number;
  preferred_channel?: string;
}

interface GraphLink extends d3.SimulationLinkDatum<GraphNode> {
  sentiment: number;
  interaction_count: number;
  avg_response_time?: number;
  last_interaction?: string;
}

// -- Color maps --

const TYPE_COLORS: Record<string, string> = {
  colleague: "#4A90D9",
  manager: "#E74C3C",
  client: "#2ECC71",
  investor: "#F39C12",
  friend: "#9B59B6",
  family: "#E67E22",
};

function sentimentColor(s: number) {
  if (s < -0.2) return "#ef4444";
  if (s > 0.2) return "#22c55e";
  return "#9ca3af";
}

function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "Never";
  const diff = Date.now() - new Date(iso).getTime();
  const days = Math.floor(diff / 86400000);
  if (days < 1) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 30) return `${days}d ago`;
  return `${Math.floor(days / 30)}mo ago`;
}

const STATUS_COLORS: Record<string, string> = {
  active: "bg-blue-500/20 text-blue-400",
  overdue: "bg-red-500/20 text-red-400",
  fulfilled: "bg-green-500/20 text-green-400",
  broken: "bg-red-500/20 text-red-400",
  cancelled: "bg-slate-500/20 text-slate-400",
};

const ATTENTION_COLORS: Record<string, { bg: string; text: string; dot: string }> = {
  overdue_commitment: { bg: "bg-red-500/10", text: "text-red-400", dot: "bg-red-500" },
  neglected_contact: { bg: "bg-orange-500/10", text: "text-orange-400", dot: "bg-orange-500" },
  tone_decline: { bg: "bg-yellow-500/10", text: "text-yellow-400", dot: "bg-yellow-500" },
};

// -- Star rating component --

function StarRating({ value, onChange }: { value: number; onChange?: (v: number) => void }) {
  const stars = Math.round(value * 5);
  return (
    <div className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map((i) => (
        <button
          key={i}
          onClick={() => onChange?.(i / 5)}
          disabled={!onChange}
          className={`text-sm transition-colors ${
            i <= stars ? "text-[#d78232]" : "text-slate-300 dark:text-slate-600"
          } ${onChange ? "hover:text-[#d78232] cursor-pointer" : "cursor-default"}`}
        >
          ★
        </button>
      ))}
    </div>
  );
}

// -- Component --

export default function RelationshipsPage() {
  const svgRef = useRef<SVGSVGElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const [graphData, setGraphData] = useState<{ nodes: GraphNode[]; links: GraphLink[] } | null>(null);
  const [attentionItems, setAttentionItems] = useState<any[]>([]);
  const [keyContacts, setKeyContacts] = useState<any[]>([]);
  const [allCommitments, setAllCommitments] = useState<any[]>([]);
  const [clusters, setClusters] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [sideTab, setSideTab] = useState<"attention" | "key" | "promises" | "clusters">("attention");

  // Contact detail state
  const [selectedContact, setSelectedContact] = useState<string | null>(null);
  const [contactDetail, setContactDetail] = useState<any | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Track selected node for highlight ring
  const selectedNodeRef = useRef<string | null>(null);

  useEffect(() => {
    Promise.all([
      relationships.graph().catch(() => ({ nodes: [], links: [] })),
      relationships.attention().catch(() => []),
      relationships.keyContacts().catch(() => []),
      relationships.clusters().catch(() => []),
      commitments.list({ status: "all" }).catch(() => []),
    ]).then(([g, att, kc, cl, cm]) => {
      const graph = g as any;
      setGraphData({
        nodes: graph.nodes || [],
        links: graph.links || graph.edges || [],
      });
      setAttentionItems(Array.isArray(att) ? att : []);
      setKeyContacts(Array.isArray(kc) ? kc : kc?.contacts || []);
      setClusters(Array.isArray(cl) ? cl : cl?.clusters || []);
      setAllCommitments(Array.isArray(cm) ? cm : []);
      setLoading(false);
    });
  }, []);

  // Fetch contact detail when selected
  const selectContact = useCallback(async (contactId: string) => {
    setSelectedContact(contactId);
    selectedNodeRef.current = contactId;
    setDetailLoading(true);
    try {
      const detail = await relationships.contactDetail(contactId);
      setContactDetail(detail);
    } catch {
      setContactDetail(null);
    }
    setDetailLoading(false);
  }, []);

  const clearSelection = useCallback(() => {
    setSelectedContact(null);
    selectedNodeRef.current = null;
    setContactDetail(null);
    // Remove highlight from all nodes
    if (svgRef.current) {
      d3.select(svgRef.current).selectAll(".node-highlight-ring").remove();
    }
  }, []);

  const handleImportanceChange = useCallback(async (contactId: string, newScore: number) => {
    try {
      await relationships.updateContact(contactId, { importance_score: newScore });
      // Update local graph data for node size
      setGraphData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          nodes: prev.nodes.map((n) => (n.id === contactId ? { ...n, importance: newScore } : n)),
        };
      });
      // Update contact detail
      setContactDetail((prev: any) => prev ? { ...prev, node: { ...prev.node, importance_score: newScore } } : prev);
      // Update key contacts list
      setKeyContacts((prev) => prev.map((c) => (c.contact_id === contactId ? { ...c, importance: newScore } : c)));
    } catch { /* silent */ }
  }, []);

  const handleVipToggle = useCallback(async (contactId: string, isVip: boolean) => {
    try {
      await relationships.updateContact(contactId, { is_vip: isVip });
      setContactDetail((prev: any) => prev ? { ...prev, is_vip: isVip } : prev);
    } catch { /* silent */ }
  }, []);

  // -- D3 Force Graph --

  const renderGraph = useCallback(() => {
    if (!svgRef.current || !graphData) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const width = svgRef.current.clientWidth;
    const height = svgRef.current.clientHeight;

    const g = svg.append("g");

    // Zoom
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.3, 4])
      .on("zoom", (event) => g.attr("transform", event.transform));
    svg.call(zoom);

    // Tooltip
    const tooltip = d3.select(tooltipRef.current);

    // Use copies so d3 doesn't mutate original state
    const nodes: GraphNode[] = graphData.nodes.map((n) => ({ ...n }));
    const links: GraphLink[] = graphData.links.map((l) => ({ ...l }));

    const simulation = d3
      .forceSimulation(nodes)
      .force(
        "link",
        d3.forceLink<GraphNode, GraphLink>(links).id((d) => d.id).distance(120)
      )
      .force("charge", d3.forceManyBody().strength(-300))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide().radius((d: any) => 12 + (d.importance || 0.5) * 20));

    // Links
    const link = g
      .append("g")
      .selectAll("line")
      .data(links)
      .join("line")
      .attr("stroke", (d) => sentimentColor(d.sentiment || 0))
      .attr("stroke-width", (d) => Math.max(1, Math.min(6, (d.interaction_count || 1) / 5)))
      .attr("stroke-opacity", 0.5);

    // Highlight rings (rendered behind nodes)
    const highlightGroup = g.append("g").attr("class", "highlight-group");

    // Nodes
    const node = g
      .append("g")
      .selectAll("circle")
      .data(nodes)
      .join("circle")
      .attr("r", (d) => 8 + (d.importance || 0.5) * 16)
      .attr("fill", (d) => TYPE_COLORS[d.type] || "#9ca3af")
      .attr("stroke", "#ffffff")
      .attr("stroke-width", 2)
      .attr("cursor", "pointer")
      .on("mouseover", (_event, d) => {
        tooltip
          .style("opacity", "1")
          .html(
            `<div class="font-medium text-slate-900 dark:text-white">${d.name}</div>
             <div class="text-[11px] text-slate-500 dark:text-slate-400 mt-1">
               Type: <span style="color:${TYPE_COLORS[d.type] || "#9ca3af"}">${d.type}</span><br/>
               Importance: ${((d.importance || 0) * 100).toFixed(0)}%<br/>
               Sentiment: ${(d.sentiment || 0).toFixed(2)}<br/>
               ${d.preferred_channel ? `Channel: ${d.preferred_channel}` : ""}
             </div>
             <div class="text-[10px] text-slate-400 mt-1">Click for details</div>`
          );
      })
      .on("mousemove", (event) => {
        tooltip
          .style("left", event.pageX + 14 + "px")
          .style("top", event.pageY - 14 + "px");
      })
      .on("mouseout", () => {
        tooltip.style("opacity", "0");
      })
      .on("click", (_event, d) => {
        if (d.type === "self") return;
        tooltip.style("opacity", "0");

        // Update highlight ring
        highlightGroup.selectAll("*").remove();
        const matchNode = nodes.find((n) => n.id === d.id);
        if (matchNode) {
          highlightGroup.append("circle")
            .attr("class", "node-highlight-ring")
            .attr("cx", matchNode.x || 0)
            .attr("cy", matchNode.y || 0)
            .attr("r", 8 + (d.importance || 0.5) * 16 + 5)
            .attr("fill", "none")
            .attr("stroke", "#d78232")
            .attr("stroke-width", 3)
            .attr("stroke-dasharray", "4,2")
            .attr("opacity", 0.9);
        }

        selectContact(d.id);
      });

    // Labels
    const label = g
      .append("g")
      .selectAll("text")
      .data(nodes)
      .join("text")
      .text((d) => d.name)
      .attr("font-size", 11)
      .attr("fill", "#6b7280")
      .attr("text-anchor", "middle")
      .attr("dy", (d) => -(12 + (d.importance || 0.5) * 16) - 4)
      .attr("pointer-events", "none");

    // Drag
    const drag = d3
      .drag<SVGCircleElement, GraphNode>()
      .on("start", (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
      })
      .on("drag", (event, d) => {
        d.fx = event.x;
        d.fy = event.y;
      })
      .on("end", (event, d) => {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
      });
    node.call(drag as any);

    simulation.on("tick", () => {
      link
        .attr("x1", (d: any) => d.source.x)
        .attr("y1", (d: any) => d.source.y)
        .attr("x2", (d: any) => d.target.x)
        .attr("y2", (d: any) => d.target.y);
      node.attr("cx", (d) => d.x!).attr("cy", (d) => d.y!);
      label.attr("x", (d) => d.x!).attr("y", (d) => d.y!);

      // Update highlight ring position
      const sel = selectedNodeRef.current;
      if (sel) {
        const sn = nodes.find((n) => n.id === sel);
        if (sn) {
          highlightGroup.select(".node-highlight-ring")
            .attr("cx", sn.x || 0)
            .attr("cy", sn.y || 0);
        }
      }
    });

    return () => simulation.stop();
  }, [graphData, selectContact]);

  useEffect(() => {
    const cleanup = renderGraph();
    const handleResize = () => renderGraph();
    window.addEventListener("resize", handleResize);
    return () => {
      cleanup?.();
      window.removeEventListener("resize", handleResize);
    };
  }, [renderGraph]);

  // Demo data for empty state
  const hasGraphData = graphData && graphData.nodes.length > 0;

  // Active/overdue commitments for Promises tab
  const activeCommitments = allCommitments.filter(
    (c: any) => c.status === "active" || c.status === "overdue"
  );

  return (
    <div className="p-8 max-w-full h-[calc(100vh)]">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-['DM_Serif_Display'] text-2xl text-slate-900 dark:text-white">Relationship Graph</h1>
          <p className="text-slate-400 text-sm mt-0.5">Visualize and manage your network connections.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 h-[calc(100vh-140px)]">
        {/* -- Graph area -- */}
        <div className="lg:col-span-3 kairo-card relative overflow-hidden p-0">
          {loading ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-slate-400 text-sm">Loading relationship graph...</div>
            </div>
          ) : !hasGraphData ? (
            <div className="flex flex-col items-center justify-center h-full gap-3">
              <Network className="w-12 h-12 text-slate-200 dark:text-slate-600" />
              <p className="text-slate-400 text-sm">No relationship data yet.</p>
              <p className="text-slate-300 dark:text-slate-600 text-xs">Your agent will build a relationship graph as it processes your communications.</p>
            </div>
          ) : (
            <svg ref={svgRef} className="w-full h-full bg-white dark:bg-[#1e1533]" />
          )}

          {/* Tooltip */}
          <div
            ref={tooltipRef}
            className="fixed z-50 bg-slate-100 dark:bg-[#2d2247] border border-slate-200 dark:border-[#2d2247] rounded-xl px-4 py-3 pointer-events-none shadow-xl max-w-xs"
            style={{ opacity: 0, transition: "opacity 0.15s" }}
          />

          {/* Legend */}
          {hasGraphData && (
            <div className="absolute bottom-4 left-4 bg-white/90 dark:bg-[#1e1533]/90 backdrop-blur border border-slate-200 dark:border-[#2d2247] rounded-xl p-3">
              <p className="text-[10px] text-slate-400 uppercase tracking-wider mb-2">Relationship Types</p>
              <div className="grid grid-cols-3 gap-x-4 gap-y-1.5">
                {Object.entries(TYPE_COLORS).map(([type, color]) => (
                  <div key={type} className="flex items-center gap-1.5">
                    <div className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
                    <span className="text-[10px] text-slate-500 dark:text-slate-400 capitalize">{type}</span>
                  </div>
                ))}
              </div>
              <div className="border-t border-slate-200 dark:border-[#2d2247] mt-2 pt-2">
                <p className="text-[10px] text-slate-400 uppercase tracking-wider mb-1.5">Edge Sentiment</p>
                <div className="flex gap-3">
                  <div className="flex items-center gap-1"><div className="w-4 h-0.5 bg-red-500 rounded" /><span className="text-[10px] text-slate-500 dark:text-slate-400">Negative</span></div>
                  <div className="flex items-center gap-1"><div className="w-4 h-0.5 bg-gray-400 rounded" /><span className="text-[10px] text-slate-500 dark:text-slate-400">Neutral</span></div>
                  <div className="flex items-center gap-1"><div className="w-4 h-0.5 bg-green-500 rounded" /><span className="text-[10px] text-slate-500 dark:text-slate-400">Positive</span></div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* -- Side panel -- */}
        <div className="lg:col-span-1 kairo-card flex flex-col overflow-hidden">
          {selectedContact && contactDetail ? (
            /* ── Contact Detail Panel ── */
            <div className="flex flex-col h-full">
              <button
                onClick={clearSelection}
                className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 mb-3 transition-colors"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                Back to tabs
              </button>

              {detailLoading ? (
                <div className="flex items-center justify-center flex-1">
                  <div className="text-slate-400 text-xs">Loading...</div>
                </div>
              ) : (
                <div className="flex-1 overflow-y-auto space-y-4">
                  {/* Name + Type + VIP */}
                  <div>
                    <div className="flex items-center gap-2">
                      <div
                        className="w-9 h-9 rounded-lg flex items-center justify-center text-sm font-bold text-white flex-shrink-0"
                        style={{ background: TYPE_COLORS[contactDetail.node?.relationship_type] || "#9ca3af" }}
                      >
                        {(contactDetail.node?.name || selectedContact)[0]?.toUpperCase()}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm text-slate-900 dark:text-white font-medium truncate">
                          {contactDetail.node?.name || selectedContact}
                        </p>
                        <p className="text-[10px] text-slate-400 capitalize">
                          {contactDetail.node?.relationship_type || "contact"}
                        </p>
                      </div>
                      <button
                        onClick={() => handleVipToggle(selectedContact, !contactDetail.is_vip)}
                        className={`p-1.5 rounded-lg transition-colors ${
                          contactDetail.is_vip
                            ? "bg-[#d78232]/20 text-[#d78232]"
                            : "bg-slate-100 dark:bg-[#2d2247]/40 text-slate-400 hover:text-[#d78232]"
                        }`}
                        title={contactDetail.is_vip ? "Remove VIP" : "Add VIP"}
                      >
                        {contactDetail.is_vip ? <ShieldCheck className="w-4 h-4" /> : <Shield className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>

                  {/* Star Rating */}
                  <div>
                    <p className="text-[10px] text-slate-400 uppercase tracking-wider mb-1.5">Importance</p>
                    <StarRating
                      value={contactDetail.node?.importance_score ?? 0.5}
                      onChange={(v) => {
                        handleImportanceChange(selectedContact, v);
                        // If 5 stars and not VIP, prompt
                        if (v === 1.0 && !contactDetail.is_vip) {
                          handleVipToggle(selectedContact, true);
                        }
                      }}
                    />
                  </div>

                  {/* Communication Health */}
                  <div>
                    <p className="text-[10px] text-slate-400 uppercase tracking-wider mb-2">Communication Health</p>
                    <div className="space-y-2">
                      <div className="flex items-center gap-2 text-xs">
                        <Clock className="w-3.5 h-3.5 text-slate-400" />
                        <span className="text-slate-500 dark:text-slate-400">Last interaction:</span>
                        <span className="text-slate-900 dark:text-white font-medium">
                          {relativeTime(contactDetail.edge?.last_interaction)}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 text-xs">
                        <MessageSquare className="w-3.5 h-3.5 text-slate-400" />
                        <span className="text-slate-500 dark:text-slate-400">Avg response:</span>
                        <span className="text-slate-900 dark:text-white font-medium">
                          {contactDetail.edge?.avg_response_time
                            ? `${Math.round(contactDetail.edge.avg_response_time)}min`
                            : "N/A"}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 text-xs">
                        <Hash className="w-3.5 h-3.5 text-slate-400" />
                        <span className="text-slate-500 dark:text-slate-400">Interactions:</span>
                        <span className="text-slate-900 dark:text-white font-medium">
                          {contactDetail.edge?.interaction_count ?? 0}
                        </span>
                      </div>
                      {/* Sentiment dots */}
                      {contactDetail.edge?.sentiment_scores?.length > 0 && (
                        <div className="flex items-center gap-2 text-xs">
                          <span className="text-slate-500 dark:text-slate-400">Sentiment:</span>
                          <div className="flex gap-1">
                            {contactDetail.edge.sentiment_scores.map((s: number, i: number) => (
                              <div
                                key={i}
                                className="w-2.5 h-2.5 rounded-full"
                                style={{ background: sentimentColor(s) }}
                                title={`${s.toFixed(2)}`}
                              />
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Promises */}
                  <div>
                    <p className="text-[10px] text-slate-400 uppercase tracking-wider mb-2">Promises</p>
                    {(!contactDetail.commitments || contactDetail.commitments.length === 0) ? (
                      <p className="text-slate-400 text-[11px]">No commitments tracked.</p>
                    ) : (
                      <div className="space-y-1.5">
                        {contactDetail.commitments.map((c: any) => (
                          <div
                            key={c.id}
                            className="p-2 rounded-lg bg-slate-50 dark:bg-[#2d2247]/40 border border-slate-200 dark:border-[#2d2247]"
                          >
                            <div className="flex items-start justify-between gap-2">
                              <p className="text-[11px] text-slate-900 dark:text-white leading-snug">
                                {c.parsed_commitment || c.raw_text}
                              </p>
                              <span className={`text-[9px] px-1.5 py-0.5 rounded-full whitespace-nowrap ${STATUS_COLORS[c.status] || "bg-slate-500/20 text-slate-400"}`}>
                                {c.status}
                              </span>
                            </div>
                            {c.deadline && (
                              <p className="text-[10px] text-slate-400 mt-1">
                                Due: {new Date(c.deadline).toLocaleDateString()}
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          ) : (
            /* ── Sidebar Tabs ── */
            <>
              <div className="flex gap-1 mb-4 bg-slate-50 dark:bg-[#2d2247]/40 rounded-lg p-1">
                {([
                  { key: "attention", icon: AlertTriangle, label: "Attention" },
                  { key: "key", icon: Star, label: "Key" },
                  { key: "promises", icon: Clock, label: "Promises" },
                  { key: "clusters", icon: Network, label: "Clusters" },
                ] as const).map(({ key, icon: Icon, label }) => (
                  <button
                    key={key}
                    onClick={() => setSideTab(key)}
                    className={`flex-1 flex items-center justify-center gap-1 py-1.5 rounded-md text-[10px] font-medium transition-colors ${
                      sideTab === key
                        ? "bg-slate-100 dark:bg-[#2d2247] text-slate-900 dark:text-white"
                        : "text-slate-400 hover:text-slate-500 dark:hover:text-slate-300"
                    }`}
                  >
                    <Icon className="w-3 h-3" />
                    {label}
                  </button>
                ))}
              </div>

              {/* Content */}
              <div className="flex-1 overflow-y-auto space-y-2">
                {sideTab === "attention" && (
                  <>
                    <p className="text-[10px] text-slate-400 uppercase tracking-wider mb-2">Needs Attention</p>
                    {attentionItems.length === 0 ? (
                      <p className="text-slate-400 text-xs">Everything looks good — no items need attention.</p>
                    ) : (
                      attentionItems.map((item: any, i: number) => {
                        const colors = ATTENTION_COLORS[item.type] || ATTENTION_COLORS.tone_decline;
                        return (
                          <button
                            key={i}
                            onClick={() => item.contact_id && selectContact(item.contact_id)}
                            className={`w-full text-left p-3 rounded-lg ${colors.bg} border border-slate-200 dark:border-[#2d2247] hover:opacity-80 transition-opacity`}
                          >
                            <div className="flex items-start gap-2">
                              <div className={`w-2 h-2 rounded-full mt-1 flex-shrink-0 ${colors.dot}`} />
                              <div className="min-w-0">
                                <p className="text-xs text-slate-900 dark:text-white font-medium truncate">
                                  {item.contact_name}
                                </p>
                                <p className={`text-[10px] mt-0.5 ${colors.text}`}>
                                  {item.message}
                                </p>
                                {item.deadline && (
                                  <p className="text-[10px] text-slate-400 mt-0.5">
                                    Due: {new Date(item.deadline).toLocaleDateString()}
                                  </p>
                                )}
                              </div>
                              <ChevronRight className="w-3 h-3 text-slate-400 flex-shrink-0 mt-0.5" />
                            </div>
                          </button>
                        );
                      })
                    )}
                  </>
                )}

                {sideTab === "key" && (
                  <>
                    <p className="text-[10px] text-slate-400 uppercase tracking-wider mb-2">Key Contacts</p>
                    {keyContacts.length === 0 ? (
                      <p className="text-slate-400 text-xs">No key contacts identified yet.</p>
                    ) : (
                      keyContacts.map((c: any, i: number) => (
                        <div
                          key={i}
                          className="p-3 rounded-lg bg-slate-50 dark:bg-[#2d2247]/40 border border-slate-200 dark:border-[#2d2247]"
                        >
                          <div className="flex items-center gap-3">
                            <button
                              onClick={() => c.contact_id && selectContact(c.contact_id)}
                              className="flex items-center gap-3 min-w-0 flex-1 text-left"
                            >
                              <div
                                className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold text-white flex-shrink-0"
                                style={{ background: TYPE_COLORS[c.type] || "#9ca3af" }}
                              >
                                {(c.name || "?")[0].toUpperCase()}
                              </div>
                              <div className="min-w-0">
                                <p className="text-xs text-slate-900 dark:text-white font-medium truncate">{c.name || c.contact_name}</p>
                                <p className="text-[10px] text-slate-400 capitalize">{c.type}</p>
                              </div>
                            </button>
                            <StarRating
                              value={c.importance || 0}
                              onChange={(v) => c.contact_id && handleImportanceChange(c.contact_id, v)}
                            />
                          </div>
                        </div>
                      ))
                    )}
                  </>
                )}

                {sideTab === "promises" && (
                  <>
                    <p className="text-[10px] text-slate-400 uppercase tracking-wider mb-2">Active Promises</p>
                    {activeCommitments.length === 0 ? (
                      <p className="text-slate-400 text-xs">No active commitments.</p>
                    ) : (
                      activeCommitments.map((c: any) => (
                        <button
                          key={c.id}
                          onClick={() => c.target_contact && selectContact(c.target_contact)}
                          className="w-full text-left p-3 rounded-lg bg-slate-50 dark:bg-[#2d2247]/40 border border-slate-200 dark:border-[#2d2247] hover:opacity-80 transition-opacity"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="min-w-0">
                              <p className="text-[11px] text-slate-900 dark:text-white leading-snug">
                                {c.parsed_commitment || c.raw_text}
                              </p>
                              <p className="text-[10px] text-slate-400 mt-1">
                                {c.target_contact && `To: ${c.target_contact}`}
                                {c.deadline && ` · Due: ${new Date(c.deadline).toLocaleDateString()}`}
                              </p>
                            </div>
                            <span className={`text-[9px] px-1.5 py-0.5 rounded-full whitespace-nowrap flex-shrink-0 ${STATUS_COLORS[c.status] || "bg-slate-500/20 text-slate-400"}`}>
                              {c.status}
                            </span>
                          </div>
                        </button>
                      ))
                    )}
                  </>
                )}

                {sideTab === "clusters" && (
                  <>
                    <p className="text-[10px] text-slate-400 uppercase tracking-wider mb-2">Communication Clusters</p>
                    {clusters.length === 0 ? (
                      <p className="text-slate-400 text-xs">No clusters detected yet.</p>
                    ) : (
                      clusters.map((cl: any, i: number) => (
                        <div key={i} className="p-3 rounded-lg bg-slate-50 dark:bg-[#2d2247]/40 border border-slate-200 dark:border-[#2d2247]">
                          <p className="text-xs text-slate-900 dark:text-white font-medium">{cl.name || cl.label || `Cluster ${i + 1}`}</p>
                          <p className="text-[10px] text-slate-400 mt-1">
                            {cl.members?.length || cl.count || 0} members
                          </p>
                          {cl.members && (
                            <div className="flex flex-wrap gap-1 mt-1.5">
                              {cl.members.slice(0, 5).map((m: string, j: number) => (
                                <span key={j} className="badge-info text-[9px]">{m}</span>
                              ))}
                              {cl.members.length > 5 && (
                                <span className="badge-neutral text-[9px]">+{cl.members.length - 5}</span>
                              )}
                            </div>
                          )}
                        </div>
                      ))
                    )}
                  </>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
