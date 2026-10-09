export function token() {
  return typeof window !== "undefined" ? localStorage.getItem("sabi_token") || "" : "";
}

export async function api(path: string, opts: RequestInit = {}) {
  const res = await fetch(`/api${path}`, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      "X-Sabi-Token": token(),
      ...(opts.headers || {}),
    },
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}
