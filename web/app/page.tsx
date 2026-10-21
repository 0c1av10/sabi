import Link from "next/link";
import Phone, { Msg } from "../components/Phone";
import RevealObserver from "../components/RevealObserver";
import Mascot from "../components/Mascot";
import CreateStore from "../components/CreateStore";
import { WhatsAppLogo, MetaLogo } from "../components/Brand";
import { usd, eur, bs, type Rates } from "../lib/money";

export const revalidate = 3600;

const FALLBACK = { usd: 875.65, eur: 980.61, fecha: "2026-10-09" };
let R: Rates = FALLBACK;
let bcvDate = FALLBACK.fecha;

async function bcvRates() {
  try {
    const [u, e] = await Promise.all(["dolares", "euros"].map((k) =>
      fetch(`https://ve.dolarapi.com/v1/${k}/oficial`, { next: { revalidate: 3600 } }).then((r) => r.json())));
    const round = (v: number) => Math.round(v * 100) / 100;
    if (!u.promedio || !e.promedio) return FALLBACK;
    return { usd: round(u.promedio), eur: round(e.promedio), fecha: String(u.fechaActualizacion).slice(0, 10) };
  } catch {
    return FALLBACK;
  }
}
const m = (v: number) => `${usd(v)} · ${eur(v, R)} · ${bs(v, R)}`;

const heroChat = (): Msg[] => [
  { who: "c", text: "Hola! qué me recomiendas para 2?", time: "21:02" },
  { who: "s", text: `El pollo entero a la brasa es la especialidad de la casa y alcanza para 2: ${m(21)}. ¿Te lo anoto?`, time: "21:02" },
  { who: "c", text: "Dale, el pollo y 2 papelones con limón", time: "21:03" },
  { who: "s", text: `¿Les sumo un quesillo casero de postre? ${m(5)}`, time: "21:03" },
  { who: "c", text: "Sí, súmalo. Delivery en Lechería", time: "21:04" },
  { who: "s", text: `Total: ${m(31)}\n¿Está correcto?`, time: "21:04" },
];

const demos = (): { title: string; desc: string; from: string; result: string; gain?: number; msgs: Msg[]; footer?: React.ReactNode }[] => [
  {
    title: "Upselling",
    desc: "Sabi ofrece la versión más completa del plato cuando vale la pena.",
    from: "$11,00",
    result: "$21,00 · +$10,00",
    gain: 10,
    msgs: [
      { who: "c", text: "Quiero un medio pollo a la brasa", time: "13:10" },
      { who: "s", text: `¡Buena elección! Por ${usd(10)} más (${eur(10, R)} · ${bs(10, R)}) te llevas el pollo entero: el doble de pollo. ¿Te lo cambio?`, time: "13:10" },
      { who: "c", text: "Sí, mejor el entero", time: "13:11" },
      { who: "s", text: `Listo: 1 x Pollo entero a la brasa.\nTotal: ${m(21)}`, time: "13:11" },
    ],
  },
  {
    title: "Cross-selling",
    desc: "Sugiere lo que combina con el pedido: la bebida, la entrada o el postre.",
    from: "$6,00",
    result: "$8,50 · +$2,50",
    gain: 2.5,
    msgs: [
      { who: "c", text: "Unos tequeños para retirar", time: "19:42" },
      { who: "s", text: `Anotado. ¿Le sumamos un papelón con limón bien frío para acompañar? ${m(2.5)}`, time: "19:42" },
      { who: "c", text: "Dale", time: "19:43" },
      { who: "s", text: `1 x Tequeños\n1 x Papelón con limón\nTotal: ${m(8.5)}`, time: "19:43" },
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

const ticketChat = (): Msg[] => [
  { who: "c", text: "Hola, quiero entradas para un concierto en Caracas", time: "18:30" },
  { who: "s", text: "Soy Sabi 👋 Encontré 1 evento en Caracas: Noches de Araguaney (demo), sáb 14 nov, 8:00 pm. ¿Te muestro las zonas?", time: "18:30" },
  { who: "c", text: "Sí", time: "18:31" },
  { who: "s", text: "General: $25,00 · disponible\nVIP: $60,00 · por confirmar\nPrecios orientativos; cargos adicionales por verificar.", time: "18:31" },
  { who: "c", text: "2 generales", time: "18:32" },
  { who: "s", text: "Subtotal orientativo: $50,00 (2 x General). Esto no reserva tus entradas: la disponibilidad final y el pago se ven en el sitio oficial de TuEntradaWeb.", time: "18:32" },
];

const ticketSteps: [string, string][] = [
  ["Encuentra el evento", "Pregunta por ciudad, artista o fecha. Sabi muestra solo eventos activos y nunca recomienda una zona agotada."],
  ["Arma la selección", "Zonas, cantidad y subtotal orientativo en su moneda. Si un precio no se verificó hace poco, lo dice."],
  ["Compra en el sitio oficial", "Sabi entrega el enlace oficial de TuEntradaWeb. El pago ocurre allí, nunca dentro del chat."],
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
    desc: "Cargas el menú en dólares y Sabi toma la tasa oficial del BCV cada día. Luego le da a cada cliente el precio en las tres monedas, sin cuentas a mano ni tasas viejas.",
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
  ["¿Cómo maneja dólares, euros y bolívares?", "Cargas el menú en dólares y Sabi actualiza solo la tasa oficial del BCV del dólar y del euro. Si prefieres otra tasa, la pones a mano en Configuración. Cada precio y cada total sale en las tres monedas."],
  ["¿Toma reservas y se conecta con mi POS?", "Las reservas por WhatsApp y la conexión con tu POS llegan con el piloto. Hoy Sabi toma pedidos de delivery y retiro."],
  ["¿Sabi vende entradas para eventos?", "Sabi te ayuda a encontrar el evento, comparar zonas y calcular un subtotal orientativo, y te entrega el enlace oficial de compra. El pago ocurre en la plataforma oficial; Sabi no cobra ni guarda datos de tarjetas. Hoy es una demo independiente, sin integración oficial con TuEntradaWeb."],
  ["¿Sabi reserva o confirma mis entradas?", "No. Elegir zona y cantidad no reserva nada y abrir el enlace tampoco es una compra. Si dices «ya pagué», Sabi lo registra como reportado y una persona autorizada lo revisa antes de confirmarlo."],
  ["¿Qué necesito para empezar?", "Tu menú con precios, tus horarios y un número de WhatsApp. Estamos abriendo el piloto para 1 a 3 restaurantes."],
];

export default async function Landing() {
  const rates = await bcvRates();
  R = rates;
  bcvDate = rates.fecha;
  const bcvLine = `BCV ${bcvDate.split("-").reverse().join("/")}: $1 = ${bs(1, R)} · €1 = ${bs(R.eur / R.usd, R)}`;
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
              Tu cliente ordena, pregunta, reserva o busca entradas desde WhatsApp. Sabi recomienda, sube el ticket con
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
          <div className="relative flex justify-center md:justify-end">
            <div className="absolute -top-20 right-0 z-10 flex flex-col items-end gap-1 sm:right-4 xl:-right-36 xl:top-16">
              <span className="msg-in mr-10 rounded-2xl rounded-br-sm bg-white px-3 py-2 text-xs font-medium text-stone-800 shadow-lg" style={{ animationDelay: ".4s" }}>¡Hola! Soy Sabi</span>
              <Mascot className="w-24 md:w-32" />
            </div>
            <Phone animate height={640} msgs={heroChat()}
              footer={<div className="ml-auto w-fit rounded-full bg-[#075E54] px-3 py-1.5 text-[11px] font-medium text-white">Pedido enviado al dueño · pendiente de aprobación</div>} />
            <div className="absolute -left-4 bottom-16 hidden w-64 -rotate-3 lg:block xl:-left-16">
              <div className="msg-in" style={{ animationDelay: "6.6s" }}>
                <div className="bezel"><div className="rounded-[calc(2rem-0.375rem)] bg-white p-4 text-stone-900 shadow-[0_30px_60px_-15px_rgba(0,0,0,0.7)]">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-semibold">Nuevo pedido · Lucía R.</p>
                    <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-800">Pendiente</span>
                  </div>
                  <p className="mt-2 text-2xl font-bold tabular-nums tracking-tight">{usd(31)}</p>
                  <p className="text-[11px] text-stone-500">{eur(31, R)} · {bs(31, R)} · Delivery</p>
                  <div className="mt-3 flex gap-2 text-xs">
                    <span className="rounded-full bg-emerald-700 px-4 py-1.5 font-medium text-white">Aprobar</span>
                    <span className="rounded-full border border-stone-200 px-4 py-1.5">Editar</span>
                  </div>
                </div></div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Problem */}
      <section className="relative border-t border-white/[0.06]">
        <div className="pointer-events-none absolute -left-20 top-20 h-[26rem] w-[30rem] rounded-full bg-red-500/[0.08] blur-3xl" />
        <div className="reveal relative mx-auto grid max-w-6xl items-center gap-14 px-6 py-28 md:grid-cols-[1fr_1.1fr]">
          <div>
            <svg viewBox="0 0 200 200" className="h-48 w-48 drop-shadow-[0_20px_40px_rgba(239,68,68,0.18)] md:h-56 md:w-56" aria-hidden="true">
              <path d="M100 100 L176.08 75.28 A80 80 0 1 1 100 20 Z" fill="#1f4b5c" />
              <path d="M105.88 91.91 L105.88 11.91 A80 80 0 0 1 181.96 67.19 Z" fill="#ef4444" className="pie-slice" />
            </svg>
            <p className="mt-10 text-5xl font-bold tabular-nums tracking-tight md:text-6xl">20% de las reservas</p>
            <p className="mt-2 text-2xl text-emerald-50/70 md:text-3xl">se pierden por responder tarde</p>
          </div>
          <ul className="divide-y divide-white/10 border-y border-white/10">
            {pains.map(([icon, text]) => (
              <li key={text} className="flex items-center gap-5 py-6">
                <svg viewBox="0 0 24 24" className="h-6 w-6 shrink-0 text-red-400" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d={icon} />
                </svg>
                <span className="text-xl font-medium tracking-tight">{text}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* Features bento */}
      <section className="reveal mx-auto max-w-6xl px-6 py-28">
        <div className="grid gap-6 md:grid-cols-2 md:items-end">
          <h2 className="text-3xl font-bold tracking-tight text-balance md:text-5xl">Un agente que vende, no un chatbot que contesta</h2>
          <p className="max-w-md text-emerald-50/70 md:justify-self-end">
            Sabi conversa como tu mejor mesonero: conoce el menú, recomienda y cierra la venta. Tú tienes la última palabra.
          </p>
        </div>
        <div className="mt-14 grid gap-4 md:grid-cols-6">
          <div className="bezel h-full md:col-span-4 md:row-span-2"><div className="bezel-core flex h-full flex-col p-7">
            <h3 className="text-2xl font-semibold tracking-tight">Asesora y vende, no solo responde</h3>
            <p className="mt-3 max-w-[52ch] leading-relaxed text-emerald-50/70">{features[0].desc}</p>
            <div className="mt-auto space-y-2 pt-10 text-sm">
              <p className="ml-auto w-fit max-w-[80%] rounded-2xl rounded-br-md bg-[#d9fdd3] px-4 py-2.5 text-stone-900">¿Qué tienen para compartir?</p>
              <p className="w-fit max-w-[85%] rounded-2xl rounded-bl-md bg-white px-4 py-2.5 text-stone-900">Los tequeños, {m(6)} los 5, o los tostones playeros, {m(5)}. ¿Te sumo un papelón con limón?</p>
              <p className="ml-auto w-fit rounded-2xl rounded-br-md bg-[#d9fdd3] px-4 py-2.5 text-stone-900">Dale, tequeños y papelón</p>
            </div>
          </div></div>
          <div className="bezel h-full md:col-span-2"><div className="bezel-core flex h-full flex-col p-7">
            <h3 className="text-xl font-semibold tracking-tight">Tú apruebas cada pedido</h3>
            <p className="mt-2 text-sm leading-relaxed text-emerald-50/70">Nada se confirma solo. Apruebas, editas o rechazas con un toque.</p>
            <div className="mt-auto flex flex-wrap gap-2 pt-6 text-sm">
              <span className="rounded-full bg-[#25D366] px-4 py-1.5 font-semibold text-[#04140f]">Aprobar</span>
              <span className="rounded-full border border-white/15 px-4 py-1.5">Editar</span>
              <span className="rounded-full border border-white/15 px-4 py-1.5 text-red-300">Rechazar</span>
            </div>
          </div></div>
          <div className="bezel h-full md:col-span-2"><div className="bezel-core flex h-full flex-col p-7">
            <p className="text-6xl font-bold tabular-nums tracking-tight text-[#25D366]">24 h</p>
            <h3 className="mt-3 text-xl font-semibold tracking-tight">Cierra el pedido completo</h3>
            <p className="mt-2 text-sm leading-relaxed text-emerald-50/70">Ítems, extras, delivery o retiro, dirección y total. También con el local cerrado.</p>
          </div></div>
          <div className="bezel h-full md:col-span-3"><div className="bezel-core flex h-full flex-col p-7">
            <h3 className="text-xl font-semibold tracking-tight">Dólares, euros y bolívares</h3>
            <p className="mt-2 text-sm leading-relaxed text-emerald-50/70">Cargas el menú en dólares. Sabi toma la tasa oficial del BCV del dólar y del euro cada día, sin que la copies a mano.</p>
            <p className="mt-3 text-xs font-medium text-[#25D366]">{bcvLine}</p>
            <dl className="mt-auto grid grid-cols-3 gap-3 pt-8">
              {[["Dólares", usd(31)], ["Euros", eur(31, R)], ["Bolívares", bs(31, R)]].map(([k, v]) => (
                <div key={k}>
                  <dd className="text-2xl font-bold tabular-nums tracking-tight">{v}</dd>
                  <dt className="mt-1 text-xs text-emerald-50/50">{k}</dt>
                </div>
              ))}
            </dl>
          </div></div>
          <div className="bezel h-full md:col-span-3"><div className="bezel-core flex h-full flex-col p-7">
            <h3 className="text-xl font-semibold tracking-tight">Un copiloto para ti</h3>
            <p className="mt-2 text-sm leading-relaxed text-emerald-50/70">Ticket promedio, lo más pedido y qué conviene ofrecer hoy, en tu panel.</p>
            <div className="mt-auto flex items-end justify-between gap-6 pt-8">
              <div>
                <p className="text-3xl font-bold tabular-nums tracking-tight">{usd(24.6)}</p>
                <p className="text-xs text-emerald-50/50">Ticket promedio de la semana</p>
              </div>
              <div className="flex h-16 items-end gap-1.5" aria-hidden="true">
                {[38, 52, 44, 61, 57, 73, 88].map((h, i) => (
                  <span key={i} style={{ height: `${h}%` }} className={`w-3 rounded-sm ${i === 6 ? "bg-[#25D366]" : "bg-white/20"}`} />
                ))}
              </div>
            </div>
          </div></div>
          <div className="bezel h-full md:col-span-6"><div className="bezel-core flex h-full flex-col gap-4 p-7 md:flex-row md:items-center md:justify-between">
            <div>
              <h3 className="text-xl font-semibold tracking-tight">Reservas sin cruces</h3>
              <p className="mt-2 max-w-xl text-sm leading-relaxed text-emerald-50/70">El cliente pide mesa por el mismo chat y Sabi la agenda según tus horarios y mesas libres.</p>
            </div>
            <span className="w-fit shrink-0 rounded-full border border-[#25D366]/40 px-4 py-1.5 text-sm text-[#25D366]">Llega con el piloto</span>
          </div></div>
        </div>
      </section>

      {/* Upsell / cross-sell / reservas */}
      <section id="ventas" className="relative overflow-hidden">
        <div className="pointer-events-none absolute -right-40 top-40 h-[32rem] w-[32rem] rounded-full bg-[#25D366]/[0.12] blur-3xl" />
        <div className="reveal relative mx-auto max-w-6xl px-6 py-28">
          <h2 className="max-w-2xl text-3xl font-bold tracking-tight text-balance md:text-4xl">Lo que Sabi vende por ti mientras atiendes el local</h2>
          <p className="mt-4 max-w-2xl text-emerald-50/70">
            Conversaciones de ejemplo con el menú de tu restaurante. Cada sugerencia sale de tu carta y tus precios, una sola vez y sin presionar.
          </p>
          <div className="mt-14 grid justify-items-center gap-14 lg:grid-cols-3">
            {demos().map((d, i) => (
              <div key={d.title} className={`flex flex-col items-center ${i === 1 ? "lg:-translate-y-10" : "lg:translate-y-6"}`}>
                <Phone msgs={d.msgs} footer={d.footer} className={i === 0 ? "lg:-rotate-2" : i === 2 ? "lg:rotate-2" : ""} />
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

      {/* Tickets / events */}
      <section id="entradas" className="relative overflow-hidden border-t border-white/[0.06]">
        <div className="pointer-events-none absolute -left-32 top-24 h-[28rem] w-[28rem] rounded-full bg-[#25D366]/[0.10] blur-3xl" />
        <div className="reveal relative mx-auto grid max-w-6xl gap-14 px-6 py-28 lg:grid-cols-[1fr_auto] lg:items-center">
          <div>
            <span className="rounded-full border border-[#25D366]/40 px-3 py-1 text-xs font-medium text-[#25D366]">Entradas y eventos</span>
            <h2 className="mt-5 max-w-xl text-3xl font-bold tracking-tight text-balance md:text-5xl">
              También vende entradas, hasta el enlace oficial de compra
            </h2>
            <p className="mt-5 max-w-xl text-emerald-50/70">
              Para productoras y eventos, el mismo número de WhatsApp atiende a quien pregunta por un concierto:
              busca el evento, compara zonas y prepara la selección. La compra se hace en la plataforma oficial.
            </p>
            <ol className="mt-10 space-y-6">
              {ticketSteps.map(([t, d], i) => (
                <li key={t} className="flex gap-4">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#25D366] text-sm font-bold text-[#04140f]">{i + 1}</span>
                  <div>
                    <h3 className="text-lg font-semibold tracking-tight">{t}</h3>
                    <p className="mt-1 max-w-[48ch] text-sm leading-relaxed text-emerald-50/70">{d}</p>
                  </div>
                </li>
              ))}
            </ol>
            <p className="mt-8 max-w-xl text-xs leading-relaxed text-emerald-50/50">
              Demo independiente: no es una integración oficial con TuEntradaWeb ni con la productora. Una selección no es una reserva,
              abrir el enlace no es una compra y un «ya pagué» no confirma nada hasta que lo revisa una persona autorizada.
            </p>
            <Link href="/eventos" className="mt-8 inline-block rounded-full bg-[#25D366] px-7 py-3 font-semibold text-[#06281e] shadow-lg shadow-[#25D366]/30 transition duration-200 hover:scale-[1.03] active:scale-[0.98]">
              Probar el asistente de eventos
            </Link>
          </div>
          <div className="flex justify-center">
            <Phone msgs={ticketChat()}
              footer={<div className="ml-auto w-fit rounded-full bg-[#075E54] px-3 py-1.5 text-[11px] font-medium text-white">Enlace oficial de TuEntradaWeb · el pago ocurre allí</div>} />
          </div>
        </div>
      </section>

      {/* Owner panel */}
      <section className="relative">
        <div className="pointer-events-none absolute left-0 top-1/3 h-[30rem] w-[30rem] rounded-full bg-emerald-400/[0.10] blur-3xl" />
        <div className="reveal relative mx-auto max-w-6xl px-6 py-28">
          <div className="grid gap-6 md:grid-cols-2 md:items-end">
            <h2 className="text-3xl font-bold tracking-tight text-balance md:text-5xl">Tu panel de empresario</h2>
            <p className="max-w-md text-emerald-50/70 md:justify-self-end">
              Desde el celular o la computadora ves lo que entra, apruebas con un toque y sabes cuánto vendiste hoy.
            </p>
          </div>
          <div className="bezel mt-12"><div className="overflow-hidden rounded-[calc(2rem-0.375rem)] bg-stone-50 text-stone-900 shadow-[0_40px_80px_-20px_rgba(37,211,102,0.18)]">
            <div className="flex items-center gap-2 border-b bg-white px-4 py-2.5">
              <span className="h-3 w-3 rounded-full bg-red-400" /><span className="h-3 w-3 rounded-full bg-amber-400" /><span className="h-3 w-3 rounded-full bg-emerald-400" />
              <span className="ml-4 rounded-md bg-stone-100 px-3 py-1 text-xs text-stone-500">holasabi.com/pedidos</span>
            </div>
            <div className="flex items-center gap-6 border-b bg-white px-6 py-3 text-sm">
              <span className="font-bold text-emerald-700">Sabi</span>
              <span className="hidden rounded-full bg-emerald-50 px-3 py-1 text-xs text-emerald-800 md:inline">Tasa {bcvLine}</span>
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
                    <li className="flex justify-between"><span>1 x Pollo entero a la brasa</span><span className="text-right">$21,00<span className="block text-[11px] text-stone-400">{eur(21, R)} · {bs(21, R)}</span></span></li>
                    <li className="flex justify-between"><span>2 x Papelón con limón</span><span className="text-right">$5,00<span className="block text-[11px] text-stone-400">{eur(5, R)} · {bs(5, R)}</span></span></li>
                    <li className="flex justify-between"><span>1 x Quesillo <span className="ml-1 rounded bg-emerald-100 px-1.5 text-[10px] font-medium text-emerald-800">sugerido por Sabi</span></span><span className="text-right">$5,00<span className="block text-[11px] text-stone-400">{eur(5, R)} · {bs(5, R)}</span></span></li>
                  </ul>
                  <p className="mt-2 text-xs text-stone-500">Delivery · Av. Principal de Lechería</p>
                  <p className="mt-3 border-t pt-3 text-sm font-semibold">Total: {m(31)}</p>
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
                  <div><p className="text-xs text-stone-500">Ticket promedio</p><p className="text-2xl font-bold">{usd(24.6)}</p><p className="text-xs text-stone-500">{eur(24.6, R)} · {bs(24.6, R)}</p></div>
                  <div><p className="text-xs text-stone-500">Lo más pedido</p><p className="font-semibold">Pollo entero a la brasa · 11 unidades</p></div>
                  <div><p className="text-xs text-stone-500">Qué conviene ofrecer</p><p>Solo 2 de 7 pedidos llevaron postre. Sabi ya ofrece el quesillo; destácalo en tu historia de hoy.</p></div>
                  <div className="rounded-lg bg-stone-100 px-3 py-2 text-xs text-stone-600">Tu link de pedidos: wa.me/laesquina</div>
                </div>
              </div>
            </div>
          </div></div>
        </div>
      </section>

      {/* WhatsApp link + ticket */}
      <section className="border-t border-white/[0.06]">
        <div className="reveal mx-auto grid max-w-6xl gap-14 px-6 py-28 md:grid-cols-[1fr_1.1fr] md:items-center">
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

          <div className="space-y-4 md:order-first md:-rotate-1">
            <div className="bezel"><div className="bezel-core p-5">
              <div className="flex items-center gap-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-tr from-amber-400 via-rose-500 to-fuchsia-600 p-[2px]">
                  <div className="flex h-full w-full items-center justify-center rounded-full bg-[#04140f] text-sm font-bold text-white">LE</div>
                </div>
                <div>
                  <p className="text-sm font-semibold">laesquina.lecheria</p>
                  <p className="text-xs text-emerald-50/50">Pollo a la brasa, cachapas y quesillo casero · Lechería</p>
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
                <span className="font-medium">$26,00</span>
              </div>
              <div className="mt-2 h-2 rounded-full bg-white/10">
                <div className="h-2 rounded-full bg-white/40" style={{ width: "84%" }} />
              </div>
              <div className="mt-5 flex items-baseline justify-between text-sm">
                <span className="text-emerald-50/70">Con el quesillo que sugirió Sabi</span>
                <span className="font-semibold text-[#25D366]">$31,00</span>
              </div>
              <div className="mt-2 h-2 rounded-full bg-white/10">
                <div className="h-2 rounded-full bg-[#25D366] shadow-[0_0_20px_rgba(37,211,102,0.5)]" style={{ width: "100%" }} />
              </div>
              <p className="mt-4 text-xs text-emerald-50/50">Mismo cliente, misma conversación: 19% más de ticket.</p>
            </div></div>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="como-funciona" className="border-t border-white/[0.06] bg-white/[0.02]">
        <div className="reveal mx-auto max-w-6xl px-6 py-28">
          <h2 className="text-3xl font-bold tracking-tight text-balance md:text-5xl">Así funciona</h2>
          <ol className="relative mt-14 grid gap-12 md:grid-cols-3 md:gap-10">
            <span className="absolute left-0 right-0 top-[7px] hidden h-px bg-gradient-to-r from-[#25D366]/70 via-white/15 to-[#25D366]/70 md:block" aria-hidden="true" />
            {[
              ["Sabi asesora", "El cliente escribe por WhatsApp como siempre. Sabi le recomienda, le sugiere qué sumar y arma el pedido con dirección y total."],
              ["Tú apruebas", "El pedido llega a tu bandeja con el resumen completo. Lo apruebas, lo editas o lo rechazas con motivo, desde el celular o la computadora."],
              ["El cliente recibe", "Cuando apruebas, el cliente recibe la confirmación por WhatsApp. Todo queda guardado en el registro del día."],
            ].map(([t, d]) => (
              <li key={t} className="relative">
                <span className="block h-[15px] w-[15px] rounded-full bg-[#25D366] shadow-[0_0_0_6px_rgba(37,211,102,0.15),0_0_24px_rgba(37,211,102,0.6)]" aria-hidden="true" />
                <h3 className="mt-6 text-2xl font-semibold tracking-tight">{t}</h3>
                <p className="mt-3 max-w-[38ch] leading-relaxed text-emerald-50/70">{d}</p>
              </li>
            ))}
          </ol>
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

      {/* Store onboarding */}
      <section id="tienda" className="relative overflow-hidden border-t border-white/[0.06]">
        <div className="pointer-events-none absolute -left-40 top-20 h-[26rem] w-[26rem] rounded-full bg-[#25D366]/[0.08] blur-3xl" />
        <div className="relative mx-auto grid max-w-6xl gap-12 px-6 py-28 lg:grid-cols-[0.9fr_1.1fr] lg:items-center">
          <div className="reveal">
            <h2 className="text-3xl font-bold tracking-tight text-balance md:text-4xl">Tu tienda online, armada con tu propia web</h2>
            <p className="mt-4 max-w-md text-emerald-50/70">
              Déjanos tu correo y tu página. Sabi lee tu carta, tu logo y tus colores y te arma una tienda con carrito,
              delivery o retiro y precios en $, € y Bs. Cada pedido cae en tu panel y lo apruebas tú.
            </p>
            <p className="mt-6 text-sm text-emerald-50/50">¿No tienes web? Igual te la armamos y cargas la carta en el panel.</p>
          </div>
          <div className="reveal"><CreateStore /></div>
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
