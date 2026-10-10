"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Mascot from "../../../components/Mascot";

export default function Login() {
  const [slug, setSlug] = useState("");
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const router = useRouter();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ slug, pin }),
    });
    if (!res.ok) return setError("Slug o PIN incorrecto");
    const data = await res.json();
    localStorage.setItem("sabi_token", data.token);
    router.push("/pedidos");
  }

  return (
    <div className="mx-auto mt-28 max-w-sm rounded-xl border bg-white p-6 shadow-sm">
      <div className="-mt-16 mb-2 flex justify-center"><Mascot className="w-24" /></div>
      <h1 className="mb-4 text-center text-xl font-semibold">Entrar a Sabi</h1>
      <form onSubmit={submit} className="space-y-3">
        <input className="w-full rounded border p-2" placeholder="Slug del restaurante"
               value={slug} onChange={(e) => setSlug(e.target.value)} />
        <input className="w-full rounded border p-2" placeholder="PIN" type="password"
               value={pin} onChange={(e) => setPin(e.target.value)} />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button className="w-full rounded bg-emerald-700 p-2 font-medium text-white">
          Entrar
        </button>
      </form>
    </div>
  );
}
