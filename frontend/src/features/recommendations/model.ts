export type Action =
  | "Acheter"
  | "Renforcer"
  | "Conserver"
  | "Alléger"
  | "Vendre"
  | "Attendre"
  | "Indisponible";
type Input = {
  momentum: number | null;
  z: number | null;
  held: boolean;
  unavailable?: string;
};
export function recommendation({ momentum, z, held, unavailable }: Input): {
  action: Action;
  priority: number | null;
  reason: string;
} {
  if (
    unavailable ||
    momentum === null ||
    z === null ||
    !Number.isFinite(momentum) ||
    !Number.isFinite(z) ||
    momentum < 0 ||
    momentum > 100
  )
    return {
      action: "Indisponible",
      priority: null,
      reason: unavailable || "Momentum ou écart à la régression indisponible.",
    };
  // Smooth signed discount: lower z increases entry priority without a lower cutoff.
  const discount = 50 * (1 - Math.tanh(z / 1.5));
  const priority = 0.7 * momentum + 0.3 * discount;
  if (held && momentum < 40)
    return {
      action: "Vendre",
      priority,
      reason:
        "Momentum inférieur à 40 : la faiblesse de tendance prime sur une éventuelle décote à la régression.",
    };
  if (held && momentum < 55 && z >= 1.5)
    return {
      action: "Alléger",
      priority,
      reason:
        "Momentum inférieur à 55 et cours au moins 1,5 σ au-dessus de sa tendance : prise de bénéfices à envisager.",
    };
  if (priority >= 60)
    return {
      action: held ? "Renforcer" : "Acheter",
      priority,
      reason:
        "Momentum et décote combinés : priorité d’entrée au moins égale à 60 (70 % Momentum, 30 % décote à la régression).",
    };
  return {
    action: held ? "Conserver" : "Attendre",
    priority,
    reason:
      "Priorité combinée inférieure à 60 : le Momentum et la décote ne suffisent pas ensemble à proposer une entrée.",
  };
}
