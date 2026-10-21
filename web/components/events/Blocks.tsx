"use client";
import { useState } from "react";
import type { Block, EventData, Zone } from "../../lib/events";

const focus =
  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-berenjena";

export function DemoBadge({ label = "Demo" }: { label?: string }) {
  return (
    <span className="inline-flex items-center rounded-full bg-pistacho px-2 py-0.5 text-xs font-semibold text-berenjena">
      {label}
    </span>
  );
}

function EventCard({ event, onAsk, disabled }: { event: EventData; onAsk: (text: string) => void; disabled: boolean }) {
  return (
    <article className="rounded-2xl border border-berenjena/15 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-base font-semibold text-berenjena">{event.nombre}</h3>
        {event.demo && <DemoBadge label="Evento ficticio" />}
      </div>
      <p className="mt-0.5 text-sm text-berenjena/80">{event.artista}</p>
      <p className="mt-2 text-sm text-berenjena">
        {event.recinto ? `${event.recinto} · ` : ""}
        {event.ciudad}
      </p>
      <p className="text-sm text-berenjena">{event.fecha}</p>
      <button
        type="button"
        disabled={disabled}
        onClick={() => onAsk(`Quiero ver zonas y precios de ${event.nombre}`)}
        className={`mt-3 w-full rounded-xl bg-coral px-4 py-2.5 text-sm font-semibold text-berenjena transition hover:brightness-95 disabled:opacity-60 ${focus}`}
      >
        Ver zonas y precios
      </button>
    </article>
  );
}

function ZonePicker({
  event,
  maxQty,
  busy,
  onSelect,
}: {
  event: EventData;
  maxQty: number;
  busy: boolean;
  onSelect: (eventId: number, zoneId: number, qty: number) => void;
}) {
  const [zoneId, setZoneId] = useState<number | null>(null);
  const [qty, setQty] = useState(1);
  const zones = event.zonas ?? [];
  return (
    <section className="rounded-2xl border border-berenjena/15 bg-white p-4 shadow-sm" aria-label={`Zonas de ${event.nombre}`}>
      <h3 className="text-base font-semibold text-berenjena">{event.nombre}</h3>
      <p className="text-sm text-berenjena/80">
        {event.recinto ? `${event.recinto} · ` : ""}
        {event.ciudad} · {event.fecha}
      </p>
      <fieldset className="mt-3 space-y-2">
        <legend className="sr-only">Elige una zona</legend>
        {zones.map((z: Zone) => (
          <label
            key={z.id}
            className={`flex cursor-pointer items-start gap-3 rounded-xl border p-3 text-sm ${
              zoneId === z.id ? "border-berenjena bg-crema" : "border-berenjena/20"
            } ${!z.recomendable ? "cursor-not-allowed opacity-70" : ""}`}
          >
            <input
              type="radio"
              name={`zona-${event.id}`}
              className="mt-1 h-4 w-4 accent-[#352238]"
              disabled={!z.recomendable}
              checked={zoneId === z.id}
              onChange={() => setZoneId(z.id)}
            />
            <span className="flex-1">
              <span className="flex items-baseline justify-between gap-2">
                <span className="font-medium text-berenjena">{z.nombre}</span>
                <span className="font-mono text-berenjena">{z.precio_referencia}</span>
              </span>
              <span className="block text-xs text-berenjena/80">
                {z.estado}
                {z.requiere_verificacion && z.recomendable ? " · datos sin verificar recientemente" : ""}
              </span>
            </span>
          </label>
        ))}
      </fieldset>
      <div className="mt-3 flex items-end gap-3">
        <label className="text-sm text-berenjena">
          <span className="mb-1 block font-medium">Cantidad</span>
          <select
            value={qty}
            onChange={(e) => setQty(Number(e.target.value))}
            className={`rounded-lg border border-berenjena/30 bg-white px-3 py-2 ${focus}`}
          >
            {Array.from({ length: maxQty }, (_, i) => i + 1).map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          disabled={busy || zoneId === null}
          onClick={() => zoneId !== null && onSelect(event.id, zoneId, qty)}
          className={`flex-1 rounded-xl bg-coral px-4 py-2.5 text-sm font-semibold text-berenjena transition hover:brightness-95 disabled:opacity-50 ${focus}`}
        >
          Preparar selección
        </button>
      </div>
      <p className="mt-2 text-xs text-berenjena/80">
        Los precios son de referencia y se confirman en TuEntradaWeb. Preparar una selección no reserva nada.
      </p>
    </section>
  );
}

export function Blocks({
  blocks,
  maxQty,
  busy,
  onAsk,
  onSelect,
}: {
  blocks: Block[];
  maxQty: number;
  busy: boolean;
  onAsk: (text: string) => void;
  onSelect: (eventId: number, zoneId: number, qty: number) => void;
}) {
  return (
    <div className="mt-2 space-y-3">
      {blocks.map((b, i) => {
        if (b.type === "events")
          return (
            <div key={i} className="grid gap-3 sm:grid-cols-2">
              {b.events.map((e) => (
                <EventCard key={e.id} event={e} onAsk={onAsk} disabled={busy} />
              ))}
            </div>
          );
        if (b.type === "event") return <ZonePicker key={i} event={b.event} maxQty={maxQty} busy={busy} onSelect={onSelect} />;
        if (b.type === "selection")
          return (
            <section key={i} className="rounded-2xl border-2 border-berenjena bg-white p-4" aria-label="Resumen de selección">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-berenjena">Resumen de selección</h3>
              <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm text-berenjena">
                <dt className="text-berenjena/70">Evento</dt>
                <dd className="font-medium">{b.evento}</dd>
                <dt className="text-berenjena/70">Zona</dt>
                <dd className="font-medium">{b.zona}</dd>
                <dt className="text-berenjena/70">Cantidad</dt>
                <dd className="font-medium">{b.cantidad}</dd>
                <dt className="text-berenjena/70">Precio unitario</dt>
                <dd className="font-mono">{b.precio_unitario}</dd>
                <dt className="text-berenjena/70">Subtotal</dt>
                <dd className="font-mono text-lg font-semibold">{b.subtotal}</dd>
              </dl>
              <p className="mt-2 text-xs text-berenjena/80">{b.nota}.</p>
              {b.advertencias.map((w) => (
                <p key={w} className="mt-1 rounded-lg bg-crema p-2 text-xs text-berenjena">
                  ⚠ {w}
                </p>
              ))}
              <p className="mt-2 text-xs font-medium text-berenjena">{b.aviso}</p>
            </section>
          );
        if (b.type === "link")
          return b.habilitado && b.ruta ? (
            <div key={i}>
              <a
                href={b.ruta}
                target="_blank"
                rel="noopener noreferrer"
                className={`block rounded-xl bg-coral px-4 py-3 text-center text-sm font-semibold text-berenjena transition hover:brightness-95 ${focus}`}
              >
                {b.texto_boton ?? "Ver disponibilidad y comprar en TuEntradaWeb"}
              </a>
              {b.aviso && <p className="mt-1 text-xs text-berenjena/80">{b.aviso}</p>}
            </div>
          ) : (
            <div key={i}>
              <button
                type="button"
                disabled
                aria-disabled="true"
                className="block w-full cursor-not-allowed rounded-xl border border-berenjena/30 bg-white px-4 py-3 text-center text-sm font-semibold text-berenjena/70"
              >
                Ver disponibilidad y comprar en TuEntradaWeb
              </button>
              <p className="mt-1 text-xs text-berenjena">{b.mensaje ?? "Configura un enlace oficial para habilitar la compra"}.</p>
            </div>
          );
        return (
          <p key={i} className="rounded-xl bg-pistacho/60 p-3 text-sm text-berenjena">
            {b.mensaje}
          </p>
        );
      })}
    </div>
  );
}
