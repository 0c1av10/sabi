"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Block,
  ChatResponse,
  SelectResponse,
  Status,
  eventsApi,
} from "../../lib/events";
import { Blocks, DemoBadge } from "./Blocks";

type Msg = { id: number; role: "user" | "assistant"; text: string; blocks?: Block[]; error?: boolean };

const SESSION_KEY = "sabi_events_session";
const GREETING =
  "Soy Sabi 👋, el asistente de eventos de FC Producciones. Te ayudo a encontrar un evento, ver zonas y " +
  "precios de referencia y llegar al enlace oficial para comprar. Por ejemplo: \"Busco un concierto en Caracas\".";
const SUGGESTIONS = ["Busco un concierto en Caracas", "¿Qué eventos hay en Valencia?", "Busco un evento en Maracaibo"];

const focus =
  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-berenjena";

function readSession(): string | null {
  try {
    return sessionStorage.getItem(SESSION_KEY);
  } catch {
    return null;
  }
}

export default function EventsChat() {
  const [messages, setMessages] = useState<Msg[]>([{ id: 0, role: "assistant", text: GREETING }]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<Status | null>(null);
  const sessionRef = useRef<string | null>(null);
  const nextId = useRef(1);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    sessionRef.current = readSession();
    eventsApi<Status>("/status").then(setStatus).catch(() => setStatus(null));
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages, busy]);

  const push = useCallback((m: Omit<Msg, "id">) => {
    setMessages((prev) => [...prev, { ...m, id: nextId.current++ }]);
  }, []);

  const remember = (id: string) => {
    sessionRef.current = id;
    try {
      sessionStorage.setItem(SESSION_KEY, id);
    } catch {
      /* storage unavailable: the chat still works for this page view */
    }
  };

  async function send(text: string) {
    const message = text.trim();
    if (!message || busy) return;
    setInput("");
    setBusy(true);
    push({ role: "user", text: message });
    try {
      const res = await eventsApi<ChatResponse>("/chat", {
        method: "POST",
        body: JSON.stringify({ session_id: sessionRef.current, message }),
      });
      remember(res.session_id);
      push({ role: "assistant", text: res.reply, blocks: res.ui });
    } catch (e) {
      push({ role: "assistant", text: (e as Error).message || "No pude responder. Intenta de nuevo.", error: true });
    } finally {
      setBusy(false);
    }
  }

  async function selectZone(eventId: number, zoneId: number, qty: number) {
    if (busy) return;
    setBusy(true);
    try {
      const res = await eventsApi<SelectResponse>("/select", {
        method: "POST",
        body: JSON.stringify({ session_id: sessionRef.current, event_id: eventId, zone_id: zoneId, quantity: qty }),
      });
      remember(res.session_id);
      if (res.ok) {
        push({
          role: "assistant",
          text: "Listo, armé tu resumen. Recuerda: esto no es una reserva; la disponibilidad y el pago se confirman en TuEntradaWeb.",
          blocks: res.ui,
        });
      } else {
        push({ role: "assistant", text: res.mensaje || "No pude preparar esa selección.", error: true });
      }
    } catch (e) {
      push({ role: "assistant", text: (e as Error).message || "No pude preparar la selección.", error: true });
    } finally {
      setBusy(false);
    }
  }

  async function askHuman() {
    if (busy) return;
    setBusy(true);
    try {
      const res = await eventsApi<{ session_id: string; mensaje: string }>("/human", {
        method: "POST",
        body: JSON.stringify({ session_id: sessionRef.current, motivo: "Solicitud desde el chat web" }),
      });
      remember(res.session_id);
      push({ role: "assistant", text: res.mensaje, blocks: [{ type: "human", mensaje: "Solicitud de atención humana registrada." }] });
    } catch (e) {
      push({ role: "assistant", text: (e as Error).message || "No pude registrar la solicitud.", error: true });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-[100dvh] max-w-2xl flex-col bg-crema text-berenjena">
      <header className="sticky top-0 z-10 border-b border-berenjena/15 bg-crema/95 px-4 pb-3 pt-4 backdrop-blur">
        <div className="flex items-center justify-between gap-3">
          <h1 className="text-lg font-bold">Sabi — Asistente de eventos</h1>
          <DemoBadge />
        </div>
        <p className="mt-1 text-xs text-berenjena/80">
          Demostración independiente para FC Producciones: no es una integración oficial con TuEntradaWeb ni una
          alianza aprobada.
        </p>
        {status?.demo_data && (
          <p role="status" className="mt-2 rounded-lg bg-pistacho px-3 py-1.5 text-xs font-medium">
            Estás viendo datos de demostración: los eventos son ficticios y la compra externa está desactivada.
          </p>
        )}
        {status?.engine === "demo" && (
          <p className="mt-1 text-xs text-berenjena/70">Respuestas guiadas de demostración (sin IA externa).</p>
        )}
      </header>

      <main className="flex-1 px-4 py-4">
        <div role="log" aria-live="polite" aria-label="Conversación con Sabi" className="space-y-4">
          {messages.map((m) => (
            <div key={m.id} className={m.role === "user" ? "flex justify-end" : "flex justify-start"}>
              <div className={m.role === "user" ? "max-w-[85%]" : "w-full max-w-[95%]"}>
                <p
                  className={`whitespace-pre-line rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                    m.role === "user"
                      ? "bg-berenjena text-crema"
                      : m.error
                        ? "border border-coral bg-white text-berenjena"
                        : "border border-berenjena/15 bg-white text-berenjena"
                  }`}
                >
                  {m.error && <span className="sr-only">Error: </span>}
                  {m.text}
                </p>
                {m.blocks && m.blocks.length > 0 && (
                  <Blocks blocks={m.blocks} maxQty={status?.max_quantity ?? 10} busy={busy} onAsk={send} onSelect={selectZone} />
                )}
              </div>
            </div>
          ))}
          {busy && (
            <p className="text-sm text-berenjena/70" role="status">
              Sabi está escribiendo…
            </p>
          )}
          <div ref={endRef} />
        </div>

        {messages.length === 1 && (
          <div className="mt-4 flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => send(s)}
                className={`rounded-full border border-berenjena/30 bg-white px-3 py-1.5 text-sm hover:bg-pistacho/50 ${focus}`}
              >
                {s}
              </button>
            ))}
          </div>
        )}
      </main>

      <footer className="sticky bottom-0 border-t border-berenjena/15 bg-crema px-4 pb-4 pt-3">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
          className="flex gap-2"
        >
          <label htmlFor="mensaje" className="sr-only">
            Escribe tu mensaje
          </label>
          <input
            id="mensaje"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            maxLength={500}
            autoComplete="off"
            placeholder="Escribe tu mensaje…"
            className={`min-w-0 flex-1 rounded-xl border border-berenjena/30 bg-white px-4 py-3 text-base ${focus}`}
          />
          <button
            type="submit"
            disabled={busy || !input.trim()}
            className={`rounded-xl bg-coral px-5 py-3 text-sm font-semibold text-berenjena transition hover:brightness-95 disabled:opacity-50 ${focus}`}
          >
            Enviar
          </button>
        </form>
        <div className="mt-2 flex items-center justify-between gap-3">
          <button type="button" onClick={askHuman} disabled={busy} className={`text-sm font-medium underline ${focus}`}>
            Hablar con una persona
          </button>
        </div>
        <p className="mt-2 text-xs text-berenjena/80">
          Precios y disponibilidad deben verificarse en TuEntradaWeb. El pago ocurre en esa plataforma externa; Sabi
          nunca te pide tarjeta, CVV ni claves.
        </p>
      </footer>
    </div>
  );
}
