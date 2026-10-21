import "./globals.css";
import { Outfit } from "next/font/google";
import Nav from "../components/Nav";

const outfit = Outfit({ subsets: ["latin"], display: "swap" });

export const metadata = {
  metadataBase: new URL("https://www.holasabi.com"),
  title: "Sabi · Agente de ventas por WhatsApp para restaurantes y eventos",
  description: "Sabi atiende por WhatsApp las 24 horas: recomienda, cierra pedidos de restaurantes y te lleva al enlace oficial para comprar entradas. Tú apruebas cada pedido. Precios en dólares, euros y bolívares.",
  openGraph: {
    title: "Sabi · Tu mejor vendedor en WhatsApp",
    description: "Pedidos y entradas por WhatsApp con IA, aprobados por ti. Dólares, euros y bolívares.",
    siteName: "Sabi",
    locale: "es_VE",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" className={outfit.className}>
      <body>
        <Nav />
        {children}
      </body>
    </html>
  );
}
