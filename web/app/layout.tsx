import "./globals.css";
import { Outfit } from "next/font/google";
import Nav from "../components/Nav";

const outfit = Outfit({ subsets: ["latin"], display: "swap" });

export const metadata = {
  metadataBase: new URL("https://www.holasabi.com"),
  title: "Sabi · La vida, más fácil.",
  description: "¿Qué te gustaría hacer? Explora menús y eventos con Sabi, tu guía en WhatsApp.",
  openGraph: {
    title: "Sabi · La vida, más fácil.",
    description: "Explora menús y eventos con Sabi, tu guía en WhatsApp.",
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
