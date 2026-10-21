import EventsChat from "../../components/events/EventsChat";

export const metadata = {
  title: "Sabi — Asistente de eventos (Demo)",
  description:
    "Demostración independiente: encuentra eventos, consulta zonas y precios de referencia y llega al enlace oficial de compra.",
  robots: { index: true, follow: true },
};

export default function EventosPage() {
  return <EventsChat />;
}
