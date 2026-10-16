/** Stable palette bucket for string keys (sidebar chips, board features, etc.). */
export function accentBucket(key: string, modulo: number): number {
  const sum = key.split("").reduce((acc, char) => acc + char.charCodeAt(0), 0);
  return Math.abs(sum) % modulo;
}
