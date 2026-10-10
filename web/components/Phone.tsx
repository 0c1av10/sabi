import { WhatsAppLogo } from "./Brand";

export type Msg = { who: "c" | "s"; text: string; time?: string };

export default function Phone({ msgs, footer, animate = false, step = 0.9, className = "" }: {
  msgs: Msg[]; footer?: React.ReactNode; animate?: boolean; step?: number; className?: string;
}) {
  const delay = (i: number) => (animate ? { animationDelay: `${0.4 + i * step}s` } : undefined);
  const cls = animate ? "msg-in" : "";
  return (
    <div className={`relative w-[300px] shrink-0 rounded-[2.75rem] border-[10px] border-stone-900 bg-stone-900 shadow-2xl shadow-emerald-950/40 ${className}`}>
      <div className="absolute left-1/2 top-0 z-10 h-5 w-24 -translate-x-1/2 rounded-b-2xl bg-stone-900" />
      <div className="flex h-[560px] flex-col overflow-hidden rounded-[2.1rem] bg-[#efeae2]">
        <div className="flex items-center gap-2 bg-[#075E54] px-4 pb-3 pt-7 text-white">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-500 text-xs font-bold">LE</div>
          <div className="leading-tight">
            <p className="text-sm font-semibold">La Esquina</p>
            <p className="text-[11px] text-emerald-100">en línea</p>
          </div>
          <WhatsAppLogo className="ml-auto h-5 w-5" fill="#ffffff" />
        </div>
        <div className="flex-1 space-y-2 overflow-hidden px-3 py-4">
          {msgs.map((m, i) => (
            <div key={i} style={delay(i)}
              className={`${cls} max-w-[85%] rounded-lg px-3 py-2 text-[13px] leading-snug text-stone-800 shadow-sm ${
                m.who === "c" ? "ml-auto rounded-tr-none bg-[#d9fdd3]" : "rounded-tl-none bg-white"}`}>
              <p className="whitespace-pre-line">{m.text}</p>
              <p className="mt-0.5 text-right text-[10px] text-stone-400">{m.time ?? "21:04"}</p>
            </div>
          ))}
          {footer && <div style={delay(msgs.length)} className={`${cls} pt-1`}>{footer}</div>}
        </div>
        <div className="flex items-center gap-2 bg-[#efeae2] px-3 pb-4">
          <div className="flex-1 rounded-full bg-white px-4 py-2 text-xs text-stone-400">Mensaje</div>
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#25D366]">
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round"><path d="M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3zM19 11a7 7 0 0 1-14 0M12 18v3" /></svg>
          </div>
        </div>
      </div>
    </div>
  );
}
