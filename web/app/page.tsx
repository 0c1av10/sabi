import Link from "next/link";
import Phone, { Msg } from "../components/Phone";
import RevealObserver from "../components/RevealObserver";
import { WhatsAppLogo, MetaLogo } from "../components/Brand";
import { usd, eur, bs } from "../lib/money";

const R = { usd: 36.5, eur: 39.6 };
const m = (v: number) => `${usd(v)} · ${eur(v, R)} · ${bs(v, R)}`;

const heroChat: Msg[] = [
  { who: "c", text: "Hola! qué me recomiendas para 2?", time: "21:02" },
  { who: "s", text: `La milanesa napolitana es la favorita de la casa: salsa, mozzarella y guarnición, ${m(4.5)}. ¿Te anoto 2?`, time: "21:02" },
  { who: "c", text: "Dale, 2 milanesas y una gaseosa", time: "21:03" },
  { who: "s", text: `¿Les sumo un flan casero de postre? ${m(1.5)}`, time: "21:03" },
  { who: "c", text: "Sí, súmalo. Delivery a Chacao", time: "21:04" },
  { who: "s", text: "Total: $11,70 · €10,78 · Bs 427,05\n¿Está correcto?", time: "21:04" },
];

const demos: { title: string; desc: string; from: string; result: string; gain?: number; msgs: Msg[]; footer?: React.ReactNode }[] = [
  {
    title: "Upselling",
    desc: "Sabi ofrece la versión más completa del plato cuando vale la pena.",
    from: "$7,60",
    result: "$9,00 · +$1,40",
    gain: 1.4,
    msgs: [
      { who: "c", text: "Quiero 2 hamburguesas completas", time: "13:10" },
      { who: "s", text: `¡Buena elección! Por ${usd(0.7)} más cada una (${bs(0.7, R)}), la milanesa napolitana viene con salsa, mozzarella y guarnición incluida. ¿Te las cambio?`, time: "13:10" },
      { who: "c", text: "Sí, mejor las milanesas", time: "13:11" },
      { who: "s", text: "Listo: 2 x Milanesa napolitana.\nTotal: $9,00 · €8,30 · Bs 328,50", time: "13:11" },
    ],
  },
  {
    title: "Cross-selling",
    desc: "Sugiere lo que combina con el pedido: la bebida, la entrada o el postre.",
    from: "$3,60",
    result: "$4,80 · +$1,20",
    gain: 1.2,
    msgs: [
      { who: "c", text: "Una docena de empanadas para retirar", time: "19:42" },
      { who: "s", text: `Anotado. ¿Le sumamos una Gaseosa 1.5L bien fría para acompañar? ${m(1.2)}`, time: "19:42" },
      { who: "c", text: "Dale", time: "19:43" },
      { who: "s", text: "1 x Empanadas de carne (docena)\n1 x Gaseosa 1.5L\nTotal: $4,80 · €4,42 · Bs 175,20", time: "19:43" },
    ],
  },
  {
    title: "Reservas",
    desc: "El cliente pide mesa por el mismo chat y tú la apruebas. Llega con el piloto.",
    from: "Mesa vacía",
    result: "Mesa para 4",
    msgs: [
      { who: "c", text: "Tienen mesa para 4 el sábado a las 9pm?", time: "16:20" },
      { who: "s", text: "Sí, hay mesa para 4 el sábado a las 21:00. ¿A nombre de quién la anoto?", time: "16:20" },
      { who: "c", text: "Andrea", time: "16:21" },
      { who: "s", text: "Perfecto, Andrea: mesa para 4, sábado 21:00. Te confirmo apenas el local la apruebe.", time: "16:21" },
    ],
    footer: <div className="ml-auto w-fit rounded-full bg-[#075E54] px-3 py-1.5 text-[11px] font-medium text-white">Reserva enviada al dueño</div>,
  },
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

const faqs: [string, string][] = [
  ["¿Necesito otro número de WhatsApp?", "Sabi funciona con la API oficial de WhatsApp Business de Meta. Puedes usar un número nuevo para pedidos o el del local; en el piloto te ayudamos a elegir y a dejarlo configurado."],
  ["¿La IA puede inventar precios o promociones?", "No. Sabi solo vende lo que está en tu menú, con tus precios, y no inventa descuentos. Además, ningún pedido se confirma sin tu aprobación."],
  ["¿Cómo apruebo los pedidos?", "Cada pedido llega a la bandeja de tu panel con ítems, total, tipo de entrega y dirección. Lo apruebas, lo editas o lo rechazas con un motivo, y solo entonces el cliente recibe la respuesta por WhatsApp."],
  ["¿Qué pasa si el cliente quiere hablar con una persona?", "Si el cliente pide algo fuera del menú o prefiere hablar contigo, Sabi se lo dice y te pasa la conversación."],
  ["¿Cómo maneja dólares, euros y bolívares?", "Cargas el menú en dólares y pones las tasas BCV del día en Configuración. Sabi muestra cada precio y cada total en las tres monedas."],
  ["¿Toma reservas y se conecta con mi POS?", "Las reservas por WhatsApp y la conexión con tu POS llegan con el piloto. Hoy Sabi toma pedidos de delivery y retiro."],
  ["¿Qué necesito para empezar?", "Tu menú con precios, tus horarios y un número de WhatsApp. Estamos abriendo el piloto para 1 a 3 restaurantes."],
];

export default function Landing() {
  return (
    <div className="relative overflow-hidden bg-[#04140f] text-white">
      <div className="grain" aria-hidden="true" />
      <RevealObserver />
      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="blob pointer-events-none absolute -left-32 -top-32 h-[28rem] w-[28rem] rounded-full bg-[#25D366]/30 blur-3xl" />
        <div className="blob pointer-events-none absolute -bottom-40 right-0 h-[30rem] w-[30rem] rounded-full bg-emerald-400/20 blur-3xl" style={{ animationDelay: "-7s" }} />
        <div className="relative mx-auto grid max-w-6xl gap-12 px-6 pb-24 pt-36 md:grid-cols-[1.1fr_1fr] md:items-center">
          <div>
            <div className="flex items-center gap-4 text-sm text-emerald-100/90">
              <span className="flex items-center gap-2"><WhatsAppLogo className="h-6 w-6" />WhatsApp</span>
              <span className="h-4 w-px bg-white/20" />
              <span className="flex items-center gap-2"><MetaLogo className="h-6 w-6" />API oficial de Meta</span>
            </div>
            <h1 className="mt-8 text-4xl font-bold leading-[1.05] tracking-tight text-balance md:text-6xl">
              Tu mejor vendedor, atendiendo <span className="text-[#25D366]">WhatsApp</span> las 24 horas
            </h1>
            <p className="mt-6 max-w-xl text-lg text-emerald-50/80">
              Tu cliente ordena, pregunta y reserva desde WhatsApp. Sabi recomienda, sube el ticket con
              la sugerencia justa y cierra el pedido. Tú apruebas cada uno antes de que se confirme.
            </p>
            <div className="mt-9 flex flex-wrap gap-3">
              <Link href="/login" className="rounded-full bg-[#25D366] px-7 py-3 font-semibold text-[#06281e] shadow-lg shadow-[#25D366]/30 transition duration-200 hover:scale-[1.03] active:scale-[0.98]">
                Probar el panel
              </Link>
              <a href="#ventas" className="rounded-full border border-white/25 px-7 py-3 font-medium text-white transition duration-200 hover:bg-white/10 active:scale-[0.98]">
                Ver cómo vende
              </a>
            </div>
          </div>
          <div className="flex justify-center md:justify-end">
            <Phone animate height={640} msgs={heroChat}
              footer={<div className="ml-auto w-fit rounded-full bg-[#075E54] px-3 py-1.5 text-[11px] font-medium text-white">Pedido enviado al dueño · pendiente de aprobación</div>} />
          </div>
        </div>
      </section>

      {/* Metrics strip */}
      <section className="border-y border-white/[0.06] bg-white/[0.02]">
        <div className="mx-auto grid max-w-6xl grid-cols-1 gap-8 px-6 py-10 text-center md:grid-cols-3">
          {[["24 h", "Atención todos los días"],
            ["100%", "Pedidos que pasan por tu aprobación"],
            ["0", "Pedidos confirmados sin tu ok"]].map(([n, l]) => (
            <div key={l}>
              <p className="text-4xl font-bold tabular-nums tracking-tight">{n}</p>
              <p className="mt-1 text-sm text-emerald-50/60">{l}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Problem */}
      <section className="relative">
        <div className="pointer-events-none absolute left-1/2 top-10 h-[26rem] w-[40rem] -translate-x-1/2 rounded-full bg-red-500/[0.07] blur-3xl" />
        <div className="reveal relative mx-auto max-w-6xl px-6 py-28 text-center">
          <svg viewBox="0 0 200 200" className="mx-auto h-52 w-52 drop-shadow-[0_20px_40px_rgba(239,68,68,0.15)]" aria-hidden="true">
            <path d="M100 100 L176.08 75.28 A80 80 0 1 1 100 20 Z" fill="#1f4b5c" />
            <path d="M105.88 91.91 L105.88 11.91 A80 80 0 0 1 181.96 67.19 Z" fill="#ef4444" className="pie-slice" />
          </svg>
          <p className="mt-8 text-4xl font-bold tabular-nums tracking-tight md:text-5xl">20% de las reservas</p>
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
      <section className="reveal mx-auto max-w-6xl px-6 py-28">
        <h2 className="text-3xl font-bold tracking-tight text-balance">Un agente que vende, no un chatbot que contesta</h2>
        <p className="mt-3 max-w-2xl text-emerald-50/70">
          Sabi conversa como tu mejor mesonero: conoce el menú, recomienda y cierra la venta. Tú tienes la última palabra.
        </p>
        <div className="mt-14 grid gap-x-16 gap-y-12 md:grid-cols-2">
          {features.map((f) => (
            <div key={f.title} className="border-t border-white/10 pt-6">
              <h3 className="text-xl font-semibold tracking-tight">{f.title}</h3>
              <p className="mt-3 max-w-[60ch] leading-relaxed text-emerald-50/70">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Upsell / cross-sell / reservas */}
      <section id="ventas" className="relative overflow-hidden">
        <div className="pointer-events-none absolute -right-40 top-40 h-[32rem] w-[32rem] rounded-full bg-[#25D366]/[0.12] blur-3xl" />
        <div className="reveal relative mx-auto max-w-6xl px-6 py-28">
          <h2 className="max-w-2xl text-3xl font-bold tracking-tight text-balance md:text-4xl">Lo que Sabi vende por ti mientras atiendes el local</h2>
          <p className="mt-4 max-w-2xl text-emerald-50/70">
            Conversaciones de prueba con el menú de La Esquina. Cada sugerencia sale de tu carta y tus precios, una sola vez y sin presionar.
          </p>
          <div className="mt-14 grid justify-items-center gap-14 lg:grid-cols-3">
            {demos.map((d) => (
              <div key={d.title} className="flex flex-col items-center">
                <Phone msgs={d.msgs} footer={d.footer} />
                <div className="mt-8 w-[300px]">
                  <h3 className="text-xl font-bold">{d.title}</h3>
                  <p className="mt-1 text-sm text-emerald-50/70">{d.desc}</p>
                  <p className="mt-3 text-sm"><span className="text-emerald-50/50">{d.from}</span> <span className="text-emerald-50/40">→</span> <span className="text-lg font-bold text-[#25D366]">{d.result}</span></p>
                  {d.gain && <p className="mt-1 text-xs text-emerald-50/50">Suma {m(d.gain)} en cada pedido</p>}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Owner panel */}
      <section className="relative">
        <div className="pointer-events-none absolute left-0 top-1/3 h-[30rem] w-[30rem] rounded-full bg-emerald-400/[0.10] blur-3xl" />
        <div className="reveal relative mx-auto max-w-6xl px-6 py-28">
          <h2 className="max-w-2xl text-3xl font-bold tracking-tight text-balance md:text-4xl">Tu panel de empresario</h2>
          <p className="mt-4 max-w-2xl text-emerald-50/80">
            Desde el celular o la computadora ves lo que entra, apruebas con un toque y sabes cuánto vendiste hoy.
          </p>
          <div className="bezel mt-12"><div className="overflow-hidden rounded-[calc(2rem-0.375rem)] bg-stone-50 text-stone-900 shadow-[0_40px_80px_-20px_rgba(37,211,102,0.18)]">
            <div className="flex items-center gap-2 border-b bg-white px-4 py-2.5">
              <span className="h-3 w-3 rounded-full bg-red-400" /><span className="h-3 w-3 rounded-full bg-amber-400" /><span className="h-3 w-3 rounded-full bg-emerald-400" />
              <span className="ml-4 rounded-md bg-stone-100 px-3 py-1 text-xs text-stone-500">sabi-ecru.vercel.app/pedidos</span>
            </div>
            <div className="flex items-center gap-6 border-b bg-white px-6 py-3 text-sm">
              <span className="font-bold text-emerald-700">Sabi</span>
              <span className="hidden rounded-full bg-emerald-50 px-3 py-1 text-xs text-emerald-800 md:inline">Tasa BCV hoy: $1 = Bs 36,50 · €1 = Bs 39,60</span>
              <span className="ml-auto font-medium text-stone-900">Pedidos</span>
              <span className="text-stone-500">Menú</span><span className="text-stone-500">Registro</span><span className="text-stone-500">Configuración</span>
            </div>
            <div className="grid gap-6 p-6 lg:grid-cols-[1.4fr_1fr]">
              <div className="space-y-4">
                <div className="grid grid-cols-4 gap-3">
                  {[["8", "Pedidos hoy"], ["6", "Aprobados"], ["1", "Rechazado"], ["1", "Pendiente"]].map(([n, l]) => (
                    <div key={l} className="rounded-xl border bg-white p-3 text-center">
                      <p className="text-2xl font-bold">{n}</p><p className="text-[11px] text-stone-500">{l}</p>
                    </div>
                  ))}
                </div>
                <div className="rounded-xl border-2 border-amber-300 bg-white p-4">
                  <div className="flex items-center justify-between">
                    <p className="font-semibold">Pedido #9 · Lucía R.</p>
                    <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-800">Pendiente</span>
                  </div>
                  <ul className="mt-3 space-y-1 text-sm text-stone-700">
                    <li className="flex justify-between"><span>2 x Milanesa napolitana</span><span className="text-right">$9,00<span className="block text-[11px] text-stone-400">{eur(9, R)} · {bs(9, R)}</span></span></li>
                    <li className="flex justify-between"><span>1 x Gaseosa 1.5L</span><span className="text-right">$1,20<span className="block text-[11px] text-stone-400">{eur(1.2, R)} · {bs(1.2, R)}</span></span></li>
                    <li className="flex justify-between"><span>1 x Flan con dulce de leche <span className="ml-1 rounded bg-emerald-100 px-1.5 text-[10px] font-medium text-emerald-800">sugerido por Sabi</span></span><span className="text-right">$1,50<span className="block text-[11px] text-stone-400">{eur(1.5, R)} · {bs(1.5, R)}</span></span></li>
                  </ul>
                  <p className="mt-2 text-xs text-stone-500">Delivery · Av. Francisco de Miranda, Chacao</p>
                  <p className="mt-3 border-t pt-3 text-sm font-semibold">Total: $11,70 · €10,78 · Bs 427,05</p>
                  <div className="mt-4 flex gap-2">
                    <span className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-medium text-white">Aprobar</span>
                    <span className="rounded-lg border px-4 py-2 text-sm">Editar</span>
                    <span className="rounded-lg border px-4 py-2 text-sm text-red-600">Rechazar</span>
                  </div>
                </div>
              </div>
              <div className="rounded-xl border bg-white p-5">
                <p className="font-semibold">Copiloto</p>
                <div className="mt-4 space-y-4 text-sm">
                  <div><p className="text-xs text-stone-500">Ticket promedio</p><p className="text-2xl font-bold">$9,85</p><p className="text-xs text-stone-500">€9,08 · Bs 359,52</p></div>
                  <div><p className="text-xs text-stone-500">Lo más pedido</p><p className="font-semibold">Milanesa napolitana · 11 unidades</p></div>
                  <div><p className="text-xs text-stone-500">Qué conviene ofrecer</p><p>Solo 2 de 7 pedidos llevaron postre. Sabi ya ofrece el flan; destácalo en tu historia de hoy.</p></div>
                  <div className="rounded-lg bg-stone-100 px-3 py-2 text-xs text-stone-600">Tu link de pedidos: wa.me/laesquina</div>
                </div>
              </div>
            </div>
          </div></div>
        </div>
      </section>

      {/* WhatsApp link + ticket */}
      <section className="border-t border-white/[0.06]">
        <div className="reveal mx-auto grid max-w-6xl gap-12 px-6 py-28 md:grid-cols-2 md:items-center">
          <div>
            <h2 className="text-3xl font-bold tracking-tight text-balance md:text-4xl">Tu cliente ya está en WhatsApp</h2>
            <p className="mt-4 text-emerald-50/70">
              Un solo link en tu Instagram, en Google Maps o en un QR sobre la mesa abre el chat con Sabi.
              Sin bajar apps, sin registrarse, sin formularios.
            </p>
            <p className="mt-4 text-emerald-50/70">
              Menos pasos es más pedidos cerrados. Y como Sabi sugiere la bebida o el postre que falta,
              cada pedido sale con un ticket más alto.
            </p>
            <h3 className="mt-10 text-lg font-semibold">Conexión con tu POS y tu sistema, sin fricción</h3>
            <p className="mt-2 text-emerald-50/70">
              Los pedidos aprobados pasan a tu caja sin volver a tipearlos. Llega con el piloto.
            </p>
          </div>

          <div className="space-y-4">
            <div className="bezel"><div className="bezel-core p-5">
              <div className="flex items-center gap-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-tr from-amber-400 via-rose-500 to-fuchsia-600 p-[2px]">
                  <div className="flex h-full w-full items-center justify-center rounded-full bg-[#04140f] text-sm font-bold text-white">LE</div>
                </div>
                <div>
                  <p className="text-sm font-semibold">laesquina.ccs</p>
                  <p className="text-xs text-emerald-50/50">Milanesas, empanadas y flan casero · Chacao</p>
                </div>
              </div>
              <div className="mt-4 flex items-center justify-between rounded-xl bg-[#25D366] px-4 py-3 text-white">
                <span className="text-sm font-medium">Pide por WhatsApp</span>
                <span className="text-xs opacity-90">wa.me/laesquina</span>
              </div>
            </div></div>

            <div className="bezel"><div className="bezel-core p-5">
              <div className="flex items-baseline justify-between text-sm">
                <span className="text-emerald-50/70">Lo que el cliente pidió</span>
                <span className="font-medium">$10,20</span>
              </div>
              <div className="mt-2 h-2 rounded-full bg-white/10">
                <div className="h-2 rounded-full bg-white/40" style={{ width: "87%" }} />
              </div>
              <div className="mt-5 flex items-baseline justify-between text-sm">
                <span className="text-emerald-50/70">Con el flan que sugirió Sabi</span>
                <span className="font-semibold text-[#25D366]">$11,70</span>
              </div>
              <div className="mt-2 h-2 rounded-full bg-white/10">
                <div className="h-2 rounded-full bg-[#25D366] shadow-[0_0_20px_rgba(37,211,102,0.5)]" style={{ width: "100%" }} />
              </div>
              <p className="mt-4 text-xs text-emerald-50/50">Mismo cliente, misma conversación: 15% más de ticket.</p>
            </div></div>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="como-funciona" className="border-t border-white/[0.06] bg-white/[0.02]">
        <div className="reveal mx-auto max-w-6xl px-6 py-28">
          <h2 className="text-3xl font-bold tracking-tight text-balance md:text-4xl">Así funciona</h2>
          <div className="mt-10 grid gap-8 md:grid-cols-3">
            {[
              ["Sabi asesora", "El cliente escribe por WhatsApp como siempre. Sabi le recomienda, le sugiere qué sumar y arma el pedido con dirección y total."],
              ["Tú apruebas", "El pedido llega a tu bandeja con el resumen completo. Lo apruebas, lo editas o lo rechazas con motivo, desde el celular o la computadora."],
              ["El cliente recibe", "Cuando apruebas, el cliente recibe la confirmación por WhatsApp. Todo queda guardado en el registro del día."],
            ].map(([t, d]) => (
              <div key={t}>
                <h3 className="text-lg font-semibold text-[#25D366]">{t}</h3>
                <p className="mt-2 text-sm leading-relaxed text-emerald-50/70">{d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="border-t border-white/[0.06]">
        <div className="reveal mx-auto grid max-w-6xl gap-12 px-6 py-28 md:grid-cols-[1fr_2fr]">
          <div className="md:sticky md:top-10 md:self-start">
            <h2 className="text-3xl font-bold tracking-tight text-balance md:text-4xl">Preguntas frecuentes</h2>
            <p className="mt-4 text-emerald-50/70">Lo que nos preguntan los dueños antes de dejar que Sabi venda por ellos.</p>
          </div>
          <dl className="divide-y divide-white/10">
            {faqs.map(([q, a]) => (
              <div key={q} className="py-6 first:pt-0">
                <dt className="text-lg font-semibold tracking-tight">{q}</dt>
                <dd className="mt-2 max-w-[62ch] leading-relaxed text-emerald-50/70">{a}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      {/* CTA */}
      <section className="relative border-t border-white/[0.06]">
        <div className="pointer-events-none absolute left-1/2 top-1/2 h-[24rem] w-[44rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[#25D366]/[0.14] blur-3xl" />
        <div className="reveal relative mx-auto max-w-6xl px-6 py-32 text-center">
          <h2 className="text-3xl font-bold tracking-tight text-balance">Deja que Sabi venda por ti, sin soltar el control</h2>
          <p className="mx-auto mt-4 max-w-xl text-emerald-50/70">
            Piloto para 1 a 3 restaurantes. Menú cargado, número de WhatsApp y listo.
          </p>
          <Link href="/login" className="mt-10 inline-block rounded-full bg-[#25D366] px-8 py-3.5 font-semibold text-[#04140f] shadow-lg shadow-[#25D366]/30 transition duration-300 ease-[cubic-bezier(.32,.72,0,1)] hover:scale-[1.03] active:scale-[0.98]">
            Entrar al panel
          </Link>
        </div>
      </section>
    </div>
  );
}
