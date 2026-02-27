"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import * as d3 from "d3";
import { relationships } from "@/lib/api";
import { AlertTriangle, UserX, Star, Network } from "lucide-react";

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

// -- Component --

export default function RelationshipsPage() {
  const svgRef = useRef<SVGSVGElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const [graphData, setGraphData] = useState<{ nodes: GraphNode[]; links: GraphLink[] } | null>(null);
  const [toneShifts, setToneShifts] = useState<any[]>([]);
  const [neglected, setNeglected] = useState<any[]>([]);
  const [keyContacts, setKeyContacts] = useState<any[]>([]);
  const [clusters, setClusters] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [sideTab, setSideTab] = useState<"tone" | "neglected" | "key" | "clusters">("tone");

  useEffect(() => {
    Promise.all([
      relationships.graph().catch(() => ({ nodes: [], links: [] })),
      relationships.toneShifts().catch(() => []),
      relationships.neglected().catch(() => []),
      relationships.keyContacts().catch(() => []),
      relationships.clusters().catch(() => []),
    ]).then(([g, ts, neg, kc, cl]) => {
      const graph = g as any;
      setGraphData({
        nodes: graph.nodes || [],
        links: graph.links || graph.edges || [],
      });
      setToneShifts(Array.isArray(ts) ? ts : ts?.shifts || []);
      setNeglected(Array.isArray(neg) ? neg : neg?.contacts || []);
      setKeyContacts(Array.isArray(kc) ? kc : kc?.contacts || []);
      setClusters(Array.isArray(cl) ? cl : cl?.clusters || []);
      setLoading(false);
    });
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
      .attr("cursor", "grab")
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
             </div>`
          );
      })
      .on("mousemove", (event) => {
        tooltip
          .style("left", event.pageX + 14 + "px")
          .style("top", event.pageY - 14 + "px");
      })
      .on("mouseout", () => {
        tooltip.style("opacity", "0");
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
    });

    return () => simulation.stop();
  }, [graphData]);

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
            <svg ref={svgRef} className="w-full h-full" style={{ background: "#ffffff" }} />
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
          {/* Tabs */}
          <div className="flex gap-1 mb-4 bg-slate-50 dark:bg-[#2d2247]/40 rounded-lg p-1">
            {([
              { key: "tone", icon: AlertTriangle, label: "Tone" },
              { key: "neglected", icon: UserX, label: "Neglected" },
              { key: "key", icon: Star, label: "Key" },
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
            {sideTab === "tone" && (
              <>
                <p className="text-[10px] text-slate-400 uppercase tracking-wider mb-2">Tone Shift Alerts</p>
                {toneShifts.length === 0 ? (
                  <p className="text-slate-400 text-xs">No tone shifts detected.</p>
                ) : (
                  toneShifts.map((t: any, i: number) => (
                    <div key={i} className="p-3 rounded-lg bg-slate-50 dark:bg-[#2d2247]/40 border border-slate-200 dark:border-[#2d2247]">
                      <p className="text-xs text-slate-900 dark:text-white font-medium">{t.contact_name || t.name}</p>
                      <p className="text-[10px] text-slate-400 mt-1">
                        {t.from_tone || t.previous} &rarr; {t.to_tone || t.current}
                      </p>
                      {t.suggestion && <p className="text-[10px] text-violet-600 dark:text-violet-400 mt-1">{t.suggestion}</p>}
                    </div>
                  ))
                )}
              </>
            )}

            {sideTab === "neglected" && (
              <>
                <p className="text-[10px] text-slate-400 uppercase tracking-wider mb-2">Neglected Contacts</p>
                {neglected.length === 0 ? (
                  <p className="text-slate-400 text-xs">All contacts are up to date.</p>
                ) : (
                  neglected.map((c: any, i: number) => (
                    <div key={i} className="p-3 rounded-lg bg-slate-50 dark:bg-[#2d2247]/40 border border-slate-200 dark:border-[#2d2247]">
                      <p className="text-xs text-slate-900 dark:text-white font-medium">{c.name || c.contact_name}</p>
                      <p className="text-[10px] text-slate-400 mt-1">
                        Last contact: {c.last_contact || c.days_since || "Unknown"}
                      </p>
                      <p className="text-[10px] text-red-500 dark:text-red-400 mt-0.5">{c.urgency || c.risk || ""}</p>
                    </div>
                  ))
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
                    <div key={i} className="p-3 rounded-lg bg-slate-50 dark:bg-[#2d2247]/40 border border-slate-200 dark:border-[#2d2247] flex items-center gap-3">
                      <div
                        className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold text-slate-900 dark:text-white flex-shrink-0"
                        style={{ background: TYPE_COLORS[c.type] || "#9ca3af" }}
                      >
                        {(c.name || "?")[0].toUpperCase()}
                      </div>
                      <div className="min-w-0">
                        <p className="text-xs text-slate-900 dark:text-white font-medium truncate">{c.name || c.contact_name}</p>
                        <p className="text-[10px] text-slate-400 capitalize">{c.type} &middot; Importance: {((c.importance || 0) * 100).toFixed(0)}%</p>
                      </div>
                    </div>
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
        </div>
      </div>
    </div>
  );
}
