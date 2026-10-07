import { useState } from "react";
import { Volume2, VolumeX, Navigation } from "lucide-react";
import type { RouteAlternative } from "@/types";

interface Props {
  route: RouteAlternative | null;
}

function formatDistance(m: number): string {
  return m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`;
}

/** Turn-by-turn instructions for the selected route, with optional voice. */
export function TurnByTurnPanel({ route }: Props) {
  const [speaking, setSpeaking] = useState(false);

  if (!route || route.instructions.length === 0) {
    return (
      <div className="p-4 border-b border-slate-700">
        <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2 mb-2">
          <Navigation className="w-4 h-4 text-purple-400" />
          Directions
        </h3>
        <p className="text-xs text-slate-500">
          Select a route to see turn-by-turn directions.
        </p>
      </div>
    );
  }

  const speak = (texts: string[]) => {
    if (!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    texts.forEach((t) => {
      const u = new SpeechSynthesisUtterance(t);
      window.speechSynthesis.speak(u);
    });
    setSpeaking(true);
    setTimeout(() => setSpeaking(false), texts.length * 3500);
  };

  const stopSpeaking = () => {
    window.speechSynthesis?.cancel();
    setSpeaking(false);
  };

  return (
    <div className="p-4 border-b border-slate-700">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
          <Navigation className="w-4 h-4 text-purple-400" />
          Directions · {route.name}
        </h3>
        <button
          onClick={() =>
            speaking
              ? stopSpeaking()
              : speak(route.instructions.map((i) => i.instruction))
          }
          className="flex items-center gap-1 text-[10px] px-2 py-1 rounded bg-slate-700 text-slate-300 hover:bg-slate-600"
          title="Voice navigation"
        >
          {speaking ? (
            <VolumeX className="w-3.5 h-3.5" />
          ) : (
            <Volume2 className="w-3.5 h-3.5" />
          )}
          {speaking ? "Stop" : "Voice"}
        </button>
      </div>
      <ol className="space-y-1.5 max-h-64 overflow-y-auto pr-1">
        {route.instructions.slice(0, 40).map((step, i) => (
          <li
            key={i}
            onClick={() => speak([step.instruction])}
            className="flex items-start gap-2 p-2 rounded bg-slate-900/60 border border-slate-700/60 cursor-pointer hover:border-slate-600"
          >
            <span className="w-5 h-5 shrink-0 rounded-full bg-purple-500/20 text-purple-300 text-[10px] font-bold flex items-center justify-center">
              {i + 1}
            </span>
            <div className="min-w-0">
              <div className="text-xs text-slate-200 leading-snug">
                {step.instruction}
              </div>
              <div className="text-[10px] text-slate-500">
                {formatDistance(step.distance_m)} ·{" "}
                {Math.round(step.duration_s)}s
              </div>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
