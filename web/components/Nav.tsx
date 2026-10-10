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
  if (path === "/") {
    return (
      <nav className="absolute inset-x-0 top-0 z-20 px-4">
        <div className="mx-auto mt-5 flex max-w-6xl items-center justify-between rounded-full border border-white/10 bg-white/[0.04] py-2 pl-6 pr-2 backdrop-blur-md">
          <Link href="/" className="text-lg font-bold tracking-tight text-white">Sabi</Link>
          <div className="flex items-center gap-6 text-sm">
            <a href="#ventas" className="hidden text-emerald-50/70 transition hover:text-white sm:inline">Cómo vende</a>
            <a href="#faq" className="hidden text-emerald-50/70 transition hover:text-white sm:inline">Preguntas</a>
            <Link href="/login" className="rounded-full bg-white px-5 py-2 font-medium text-[#04140f] transition duration-300 ease-[cubic-bezier(.32,.72,0,1)] hover:bg-[#25D366] active:scale-[0.98]">
              Entrar al panel
            </Link>
          </div>
        </div>
      </nav>
    );
  }
  return (
    <nav className="border-b bg-white">
      <div className="mx-auto flex max-w-6xl items-center gap-6 p-4">
        <Link href="/" className="text-lg font-bold text-emerald-700">Sabi</Link>
        <div className="ml-auto flex items-center gap-5">
          {links.map(([href, label]) => (
            <Link key={href} href={href} className={`text-sm hover:text-stone-900 ${path === href ? "font-medium text-stone-900" : "text-stone-600"}`}>
              {label}
            </Link>
          ))}
        </div>
      </div>
    </nav>
  );
}
