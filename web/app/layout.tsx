import "./globals.css";
import Nav from "../components/Nav";

export const metadata = { title: "Sabi — Panel del restaurante" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>
        <Nav />
        <main className="mx-auto max-w-5xl p-6">{children}</main>
      </body>
    </html>
  );
}
