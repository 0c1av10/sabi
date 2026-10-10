import Link from "next/link";

const chat = [
  { who: "c", text: "Hola! Quiero pedir 2 milanesas napolitanas y una gaseosa", time: "21:03" },
  { who: "s", text: "Anoté 2 milanesas y una gaseosa. ¿Les sumo un flan con dulce de leche de postre? Es casero, $1,50. ¿Delivery o retiro?", time: "21:03" },
  { who: "c", text: "Dale, súmalo. Delivery a Av. Francisco de Miranda, Chacao", time: "21:04" },
  { who: "s", text: "Tu pedido: 2 milanesas + 1 gaseosa + 1 flan. Total: $11,70 · €10,78 · Bs 427,05. ¿Está correcto?", time: "21:04" },
  { who: "c", text: "Sí", time: "21:05" },
];

const features = [
  {
    title: "Asesora y vende, no solo responde",
    desc: "Recomienda según lo que el cliente busca, sugiere la bebida o el postre antes de cerrar y ofrece un reemplazo cuando algo se agotó. Siempre con tu menú y tus precios, sin presionar.",
  },
  {
    title: "Cierra el pedido completo",
    desc: "Ítems, cantidades, extras, delivery o retiro, dirección y total en dólares, euros y bolívares. A cualquier hora, sin audios ni notas a mano.",
  },
  {
    title: "Tú apruebas cada pedido",
    desc: "Nada se confirma solo. Cada pedido llega a tu bandeja con el resumen completo y lo apruebas, editas o rechazas con un toque. Solo entonces el cliente recibe la confirmación. Cada conversación y pedido queda registrado.",
  },
  {
    title: "Dólares, euros y bolívares",
    desc: "Cargas el menú en dólares y las tasas del día. Sabi le da a cada cliente el precio en las tres monedas, sin cuentas a mano ni tasas viejas.",
  },
  {
    title: "Reservas sin cruces",
    desc: "El cliente pide mesa por el mismo chat y Sabi la agenda según tus horarios y mesas libres. Llega con el piloto.",
  },
  {
    title: "Un copiloto para ti",
    desc: "Ticket promedio, lo más pedido y qué conviene ofrecer hoy, en tu panel. Además, tu link de pedidos listo para compartir.",
  },
];

const pains: [string, string][] = [
  ["M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7v5l3 2", "Respuesta lenta = pedido perdido"],
  ["M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z", "Mensajes que llegan con el local cerrado"],
  ["M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3zM19 11a7 7 0 0 1-14 0M12 18v3", "Pedidos mal anotados de audios"],
  ["M8 3v3M16 3v3M4 8h16M5 5h14a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z", "Reservas cruzadas"],
];

export default function Landing() {
  return (
    <div className="bg-white">
      {/* Hero */}
      <section className="border-b">
        <div className="mx-auto grid max-w-6xl gap-12 px-6 py-20 md:grid-cols-2 md:items-center">
          <div>
            <h1 className="text-4xl font-bold leading-tight tracking-tight md:text-5xl">
              Tu mejor vendedor, atendiendo WhatsApp las 24 horas
            </h1>
            <p className="mt-5 text-lg text-stone-600">
              Tu cliente ordena, pregunta y reserva desde WhatsApp. Sabi no es un chatbot que contesta
              preguntas: recomienda platos, sugiere el acompañamiento justo y cierra el pedido. Tú apruebas
              cada uno antes de que se confirme.
            </p>
            <div className="mt-8 flex gap-3">
              <Link href="/login" className="rounded-lg bg-emerald-700 px-6 py-3 font-medium text-white hover:bg-emerald-800">
                Probar el panel
              </Link>
              <a href="#como-funciona" className="rounded-lg border px-6 py-3 font-medium text-stone-700 hover:bg-stone-50">
                Cómo funciona
              </a>
            </div>
          </div>

          {/* WhatsApp mock */}
          <div className="rounded-3xl border bg-[#ece5dd] p-4 shadow-sm">
            <div className="mb-3 flex items-center gap-2 border-b border-stone-300/60 pb-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-emerald-700 text-sm font-bold text-white">S</div>
              <div>
                <p className="text-sm font-semibold">La Esquina · Sabi</p>
                <p className="text-xs text-emerald-700">en línea</p>
              </div>
            </div>
            <div className="space-y-2">
              {chat.map((m, i) => (
                <div key={i} className={`max-w-[85%] rounded-lg px-3 py-2 text-sm shadow-sm ${
                  m.who === "c" ? "ml-auto bg-[#dcf8c6]" : "bg-white"}`}>
                  <p>{m.text}</p>
                  <p className="mt-0.5 text-right text-[10px] text-stone-400">{m.time}</p>
                </div>
              ))}
              <div className="ml-auto w-fit rounded-lg border border-emerald-600 bg-emerald-50 px-3 py-2 text-xs font-medium text-emerald-800">
                Pedido enviado al dueño · pendiente de aprobación
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Metrics strip */}
      <section className="border-b bg-emerald-900 text-white">
        <div className="mx-auto grid max-w-6xl grid-cols-1 gap-8 px-6 py-10 text-center md:grid-cols-3">
          {[["24 h", "Atención todos los días"],
            ["100%", "Pedidos que pasan por tu aprobación"],
            ["0", "Pedidos confirmados sin tu ok"]].map(([n, l]) => (
            <div key={l}>
              <p className="text-3xl font-bold">{n}</p>
              <p className="mt-1 text-sm text-emerald-200">{l}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Problem */}
      <section className="bg-gradient-to-b from-emerald-950 to-[#04261c] text-white">
        <div className="mx-auto max-w-6xl px-6 py-20 text-center">
          <svg viewBox="0 0 200 200" className="mx-auto h-44 w-44" aria-hidden="true">
            <path d="M100 100 L176.08 75.28 A80 80 0 1 1 100 20 Z" fill="#1f4b5c" />
            <path d="M105.88 91.91 L105.88 11.91 A80 80 0 0 1 181.96 67.19 Z" fill="#ef4444" />
          </svg>
          <p className="mt-8 text-3xl font-bold md:text-4xl">20% de las reservas</p>
          <p className="mt-1 text-2xl text-emerald-100/80 md:text-3xl">se pierden por responder tarde</p>
          <div className="mt-12 grid gap-4 text-left sm:grid-cols-2 lg:grid-cols-4">
            {pains.map(([icon, text]) => (
              <div key={text} className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/5 px-4 py-4">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-white/15">
                  <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <path d={icon} />
                  </svg>
                </span>
                <span className="text-sm text-emerald-50">{text}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="mx-auto max-w-6xl px-6 py-20">
        <h2 className="text-3xl font-bold tracking-tight">Un agente que vende, no un chatbot que contesta</h2>
        <p className="mt-3 max-w-2xl text-stone-600">
          Sabi conversa como tu mejor mesonero: conoce el menú, recomienda y cierra la venta. Tú tienes la última palabra.
        </p>
        <div className="mt-12 grid gap-6 md:grid-cols-2">
          {features.map((f) => (
            <div key={f.title} className="rounded-2xl border p-6">
              <h3 className="text-lg font-semibold">{f.title}</h3>
              <p className="mt-3 text-sm leading-relaxed text-stone-600">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* WhatsApp link + ticket */}
      <section className="border-t">
        <div className="mx-auto grid max-w-6xl gap-12 px-6 py-20 md:grid-cols-2 md:items-center">
          <div>
            <h2 className="text-3xl font-bold tracking-tight">Tu cliente ya está en WhatsApp</h2>
            <p className="mt-4 text-stone-600">
              Un solo link en tu Instagram, en Google Maps o en un QR sobre la mesa abre el chat con Sabi.
              Sin bajar apps, sin registrarse, sin formularios.
            </p>
            <p className="mt-4 text-stone-600">
              Menos pasos es más pedidos cerrados. Y como Sabi sugiere la bebida o el postre que falta,
              cada pedido sale con un ticket más alto.
            </p>
            <h3 className="mt-10 text-lg font-semibold">Conexión con tu POS y tu sistema, sin fricción</h3>
            <p className="mt-2 text-stone-600">
              Los pedidos aprobados pasan a tu caja sin volver a tipearlos. Llega con el piloto.
            </p>
          </div>

          <div className="space-y-4">
            <div className="rounded-2xl border p-5 shadow-sm">
              <div className="flex items-center gap-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-tr from-amber-400 via-rose-500 to-fuchsia-600 p-[2px]">
                  <div className="flex h-full w-full items-center justify-center rounded-full bg-white text-sm font-bold text-stone-800">LE</div>
                </div>
                <div>
                  <p className="text-sm font-semibold">laesquina.ccs</p>
                  <p className="text-xs text-stone-500">Milanesas, empanadas y flan casero · Chacao</p>
                </div>
              </div>
              <div className="mt-4 flex items-center justify-between rounded-xl bg-[#25D366] px-4 py-3 text-white">
                <span className="text-sm font-medium">Pide por WhatsApp</span>
                <span className="text-xs opacity-90">wa.me/laesquina</span>
              </div>
            </div>

            <div className="rounded-2xl border p-5 shadow-sm">
              <div className="flex items-baseline justify-between text-sm">
                <span className="text-stone-600">Lo que el cliente pidió</span>
                <span className="font-medium">$10,20</span>
              </div>
              <div className="mt-2 h-2 rounded-full bg-stone-100">
                <div className="h-2 rounded-full bg-stone-400" style={{ width: "87%" }} />
              </div>
              <div className="mt-5 flex items-baseline justify-between text-sm">
                <span className="text-stone-600">Con el flan que sugirió Sabi</span>
                <span className="font-semibold text-emerald-700">$11,70</span>
              </div>
              <div className="mt-2 h-2 rounded-full bg-stone-100">
                <div className="h-2 rounded-full bg-emerald-600" style={{ width: "100%" }} />
              </div>
              <p className="mt-4 text-xs text-stone-500">Mismo cliente, misma conversación: 15% más de ticket.</p>
            </div>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="como-funciona" className="border-t bg-stone-50">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <h2 className="text-3xl font-bold tracking-tight">Así funciona</h2>
          <div className="mt-10 grid gap-8 md:grid-cols-3">
            {[
              ["Sabi asesora", "El cliente escribe por WhatsApp como siempre. Sabi le recomienda, le sugiere qué sumar y arma el pedido con dirección y total."],
              ["Tú apruebas", "El pedido llega a tu bandeja con el resumen completo. Lo apruebas, lo editas o lo rechazas con motivo, desde el celular o la computadora."],
              ["El cliente recibe", "Cuando apruebas, el cliente recibe la confirmación por WhatsApp. Todo queda guardado en el registro del día."],
            ].map(([t, d]) => (
              <div key={t}>
                <h3 className="text-lg font-semibold text-emerald-800">{t}</h3>
                <p className="mt-2 text-sm leading-relaxed text-stone-600">{d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t">
        <div className="mx-auto max-w-6xl px-6 py-20 text-center">
          <h2 className="text-3xl font-bold tracking-tight">Deja que Sabi venda por ti, sin soltar el control</h2>
          <p className="mx-auto mt-4 max-w-xl text-stone-600">
            Piloto para 1 a 3 restaurantes. Menú cargado, número de WhatsApp y listo.
          </p>
          <Link href="/login" className="mt-8 inline-block rounded-lg bg-emerald-700 px-8 py-3 font-medium text-white hover:bg-emerald-800">
            Entrar al panel
          </Link>
        </div>
      </section>
    </div>
  );
}
