import "./globals.css";
import { Outfit } from "next/font/google";
import Nav from "../components/Nav";

const outfit = Outfit({ subsets: ["latin"], display: "swap" });

export const metadata = {
  title: "Sabi · Agente de ventas por WhatsApp para restaurantes",
  description: "Sabi recomienda, sube el ticket y cierra pedidos por WhatsApp las 24 horas. Tú apruebas cada uno. Precios en dólares, euros y bolívares.",
  openGraph: {
    title: "Sabi · Tu mejor vendedor en WhatsApp",
    description: "Pedidos por WhatsApp con IA, aprobados por ti. Dólares, euros y bolívares.",
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
