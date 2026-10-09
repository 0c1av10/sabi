const num = (v: number) =>
  v.toLocaleString("es-VE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const usd = (v: number) => `$${num(v)}`;
export const bs = (v: number, rate: number) => `Bs ${num(v * rate)}`;
