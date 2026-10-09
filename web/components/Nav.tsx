"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  ["/pedidos", "Pedidos"],
  ["/menu", "Menú"],
  ["/registro", "Registro"],
  ["/config", "Configuración"],
] as const;

export default function Nav() {
  const path = usePathname();
  const isLanding = path === "/";
  return (
    <nav className="border-b bg-white">
      <div className="mx-auto flex max-w-6xl items-center gap-6 p-4">
        <Link href="/" className="text-lg font-bold text-emerald-700">Sabi</Link>
        <div className="ml-auto flex items-center gap-5">
          {!isLanding &&
            links.map(([href, label]) => (
              <Link key={href} href={href} className="text-sm text-stone-600 hover:text-stone-900">
                {label}
              </Link>
            ))}
          {isLanding && (
            <Link href="/login" className="text-sm font-medium text-emerald-700">
              Entrar al panel
            </Link>
          )}
        </div>
      </div>
    </nav>
  );
}
