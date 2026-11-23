export const pct = (x: number | undefined | null, digits = 1): string =>
  x === undefined || x === null || Number.isNaN(x) ? "—" : `${(x * 100).toFixed(digits)}%`;
export const num = (x: number, digits = 1): string => x.toFixed(digits);
export const signed = (x: number, digits = 1): string => `${x > 0 ? "+" : ""}${x.toFixed(digits)}`;
