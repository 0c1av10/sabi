"use client";
import Link from "next/link";

const links = [
  ["/pedidos", "Pedidos"],
  ["/menu", "Menú"],
  ["/registro", "Registro"],
  ["/config", "Configuración"],
] as const;

export default function Nav() {
  return (
    <nav className="border-b bg-white">
      <div className="mx-auto flex max-w-5xl items-center gap-6 p-4">
        <Link href="/pedidos" className="text-lg font-bold text-emerald-700">Sabi</Link>
        {links.map(([href, label]) => (
          <Link key={href} href={href} className="text-sm text-stone-600 hover:text-stone-900">
            {label}
          </Link>
        ))}
      </div>
    </nav>
  );
}
