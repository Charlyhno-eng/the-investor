/** Generate a deterministic RGB color, then resolve collisions within this chart. */
function candidate(id: string, attempt: number): string {
  let hash = 2166136261;
  for (const char of `${id}:${attempt}`)
    hash = Math.imul(hash ^ char.charCodeAt(0), 16777619) >>> 0;
  const hue = ((hash * 0.618033988749895) % 1) * 360;
  const saturation = (58 + (hash % 25)) / 100;
  const light = (54 + ((hash >>> 8) % 17)) / 100;
  const a = saturation * Math.min(light, 1 - light);
  const channel = (offset: number) => {
    const k = (offset + hue / 30) % 12;
    return Math.round(
      255 * (light - a * Math.max(-1, Math.min(k - 3, 9 - k, 1))),
    )
      .toString(16)
      .padStart(2, "0");
  };
  return `#${channel(0)}${channel(8)}${channel(4)}`;
}

// OKLab distances favor perceptual separation, rather than merely distinct RGBs.
function oklab(hex: string): number[] {
  const rgb = [1, 3, 5].map((i) => {
    const v = parseInt(hex.slice(i, i + 2), 16) / 255;
    return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  });
  const [r, g, b] = rgb;
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const t = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * t,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * t,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * t,
  ];
}
const squaredDistance = (a: number[], b: number[]) =>
  a.reduce((sum, v, i) => sum + (v - b[i]) ** 2, 0);
export const colorSeparation = (a: string, b: string) =>
  Math.sqrt(squaredDistance(oklab(a), oklab(b)));
const pool = Array.from({ length: 1024 }, (_, i) => {
  const color = candidate(`palette-${i}`, 0);
  return { color, lab: oklab(color) };
});

export function allocationColors(
  items: { id: string; color?: string }[],
): Map<string, string> {
  const used = new Set<string>();
  const colors = new Map<string, string>();
  const distances = pool.map(() => Infinity);
  const differentHue = (lab: number[], others: number[][]) =>
    others.every((other) => {
      const delta = Math.abs(
        Math.atan2(lab[2], lab[1]) - Math.atan2(other[2], other[1]),
      );
      return Math.min(delta, 2 * Math.PI - delta) >= Math.PI / 6;
    });
  const selected: number[][] = [];
  for (const item of [...items].sort((a, b) => a.id.localeCompare(b.id))) {
    if (colors.has(item.id)) continue;
    let color: string;
    const preferred = item.color?.toLowerCase();
    if (
      preferred &&
      !used.has(preferred) &&
      (selected.length >= 9 || differentHue(oklab(preferred), selected)) &&
      selected.every(
        (lab) => squaredDistance(oklab(preferred), lab) >= 0.12 ** 2,
      )
    ) {
      color = preferred;
    } else if (selected.length < pool.length) {
      // For a small portfolio, avoid selecting several shades of one hue.
      let best = -1;
      for (let i = 0; i < pool.length; i++) {
        if (selected.length < 9 && !differentHue(pool[i].lab, selected))
          continue;
        if (best < 0 || distances[i] > distances[best]) best = i;
      }
      if (best < 0) {
        best = 0;
        for (let i = 1; i < pool.length; i++)
          if (distances[i] > distances[best]) best = i;
      }
      color = pool[best].color;
    } else {
      color = candidate(item.id, 0);
    }
    let attempt = 1;
    while (used.has(color)) color = candidate(item.id, attempt++);
    used.add(color);
    colors.set(item.id, color);
    const lab = oklab(color);
    selected.push(lab);
    // Beyond the candidate pool, keep generating unique RGBs without a fixed palette cycle.
    if (selected.length <= pool.length)
      for (let i = 0; i < pool.length; i++)
        distances[i] = Math.min(
          distances[i],
          squaredDistance(lab, pool[i].lab),
        );
  }
  return colors;
}

export function donutArc(
  start: number,
  weight: number,
  outer: number,
  inner: number,
): string {
  const angle = Math.min(359.9999, weight * 360);
  const gap = Math.min(0.8, angle * 0.12);
  const a = start * 360 + gap / 2;
  const b = start * 360 + angle - gap / 2;
  const point = (r: number, degrees: number) =>
    `${180 + r * Math.cos(((degrees - 90) * Math.PI) / 180)},${180 + r * Math.sin(((degrees - 90) * Math.PI) / 180)}`;
  const large = b - a > 180 ? 1 : 0;
  return `M${point(outer, a)} A${outer},${outer} 0 ${large} 1 ${point(outer, b)} L${point(inner, b)} A${inner},${inner} 0 ${large} 0 ${point(inner, a)} Z`;
}
