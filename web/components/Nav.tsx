"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

const links = [
  ["/pedidos", "Pedidos"],
  ["/menu", "Menú"],
  ["/tienda", "Tienda"],
  ["/registro", "Registro"],
  ["/config", "Configuración"],
] as const;

export default function Nav() {
  const path = usePathname();
  const [restaurant, setRestaurant] = useState<{ name: string; logo_url: string; brand_color: string } | null>(null);
  useEffect(() => {
    if (path === "/" || path === "/login" || path.startsWith("/eventos")) return;
    fetch("/api/me", { headers: { "X-Sabi-Token": localStorage.getItem("sabi_token") || "" } })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => data && setRestaurant(data))
      .catch(() => {});
  }, [path]);
  if (path.startsWith("/tienda/") || path.startsWith("/eventos")) return null;
  if (path === "/") return null;

  return (
    <nav className="border-b bg-white">
      <div className="mx-auto flex max-w-6xl items-center gap-6 p-4">
        <Link href="/" className="flex items-center gap-2 text-lg font-bold text-emerald-700">
          {restaurant?.logo_url && <img src={restaurant.logo_url} alt="" className="h-7 w-7 rounded-lg object-contain" />}
          <span>{restaurant?.name || "Sabi"}</span>
        </Link>
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
