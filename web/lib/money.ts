export type Rates = { usd: number; eur: number };

const num = (v: number) =>
  v.toLocaleString("es-VE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const usd = (v: number) => `$${num(v)}`;
export const bs = (v: number, r: Rates) => `Bs ${num(v * r.usd)}`;
export const eur = (v: number, r: Rates) => `€${num(r.eur ? (v * r.usd) / r.eur : 0)}`;
