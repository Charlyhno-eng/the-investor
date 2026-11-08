// Diverging blue / neutral / red, like the RdBu_r heatmaps used in notebooks.
export function correlationColor(value: number): string {
  const stops = [
    [33, 102, 172],
    [103, 169, 207],
    [209, 229, 240],
    [247, 247, 247],
    [253, 219, 199],
    [239, 138, 98],
    [178, 24, 43],
  ];
  const t = ((Math.max(-1, Math.min(1, value)) + 1) / 2) * (stops.length - 1);
  const left = Math.min(Math.floor(t), stops.length - 2);
  return `rgb(${stops[left].map((channel, i) => Math.round(channel + (stops[left + 1][i] - channel) * (t - left))).join(",")})`;
}
