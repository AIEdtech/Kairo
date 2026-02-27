"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/store";
import { marketplace, agents as agentsApi } from "@/lib/api";
import {
  Store, Search, Star, ShoppingCart, Plus, DollarSign, TrendingUp, Package,
  Pause, Play, Tag, Filter, ArrowUpDown, MessageSquare, Send
} from "lucide-react";

const CATEGORIES = [
  { value: "", label: "All Categories" },
  { value: "communication", label: "Communication" },
  { value: "scheduling", label: "Scheduling" },
  { value: "relationship_intel", label: "Relationship Intel" },
  { value: "ghost_mode", label: "Ghost Mode" },
  { value: "cross_context", label: "Cross-Context" },
  { value: "mesh_coordination", label: "Mesh Coordination" },
  { value: "commitment_tracking", label: "Commitment & Accountability" },
  { value: "delegation", label: "Smart Delegation" },
  { value: "wellness", label: "Wellness & Burnout" },
  { value: "analytics", label: "Decision Analytics" },
  { value: "focus", label: "Focus & Flow" },
  { value: "bundle", label: "Bundles" },
];

const SORT_OPTIONS = [
  { value: "newest", label: "Newest" },
  { value: "popular", label: "Most Popular" },
  { value: "top_rated", label: "Top Rated" },
  { value: "price_low", label: "Price: Low to High" },
  { value: "price_high", label: "Price: High to Low" },
];

function StarRating({ rating, size = "sm" }: { rating: number; size?: string }) {
  const cls = size === "sm" ? "w-3 h-3" : "w-4 h-4";
  return (
    <div className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((s) => (
        <Star
          key={s}
          className={`${cls} ${s <= Math.round(rating) ? "text-amber-400 fill-amber-400" : "text-slate-300 dark:text-slate-600"}`}
        />
      ))}
    </div>
  );
}

function ClickableStarRating({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return (
    <div className="flex items-center gap-1">
      {[1, 2, 3, 4, 5].map((s) => (
        <button key={s} onClick={() => onChange(s)} type="button" className="focus:outline-none">
          <Star className={`w-5 h-5 transition-colors ${s <= value ? "text-amber-400 fill-amber-400" : "text-slate-300 dark:text-slate-600 hover:text-amber-300"}`} />
        </button>
      ))}
    </div>
  );
}

export default function MarketplacePage() {
  const { user } = useAuth();
  const [tab, setTab] = useState<"browse" | "my-listings" | "my-purchases">("browse");

  // Browse state
  const [listings, setListings] = useState<any[]>([]);
  const [category, setCategory] = useState("");
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("newest");
  const [loadingBrowse, setLoadingBrowse] = useState(false);

  // Purchase modal state
  const [purchaseTarget, setPurchaseTarget] = useState<any>(null);
  const [taskDesc, setTaskDesc] = useState("");
  const [purchasing, setPurchasing] = useState(false);
  const [purchaseResult, setPurchaseResult] = useState<any>(null);

  // My listings state
  const [myListings, setMyListings] = useState<any[]>([]);
  const [sellerStats, setSellerStats] = useState<any>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [myAgents, setMyAgents] = useState<any[]>([]);

  // Create form state
  const [newListing, setNewListing] = useState({
    agent_id: "", title: "", description: "", category: "communication",
    capability_type: "task", price_per_use: 1.0, tags: "",
  });
  const [creating, setCreating] = useState(false);

  // My purchases state
  const [purchases, setPurchases] = useState<any[]>([]);

  // Review state
  const [reviewTarget, setReviewTarget] = useState<string | null>(null);
  const [reviewRating, setReviewRating] = useState(5);
  const [reviewText, setReviewText] = useState("");
  const [submittingReview, setSubmittingReview] = useState(false);

  const loadBrowse = () => {
    setLoadingBrowse(true);
    marketplace.browse({ category: category || undefined, search: search || undefined, sort_by: sortBy })
      .then(setListings)
      .catch(() => {})
      .finally(() => setLoadingBrowse(false));
  };

  useEffect(() => {
    if (!user) return;
    loadBrowse();
  }, [user, category, sortBy]);

  useEffect(() => {
    if (!user || tab !== "my-listings") return;
    marketplace.myListings().then(setMyListings).catch(() => {});
    marketplace.sellerDashboard().then(setSellerStats).catch(() => {});
    agentsApi.list().then(setMyAgents).catch(() => {});
  }, [user, tab]);

  useEffect(() => {
    if (!user || tab !== "my-purchases") return;
    marketplace.myPurchases().then(setPurchases).catch(() => {});
  }, [user, tab]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    loadBrowse();
  };

  const handlePurchase = async () => {
    if (!purchaseTarget) return;
    setPurchasing(true);
    try {
      const result = await marketplace.purchase({ listing_id: purchaseTarget.id, task_description: taskDesc });
      setPurchaseResult(result);
      loadBrowse();
    } catch (err: any) {
      setPurchaseResult({ error: err.message });
    } finally {
      setPurchasing(false);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      await marketplace.createListing({
        ...newListing,
        tags: newListing.tags.split(",").map((t) => t.trim()).filter(Boolean),
      });
      setShowCreateForm(false);
      setNewListing({ agent_id: "", title: "", description: "", category: "communication", capability_type: "task", price_per_use: 1.0, tags: "" });
      marketplace.myListings().then(setMyListings).catch(() => {});
      marketplace.sellerDashboard().then(setSellerStats).catch(() => {});
    } catch (err: any) {
      alert(err.message);
    } finally {
      setCreating(false);
    }
  };

  const toggleListingStatus = async (listing: any) => {
    try {
      if (listing.status === "active") {
        await marketplace.pauseListing(listing.id);
      } else {
        await marketplace.activateListing(listing.id);
      }
      marketplace.myListings().then(setMyListings).catch(() => {});
      marketplace.sellerDashboard().then(setSellerStats).catch(() => {});
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleReview = async (txnId: string) => {
    setSubmittingReview(true);
    try {
      await marketplace.submitReview(txnId, { rating: reviewRating, review_text: reviewText });
      setReviewTarget(null);
      setReviewRating(5);
      setReviewText("");
      marketplace.myPurchases().then(setPurchases).catch(() => {});
    } catch (err: any) {
      alert(err.message);
    } finally {
      setSubmittingReview(false);
    }
  };

  if (!user) return null;

  const tabs = [
    { id: "browse" as const, label: "Browse", icon: Search },
    { id: "my-listings" as const, label: "My Listings", icon: Package },
    { id: "my-purchases" as const, label: "My Purchases", icon: ShoppingCart },
  ];

  return (
    <div className="p-8 max-w-5xl">
      {/* Header */}
      <div className="mb-6 pb-5 border-b border-slate-200 dark:border-[#2d2247]">
        <h1 className="font-['DM_Serif_Display'] text-2xl text-slate-900 dark:text-white">Marketplace</h1>
        <p className="text-slate-400 text-sm mt-1">Buy and sell agent capabilities powered by Skyfire</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 p-1 bg-slate-100 dark:bg-[#1a1128] rounded-xl w-fit">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              tab === id
                ? "bg-white dark:bg-[#2d2247] text-slate-900 dark:text-white shadow-sm"
                : "text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
            }`}
          >
            <Icon className="w-4 h-4" />
            {label}
          </button>
        ))}
      </div>

      {/* ═══ BROWSE TAB ═══ */}
      {tab === "browse" && (
        <>
          {/* Filters */}
          <div className="flex flex-wrap gap-3 mb-6">
            <form onSubmit={handleSearch} className="flex-1 min-w-[200px]">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search capabilities..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-white dark:bg-[#1a1128] border border-slate-200 dark:border-[#2d2247] text-sm text-slate-900 dark:text-white placeholder:text-slate-400 focus:outline-none focus:border-violet-500/50"
                />
              </div>
            </form>
            <div className="relative">
              <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400 pointer-events-none" />
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="pl-9 pr-8 py-2.5 rounded-xl bg-white dark:bg-[#1a1128] border border-slate-200 dark:border-[#2d2247] text-sm text-slate-900 dark:text-white focus:outline-none focus:border-violet-500/50 appearance-none cursor-pointer"
              >
                {CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </div>
            <div className="relative">
              <ArrowUpDown className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400 pointer-events-none" />
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="pl-9 pr-8 py-2.5 rounded-xl bg-white dark:bg-[#1a1128] border border-slate-200 dark:border-[#2d2247] text-sm text-slate-900 dark:text-white focus:outline-none focus:border-violet-500/50 appearance-none cursor-pointer"
              >
                {SORT_OPTIONS.map((s) => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Listings Grid */}
          {loadingBrowse ? (
            <div className="text-center py-16 text-slate-400 text-sm">Loading listings...</div>
          ) : listings.length === 0 ? (
            <div className="text-center py-16">
              <div className="w-16 h-16 rounded-2xl bg-slate-50 dark:bg-[#2d2247]/40 border border-slate-200 dark:border-[#2d2247] flex items-center justify-center mx-auto mb-4">
                <Store className="w-7 h-7 text-slate-200 dark:text-slate-600" />
              </div>
              <p className="text-slate-400 text-sm font-medium">No listings found</p>
              <p className="text-slate-300 dark:text-slate-600 text-xs mt-1">Try adjusting your search or filters</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {listings.map((listing) => (
                <div key={listing.id} className="kairo-card hover:border-violet-500/20 dark:hover:border-violet-500/20 transition-all duration-200 group">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex-1 min-w-0">
                      <h3 className="text-sm font-medium text-slate-900 dark:text-white truncate group-hover:text-violet-600 dark:group-hover:text-violet-400 transition-colors">
                        {listing.title}
                      </h3>
                      <p className="text-[11px] text-slate-400 mt-0.5">by {listing.seller_name}</p>
                    </div>
                    <span className="ml-3 px-2.5 py-1 rounded-lg bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 text-xs font-semibold whitespace-nowrap">
                      ${listing.price_per_use.toFixed(2)}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed mb-3 line-clamp-2">
                    {listing.description}
                  </p>
                  <div className="flex items-center gap-2 mb-3 flex-wrap">
                    <span className="badge-info text-[10px]">{listing.category.replace(/_/g, " ")}</span>
                    {listing.tags?.slice(0, 2).map((tag: string) => (
                      <span key={tag} className="px-1.5 py-0.5 rounded text-[10px] bg-slate-100 dark:bg-[#2d2247]/60 text-slate-500 dark:text-slate-400">
                        {tag}
                      </span>
                    ))}
                    {listing.is_featured && <span className="badge-warning text-[10px]">Featured</span>}
                  </div>
                  <div className="flex items-center justify-between pt-3 border-t border-slate-100 dark:border-[#2d2247]">
                    <div className="flex items-center gap-3">
                      <div className="flex items-center gap-1">
                        <StarRating rating={listing.avg_rating} />
                        <span className="text-[10px] text-slate-400 ml-0.5">
                          {listing.avg_rating > 0 ? listing.avg_rating.toFixed(1) : "New"}
                        </span>
                      </div>
                      <span className="text-[10px] text-slate-400">{listing.total_purchases} uses</span>
                    </div>
                    <button
                      onClick={() => { setPurchaseTarget(listing); setTaskDesc(""); setPurchaseResult(null); }}
                      className="px-3 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-700 text-white text-xs font-medium transition-colors"
                    >
                      Use Capability
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Purchase Modal */}
          {purchaseTarget && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={() => setPurchaseTarget(null)}>
              <div className="bg-white dark:bg-[#1a1128] rounded-2xl border border-slate-200 dark:border-[#2d2247] p-6 max-w-md w-full shadow-xl" onClick={(e) => e.stopPropagation()}>
                <h3 className="text-lg font-medium text-slate-900 dark:text-white mb-1">{purchaseTarget.title}</h3>
                <p className="text-xs text-slate-400 mb-4">by {purchaseTarget.seller_name}</p>

                {!purchaseResult ? (
                  <>
                    <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">{purchaseTarget.description}</p>
                    <div className="mb-4">
                      <label className="text-xs text-slate-500 dark:text-slate-400 mb-1.5 block">Describe your task (optional)</label>
                      <textarea
                        value={taskDesc}
                        onChange={(e) => setTaskDesc(e.target.value)}
                        rows={3}
                        className="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-[#0f0a1a] border border-slate-200 dark:border-[#2d2247] text-sm text-slate-900 dark:text-white placeholder:text-slate-400 focus:outline-none focus:border-violet-500/50 resize-none"
                        placeholder="e.g., Triage my sales inbox for the past week..."
                      />
                    </div>
                    <div className="flex items-center justify-between p-3 rounded-xl bg-slate-50 dark:bg-[#0f0a1a] border border-slate-200 dark:border-[#2d2247] mb-4">
                      <span className="text-sm text-slate-500 dark:text-slate-400">Total (via Skyfire)</span>
                      <span className="text-lg font-semibold text-emerald-600 dark:text-emerald-400">${purchaseTarget.price_per_use.toFixed(2)}</span>
                    </div>
                    <div className="flex gap-3">
                      <button onClick={() => setPurchaseTarget(null)} className="flex-1 px-4 py-2.5 rounded-xl border border-slate-200 dark:border-[#2d2247] text-sm text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 transition-colors">
                        Cancel
                      </button>
                      <button onClick={handlePurchase} disabled={purchasing} className="flex-1 px-4 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-700 text-white text-sm font-medium transition-colors disabled:opacity-50">
                        {purchasing ? "Processing..." : "Confirm Purchase"}
                      </button>
                    </div>
                  </>
                ) : purchaseResult.error ? (
                  <div className="text-center py-4">
                    <p className="text-red-500 text-sm mb-4">{purchaseResult.error}</p>
                    <button onClick={() => setPurchaseTarget(null)} className="px-4 py-2 rounded-xl border border-slate-200 dark:border-[#2d2247] text-sm text-slate-500 hover:text-slate-700 transition-colors">
                      Close
                    </button>
                  </div>
                ) : (
                  <div className="text-center py-4">
                    <div className="w-12 h-12 rounded-2xl bg-emerald-50 dark:bg-emerald-500/10 flex items-center justify-center mx-auto mb-3">
                      <ShoppingCart className="w-6 h-6 text-emerald-600 dark:text-emerald-400" />
                    </div>
                    <p className="text-sm font-medium text-slate-900 dark:text-white mb-1">Purchase Complete</p>
                    <p className="text-xs text-slate-400 mb-1">Transaction: {purchaseResult.skyfire_transaction_id}</p>
                    <p className="text-xs text-slate-400 mb-4">Amount: ${purchaseResult.amount?.toFixed(2)}</p>
                    <button onClick={() => setPurchaseTarget(null)} className="px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-700 text-white text-sm font-medium transition-colors">
                      Done
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
        </>
      )}

      {/* ═══ MY LISTINGS TAB ═══ */}
      {tab === "my-listings" && (
        <>
          {/* Seller Stats */}
          <div className="grid grid-cols-3 gap-4 mb-6">
            {[
              { icon: DollarSign, color: "text-emerald-600 dark:text-emerald-400", gradient: "from-emerald-500/[0.07] to-transparent", border: "border-emerald-500/10", label: "Total Earnings", value: `$${(sellerStats?.total_earnings ?? 0).toFixed(2)}` },
              { icon: TrendingUp, color: "text-violet-600 dark:text-violet-400", gradient: "from-violet-500/[0.07] to-transparent", border: "border-violet-500/10", label: "Total Sales", value: sellerStats?.total_sales ?? 0 },
              { icon: Package, color: "text-blue-600 dark:text-blue-400", gradient: "from-blue-500/[0.07] to-transparent", border: "border-blue-500/10", label: "Active Listings", value: sellerStats?.active_listings ?? 0 },
            ].map(({ icon: Icon, color, gradient, border, label, value }) => (
              <div key={label} className={`kairo-card relative overflow-hidden !border ${border}`}>
                <div className={`absolute inset-0 bg-gradient-to-b ${gradient} pointer-events-none`} />
                <div className="relative z-10">
                  <div className="flex items-center gap-2 mb-2">
                    <Icon className={`w-4 h-4 ${color}`} />
                    <span className="text-xs text-slate-400 font-medium">{label}</span>
                  </div>
                  <p className={`stat-value ${color}`}>{value}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Create Listing Button */}
          <div className="mb-6">
            <button
              onClick={() => setShowCreateForm(!showCreateForm)}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-700 text-white text-sm font-medium transition-colors"
            >
              <Plus className="w-4 h-4" />
              {showCreateForm ? "Cancel" : "Create Listing"}
            </button>
          </div>

          {/* Create Form */}
          {showCreateForm && (
            <div className="kairo-card mb-6">
              <h2 className="section-title mb-4">New Listing</h2>
              <form onSubmit={handleCreate} className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs text-slate-500 dark:text-slate-400 mb-1.5 block">Agent</label>
                    <select
                      value={newListing.agent_id}
                      onChange={(e) => setNewListing({ ...newListing, agent_id: e.target.value })}
                      required
                      className="w-full px-3 py-2.5 rounded-xl bg-slate-50 dark:bg-[#0f0a1a] border border-slate-200 dark:border-[#2d2247] text-sm text-slate-900 dark:text-white focus:outline-none focus:border-violet-500/50"
                    >
                      <option value="">Select agent...</option>
                      {myAgents.map((a: any) => (
                        <option key={a.id} value={a.id}>{a.name}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-slate-500 dark:text-slate-400 mb-1.5 block">Category</label>
                    <select
                      value={newListing.category}
                      onChange={(e) => setNewListing({ ...newListing, category: e.target.value })}
                      className="w-full px-3 py-2.5 rounded-xl bg-slate-50 dark:bg-[#0f0a1a] border border-slate-200 dark:border-[#2d2247] text-sm text-slate-900 dark:text-white focus:outline-none focus:border-violet-500/50"
                    >
                      {CATEGORIES.filter((c) => c.value).map((c) => (
                        <option key={c.value} value={c.value}>{c.label}</option>
                      ))}
                    </select>
                  </div>
                </div>
                <div>
                  <label className="text-xs text-slate-500 dark:text-slate-400 mb-1.5 block">Title</label>
                  <input
                    type="text"
                    value={newListing.title}
                    onChange={(e) => setNewListing({ ...newListing, title: e.target.value })}
                    required
                    placeholder="e.g., Deep Work Shield — Auto-Decline Preset"
                    className="w-full px-3 py-2.5 rounded-xl bg-slate-50 dark:bg-[#0f0a1a] border border-slate-200 dark:border-[#2d2247] text-sm text-slate-900 dark:text-white placeholder:text-slate-400 focus:outline-none focus:border-violet-500/50"
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-500 dark:text-slate-400 mb-1.5 block">Description</label>
                  <textarea
                    value={newListing.description}
                    onChange={(e) => setNewListing({ ...newListing, description: e.target.value })}
                    rows={3}
                    placeholder="Describe what this capability does..."
                    className="w-full px-3 py-2.5 rounded-xl bg-slate-50 dark:bg-[#0f0a1a] border border-slate-200 dark:border-[#2d2247] text-sm text-slate-900 dark:text-white placeholder:text-slate-400 focus:outline-none focus:border-violet-500/50 resize-none"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs text-slate-500 dark:text-slate-400 mb-1.5 block">Price per Use ($)</label>
                    <input
                      type="number"
                      step="0.25"
                      min="0.25"
                      value={newListing.price_per_use}
                      onChange={(e) => setNewListing({ ...newListing, price_per_use: parseFloat(e.target.value) || 0 })}
                      required
                      className="w-full px-3 py-2.5 rounded-xl bg-slate-50 dark:bg-[#0f0a1a] border border-slate-200 dark:border-[#2d2247] text-sm text-slate-900 dark:text-white focus:outline-none focus:border-violet-500/50"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500 dark:text-slate-400 mb-1.5 block">Tags (comma-separated)</label>
                    <input
                      type="text"
                      value={newListing.tags}
                      onChange={(e) => setNewListing({ ...newListing, tags: e.target.value })}
                      placeholder="e.g., sales, email, b2b"
                      className="w-full px-3 py-2.5 rounded-xl bg-slate-50 dark:bg-[#0f0a1a] border border-slate-200 dark:border-[#2d2247] text-sm text-slate-900 dark:text-white placeholder:text-slate-400 focus:outline-none focus:border-violet-500/50"
                    />
                  </div>
                </div>
                <button
                  type="submit"
                  disabled={creating}
                  className="px-5 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-700 text-white text-sm font-medium transition-colors disabled:opacity-50"
                >
                  {creating ? "Creating..." : "Create Listing"}
                </button>
              </form>
            </div>
          )}

          {/* My Listings Table */}
          <div className="kairo-card">
            <h2 className="section-title mb-4">Your Listings</h2>
            {myListings.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-slate-400 text-sm">You haven&apos;t created any listings yet.</p>
                <p className="text-slate-300 dark:text-slate-600 text-xs mt-1">Click &quot;Create Listing&quot; to sell your agent&apos;s capabilities.</p>
              </div>
            ) : (
              <div className="space-y-2.5">
                {myListings.map((listing) => (
                  <div key={listing.id} className="flex items-center justify-between p-3.5 rounded-xl bg-slate-50 dark:bg-[#2d2247]/40 border border-slate-200 dark:border-[#2d2247]">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm text-slate-900 dark:text-white font-medium truncate">{listing.title}</p>
                        <span className={listing.status === "active" ? "badge-success" : "badge-neutral"}>{listing.status}</span>
                      </div>
                      <div className="flex items-center gap-3 mt-1">
                        <span className="text-[10px] text-slate-400">${listing.price_per_use.toFixed(2)}/use</span>
                        <span className="text-[10px] text-slate-400">{listing.total_purchases} sales</span>
                        <span className="text-[10px] text-slate-400">${listing.total_earnings.toFixed(2)} earned</span>
                        {listing.avg_rating > 0 && (
                          <span className="text-[10px] text-slate-400 flex items-center gap-0.5">
                            <Star className="w-2.5 h-2.5 text-amber-400 fill-amber-400" /> {listing.avg_rating.toFixed(1)}
                          </span>
                        )}
                      </div>
                    </div>
                    <button
                      onClick={() => toggleListingStatus(listing)}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                        listing.status === "active"
                          ? "bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400 hover:bg-amber-100 dark:hover:bg-amber-500/20"
                          : "bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-100 dark:hover:bg-emerald-500/20"
                      }`}
                    >
                      {listing.status === "active" ? <><Pause className="w-3 h-3" /> Pause</> : <><Play className="w-3 h-3" /> Activate</>}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}

      {/* ═══ MY PURCHASES TAB ═══ */}
      {tab === "my-purchases" && (
        <div className="kairo-card">
          <h2 className="section-title mb-4">Purchase History</h2>
          {purchases.length === 0 ? (
            <div className="text-center py-12">
              <div className="w-16 h-16 rounded-2xl bg-slate-50 dark:bg-[#2d2247]/40 border border-slate-200 dark:border-[#2d2247] flex items-center justify-center mx-auto mb-4">
                <ShoppingCart className="w-7 h-7 text-slate-200 dark:text-slate-600" />
              </div>
              <p className="text-slate-400 text-sm font-medium">No purchases yet</p>
              <p className="text-slate-300 dark:text-slate-600 text-xs mt-1">Browse the marketplace to find agent capabilities.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {purchases.map((txn) => (
                <div key={txn.id} className="p-4 rounded-xl bg-slate-50 dark:bg-[#2d2247]/40 border border-slate-200 dark:border-[#2d2247]">
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <p className="text-sm text-slate-900 dark:text-white font-medium">{txn.listing_title}</p>
                      <p className="text-[11px] text-slate-400">from {txn.seller_name}</p>
                    </div>
                    <div className="text-right">
                      <span className="text-sm font-semibold text-emerald-600 dark:text-emerald-400">${txn.amount.toFixed(2)}</span>
                      <p className="text-[10px] text-slate-400">{txn.created_at ? new Date(txn.created_at).toLocaleDateString() : ""}</p>
                    </div>
                  </div>
                  {txn.task_description && (
                    <p className="text-xs text-slate-500 dark:text-slate-400 mb-2">{txn.task_description}</p>
                  )}

                  {/* Review */}
                  {txn.rating ? (
                    <div className="flex items-center gap-2 pt-2 border-t border-slate-200 dark:border-[#2d2247]/60">
                      <StarRating rating={txn.rating} />
                      {txn.review_text && <span className="text-[11px] text-slate-400 italic">&quot;{txn.review_text}&quot;</span>}
                    </div>
                  ) : reviewTarget === txn.id ? (
                    <div className="pt-3 border-t border-slate-200 dark:border-[#2d2247]/60 space-y-2">
                      <ClickableStarRating value={reviewRating} onChange={setReviewRating} />
                      <div className="flex gap-2">
                        <input
                          type="text"
                          value={reviewText}
                          onChange={(e) => setReviewText(e.target.value)}
                          placeholder="Write a review..."
                          className="flex-1 px-3 py-2 rounded-lg bg-white dark:bg-[#0f0a1a] border border-slate-200 dark:border-[#2d2247] text-xs text-slate-900 dark:text-white placeholder:text-slate-400 focus:outline-none focus:border-violet-500/50"
                        />
                        <button
                          onClick={() => handleReview(txn.id)}
                          disabled={submittingReview}
                          className="px-3 py-2 rounded-lg bg-violet-600 hover:bg-violet-700 text-white text-xs font-medium transition-colors disabled:opacity-50"
                        >
                          <Send className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  ) : (
                    <button
                      onClick={() => { setReviewTarget(txn.id); setReviewRating(5); setReviewText(""); }}
                      className="flex items-center gap-1.5 text-[11px] text-violet-600 dark:text-violet-400 hover:text-violet-700 dark:hover:text-violet-300 mt-2 pt-2 border-t border-slate-200 dark:border-[#2d2247]/60 transition-colors"
                    >
                      <MessageSquare className="w-3 h-3" /> Leave a review
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
