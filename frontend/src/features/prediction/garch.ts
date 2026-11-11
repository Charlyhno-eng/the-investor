/** Gaussian quasi-likelihood GARCH(1,1), with variance targeting.
 * The grid plus local refinement includes the constant-variance benchmark.
 * Inputs are zero-mean innovations, one per observed session/calendar day.
 */
export function fitGarch(innovations: number[]) {
  if (innovations.length < 60 || innovations.some((e) => !Number.isFinite(e)))
    throw new Error(
      "Au moins 60 innovations finies sont nécessaires pour GARCH.",
    );
  const variance =
    innovations.reduce((s, e) => s + e * e, 0) / innovations.length;
  if (variance < 1e-20)
    return {
      omega: 0,
      alpha: 0,
      beta: 0,
      variance: 0,
      nextVariance: 0,
      loss: 0,
      constantLoss: 0,
    };
  // Normalize to unit sample variance to keep the likelihood well-conditioned.
  const squared = innovations.map((e) => (e * e) / variance);
  function evaluate(alpha: number, beta: number) {
    if (alpha < 0 || beta < 0 || alpha + beta >= 0.995) return Infinity;
    const omega = 1 - alpha - beta;
    let h = 1,
      loss = 0;
    for (const e2 of squared) {
      loss += Math.log(h) + e2 / h;
      h = omega + alpha * e2 + beta * h;
    }
    return loss;
  }
  let alpha = 0,
    beta = 0,
    loss = evaluate(0, 0);
  const constantLoss = loss;
  for (const a of [0, 0.03, 0.06, 0.12, 0.2, 0.35, 0.6]) {
    for (const b of [0, 0.3, 0.6, 0.8, 0.9, 0.95, 0.98]) {
      const candidate = evaluate(a, b);
      if (candidate < loss) {
        alpha = a;
        beta = b;
        loss = candidate;
      }
    }
  }
  let step = 0.05;
  for (let iteration = 0; iteration < 100 && step > 0.00001; iteration++) {
    let bestA = alpha,
      bestB = beta,
      bestLoss = loss;
    for (const da of [-step, 0, step])
      for (const db of [-step, 0, step]) {
        const candidate = evaluate(alpha + da, beta + db);
        if (candidate < bestLoss) {
          bestA = alpha + da;
          bestB = beta + db;
          bestLoss = candidate;
        }
      }
    if (bestLoss < loss) {
      alpha = bestA;
      beta = bestB;
      loss = bestLoss;
    } else step /= 2;
  }
  const omega = variance * (1 - alpha - beta);
  let nextVariance = variance;
  for (const e of innovations)
    nextVariance = omega + alpha * e * e + beta * nextVariance;
  return { omega, alpha, beta, variance, nextVariance, loss, constantLoss };
}
