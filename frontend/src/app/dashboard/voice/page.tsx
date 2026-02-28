"use client";
import { useState, useRef, useEffect, useCallback } from "react";
import { Mic, MicOff, Volume2, Wifi, WifiOff, Globe, ChevronDown, Square, AlertTriangle, MessageSquare } from "lucide-react";
import { Room, RoomEvent, Track, RemoteTrackPublication, RemoteTrack } from "livekit-client";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Language = "EN" | "HI" | "Auto";
type ConnectionStatus = "disconnected" | "connecting" | "connected" | "not_configured";

const QUICK_COMMANDS = [
  { label: "What did I miss?", icon: "?" },
  { label: "Aaj ka schedule kya hai?", icon: "HI" },
  { label: "Toggle ghost mode", icon: "G" },
  { label: "Weekly summary", icon: "W" },
];

export default function VoicePage() {
  const [isListening, setIsListening] = useState(false);
  const [language, setLanguage] = useState<Language>("Auto");
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const [transcript, setTranscript] = useState<{ role: "user" | "agent"; text: string }[]>([]);
  const [showLangMenu, setShowLangMenu] = useState(false);
  const [configError, setConfigError] = useState<string | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement>(null);
  const roomRef = useRef<Room | null>(null);

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript]);

  useEffect(() => {
    // Suppress LiveKit internal unhandled promise rejections (WebSocket Event objects)
    // that surface as [object Event] in Next.js dev overlay
    const handleRejection = (e: PromiseRejectionEvent) => {
      if (e.reason instanceof Event || (e.reason && typeof e.reason === "object" && !(e.reason instanceof Error))) {
        e.preventDefault();
      }
    };
    window.addEventListener("unhandledrejection", handleRejection);
    return () => {
      window.removeEventListener("unhandledrejection", handleRejection);
      if (roomRef.current) {
        roomRef.current.disconnect();
        roomRef.current = null;
      }
    };
  }, []);

  const connectToRoom = useCallback(async () => {
    const token = typeof window !== "undefined" ? localStorage.getItem("kairo_token") : null;
    if (!token) {
      setTranscript((prev) => [...prev, { role: "agent", text: "Please log in to use voice features." }]);
      return;
    }

    setStatus("connecting");
    setConfigError(null);

    try {
      const res = await fetch(`${API_URL}/api/voice/token`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ mode: "COMMAND", language }),
      });

      if (!res.ok) {
        throw new Error(`Token request failed: ${res.status}`);
      }

      const data = await res.json();

      if (data.error) {
        setStatus("not_configured");
        setConfigError(data.error);
        return;
      }

      const room = new Room();
      roomRef.current = room;

      room.on(RoomEvent.TrackSubscribed, (track: RemoteTrack, publication: RemoteTrackPublication) => {
        if (track.kind === Track.Kind.Audio) {
          const element = track.attach();
          element.autoplay = true;
          element.id = `lk-audio-${publication.trackSid}`;
          document.body.appendChild(element);
        }
      });

      room.on(RoomEvent.TrackUnsubscribed, (track: RemoteTrack) => {
        track.detach().forEach((el) => el.remove());
      });

      room.on(RoomEvent.DataReceived, (payload: Uint8Array | unknown) => {
        try {
          // livekit-client may pass raw Uint8Array or a DataPacket wrapper
          let bytes: Uint8Array;
          if (payload instanceof Uint8Array) {
            bytes = payload;
          } else if (payload && typeof payload === "object" && "payload" in payload) {
            bytes = (payload as { payload: Uint8Array }).payload;
          } else {
            return; // Unknown shape, skip
          }
          const message = JSON.parse(new TextDecoder().decode(bytes));
          if (message.type === "transcript" || message.type === "response") {
            const role = message.role === "user" ? "user" as const : "agent" as const;
            setTranscript((prev) => [...prev, { role, text: message.text }]);
          }
        } catch {
          // Not JSON data, ignore
        }
      });

      room.on(RoomEvent.Disconnected, () => {
        setStatus("disconnected");
        setIsListening(false);
        roomRef.current = null;
      });

      await room.connect(data.url, data.token);
      setStatus("connected");

      await room.localParticipant.setMicrophoneEnabled(true);
      setIsListening(true);

      setTranscript((prev) => [
        ...prev,
        { role: "agent", text: "Connected. Listening..." },
      ]);
    } catch (err: unknown) {
      setStatus("disconnected");
      const message = err instanceof Error ? err.message : "Unknown error";
      setTranscript((prev) => [
        ...prev,
        { role: "agent", text: `Connection failed: ${message}` },
      ]);
    }
  }, [language]);

  const disconnect = useCallback(() => {
    if (roomRef.current) {
      roomRef.current.disconnect();
      roomRef.current = null;
    }
    setStatus("disconnected");
    setIsListening(false);
  }, []);

  const toggleListening = useCallback(async () => {
    if (status === "disconnected" || status === "not_configured") {
      await connectToRoom();
      return;
    }

    if (status === "connected" && roomRef.current) {
      if (isListening) {
        await roomRef.current.localParticipant.setMicrophoneEnabled(false);
        setIsListening(false);
      } else {
        await roomRef.current.localParticipant.setMicrophoneEnabled(true);
        setIsListening(true);
      }
    }
  }, [status, isListening, connectToRoom]);

  const sendQuickCommand = (cmd: string) => {
    if (status === "connected" && roomRef.current) {
      const encoder = new TextEncoder();
      const data = encoder.encode(JSON.stringify({ type: "command", text: cmd }));
      roomRef.current.localParticipant.publishData(data, { reliable: true });
      setTranscript((prev) => [...prev, { role: "user", text: cmd }]);
    } else {
      setTranscript((prev) => [
        ...prev,
        { role: "user", text: cmd },
        { role: "agent", text: "Connect to a voice session first to send commands." },
      ]);
    }
  };

  const statusLabel =
    status === "not_configured"
      ? "Not configured"
      : status === "disconnected"
      ? "Connect to start"
      : status === "connecting"
      ? "Connecting..."
      : isListening
      ? "Listening..."
      : "Connected";

  const statusColor =
    status === "connected"
      ? "text-emerald-600 dark:text-emerald-400"
      : status === "connecting"
      ? "text-amber-600 dark:text-amber-400"
      : status === "not_configured"
      ? "text-red-500 dark:text-red-400"
      : "text-slate-400";

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="font-['DM_Serif_Display'] text-2xl text-slate-900 dark:text-white">Voice Interface</h1>
        <p className="text-slate-400 text-sm mt-0.5">Talk to Kairo using natural voice in English or Hindi.</p>
      </div>

      {/* LiveKit not configured notice */}
      {status === "not_configured" && configError && (
        <div className="kairo-card mb-6 border-red-500/20 bg-red-50 dark:bg-red-500/10">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-red-500 dark:text-red-400 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm text-red-600 dark:text-red-400 font-medium">LiveKit Not Configured</p>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                To enable real-time voice, add these to your <code className="bg-red-100 dark:bg-red-500/20 px-1 rounded text-red-600 dark:text-red-400">.env</code> file:
              </p>
              <pre className="mt-2 p-3 rounded-lg bg-slate-900 dark:bg-black/40 text-xs text-slate-300 font-mono overflow-x-auto">
{`LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret
LIVEKIT_URL=wss://your-instance.livekit.cloud`}
              </pre>
              <div className="mt-3 p-3 rounded-lg bg-violet-50 dark:bg-violet-500/10 border border-violet-200 dark:border-violet-500/20">
                <div className="flex items-center gap-2 mb-1">
                  <MessageSquare className="w-3.5 h-3.5 text-violet-600 dark:text-violet-400" />
                  <p className="text-xs font-medium text-violet-700 dark:text-violet-300">Use Command Bar Instead</p>
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Press <kbd className="px-1.5 py-0.5 rounded bg-slate-200 dark:bg-[#2d2247] text-[10px] font-mono">&#x2318;K</kbd> to open the Command Bar — it supports text + mic input without LiveKit.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Disconnected notice */}
      {status === "disconnected" && (
        <div className="kairo-card mb-6 border-amber-500/20 bg-amber-50 dark:bg-amber-500/10">
          <div className="flex items-center gap-3">
            <WifiOff className="w-4 h-4 text-amber-600 dark:text-amber-400 flex-shrink-0" />
            <div>
              <p className="text-sm text-amber-600 dark:text-amber-400 font-medium">Not connected</p>
              <p className="text-xs text-slate-400 mt-0.5">Tap the mic to connect to Kairo&apos;s voice agent via LiveKit.</p>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* -- Main voice area -- */}
        <div className="lg:col-span-2 space-y-6">
          {/* Mic button + status */}
          <div className="kairo-card flex flex-col items-center py-12">
            <div className={`flex items-center gap-2 mb-6 ${statusColor}`}>
              {status === "connected" ? (
                <Wifi className="w-3.5 h-3.5" />
              ) : status === "connecting" ? (
                <Wifi className="w-3.5 h-3.5 animate-pulse" />
              ) : status === "not_configured" ? (
                <AlertTriangle className="w-3.5 h-3.5" />
              ) : (
                <WifiOff className="w-3.5 h-3.5" />
              )}
              <span className="text-xs font-medium">{statusLabel}</span>
            </div>

            <button
              onClick={toggleListening}
              disabled={status === "connecting"}
              className={`relative w-24 h-24 rounded-full flex items-center justify-center transition-all duration-300 ${
                isListening
                  ? "bg-violet-600 shadow-[0_0_40px_rgba(124,58,237,0.4)]"
                  : status === "connecting"
                  ? "bg-slate-100 dark:bg-[#2d2247] animate-pulse cursor-wait"
                  : "bg-slate-100 dark:bg-[#2d2247] border-2 border-slate-200 dark:border-[#2d2247] hover:border-violet-500/50 hover:shadow-[0_0_20px_rgba(124,58,237,0.15)]"
              }`}
            >
              {isListening ? (
                <Volume2 className="w-10 h-10 text-white animate-pulse" />
              ) : (
                <Mic className={`w-10 h-10 ${status === "connecting" ? "text-amber-600 dark:text-amber-400" : status === "not_configured" ? "text-red-400" : "text-slate-400"}`} />
              )}
              {isListening && (
                <>
                  <span className="absolute inset-0 rounded-full border-2 border-violet-500 animate-ping opacity-20" />
                  <span className="absolute inset-[-8px] rounded-full border border-violet-500/30 animate-ping opacity-10" style={{ animationDelay: "0.3s" }} />
                </>
              )}
            </button>

            <p className="text-slate-400 text-xs mt-6">
              {status === "not_configured"
                ? "Configure LiveKit or use Command Bar (⌘K)"
                : status === "connecting"
                ? "Connecting..."
                : isListening
                ? "Tap to mute"
                : status === "connected"
                ? "Tap to unmute"
                : "Tap to start voice session"}
            </p>

            {status === "connected" && (
              <button
                onClick={disconnect}
                className="mt-4 flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 transition-colors"
              >
                <Square className="w-3 h-3" />
                Disconnect
              </button>
            )}
          </div>

          {/* Transcript */}
          <div className="kairo-card">
            <h2 className="section-title mb-4">Transcript</h2>
            <div className="h-64 overflow-y-auto space-y-3 scrollbar-thin">
              {transcript.length === 0 ? (
                <p className="text-slate-400 text-sm text-center py-8">
                  Start a voice session or use a quick command to begin.
                </p>
              ) : (
                transcript.map((msg, i) => (
                  <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                    <div
                      className={`max-w-[80%] px-4 py-2.5 rounded-xl text-sm ${
                        msg.role === "user"
                          ? "bg-violet-100 dark:bg-violet-500/15 text-violet-600 dark:text-violet-400 rounded-br-md"
                          : "bg-slate-50 dark:bg-[#2d2247]/40 text-slate-500 dark:text-slate-400 rounded-bl-md"
                      }`}
                    >
                      {msg.text}
                    </div>
                  </div>
                ))
              )}
              <div ref={transcriptEndRef} />
            </div>
          </div>
        </div>

        {/* -- Side controls -- */}
        <div className="space-y-6">
          {/* Language */}
          <div className="kairo-card">
            <h3 className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-3">Language</h3>
            <div className="relative">
              <button
                onClick={() => setShowLangMenu(!showLangMenu)}
                disabled={status === "connected"}
                className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg bg-slate-50 dark:bg-[#2d2247]/40 border border-slate-200 dark:border-[#2d2247] text-sm text-slate-900 dark:text-white ${status === "connected" ? "opacity-60 cursor-not-allowed" : ""}`}
              >
                <span className="flex items-center gap-2">
                  <Globe className="w-3.5 h-3.5 text-slate-400" />
                  {language === "Auto" ? "Auto Detect" : language === "EN" ? "English" : "Hindi"}
                </span>
                <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
              </button>
              {showLangMenu && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-white dark:bg-[#1e1533] border border-slate-200 dark:border-[#2d2247] rounded-lg overflow-hidden z-10">
                  {(["EN", "HI", "Auto"] as Language[]).map((l) => (
                    <button
                      key={l}
                      onClick={() => { setLanguage(l); setShowLangMenu(false); }}
                      className={`w-full text-left px-3 py-2 text-xs transition-colors ${
                        language === l ? "text-violet-600 dark:text-violet-400 bg-violet-50/50 dark:bg-violet-500/5" : "text-slate-500 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-[#2d2247]/30"
                      }`}
                    >
                      {l === "Auto" ? "Auto Detect" : l === "EN" ? "English" : "Hindi"}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Quick commands */}
          <div className="kairo-card">
            <h3 className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-3">Quick Commands</h3>
            <div className="space-y-1.5">
              {QUICK_COMMANDS.map((cmd) => (
                <button
                  key={cmd.label}
                  onClick={() => sendQuickCommand(cmd.label)}
                  className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-50 dark:hover:bg-[#2d2247]/30 transition-colors text-left"
                >
                  <span className="w-5 h-5 rounded bg-slate-100 dark:bg-[#2d2247] flex items-center justify-center text-[9px] font-bold text-slate-400 flex-shrink-0">
                    {cmd.icon}
                  </span>
                  {cmd.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
