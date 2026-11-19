// Research ledger for one ETF and cash. Signals use the portfolio after that
// day's fills. A pending order keeps its target until its execution close.
#include <math.h>

void allocation(int n, int start, int step, int delay, double band, double fee,
                double years, const double *price, const double *target, double *out) {
    double cash = 10000., units = 0., previous = 10000., peak = 10000.;
    double drawdown = 0., sum = 0., squares = 0., exposure = 0., fees = 0.;
    double last_target = -1.;
    int trades = 0;
    int pending[3] = {0};  // Execution delays supported by the study: 1 or 2.
    for (int i = start; i < n; i++) {
        int signal = i - delay;
        double nav = cash + price[i] * units;
        if (signal >= start && pending[signal % 3]) {
            double weight = target[signal], old = units * price[i];
            double rate = weight * nav > old ? fee : -fee;
            double next = floor(weight * (nav + rate * old) /
                                (price[i] * (1. + rate * weight)) + 1e-10);
            double volume = (next - units) * price[i], cost = fabs(volume) * fee;
            cash -= volume + cost;
            fees += cost;
            trades += next != units;
            units = next;
            if (cash < -1e-6 || units < 0.) {
                out[0] = NAN;
                return;
            }
            nav = cash + price[i] * units;
        }

        int scheduled = (i - start) % step == 0;
        // Binary controls transact only when their state changes.
        int changed = band < 0. ? target[i] != last_target
                                : fabs(target[i] - units * price[i] / nav) >= band;
        pending[i % 3] = scheduled && (i == start || changed);
        if (scheduled) last_target = target[i];

        peak = fmax(peak, nav);
        drawdown = fmin(drawdown, nav / peak - 1.);
        if (i > start) {
            double ret = nav / previous - 1.;
            sum += ret;
            squares += ret * ret;
        }
        previous = nav;
        exposure += units * price[i] / nav;
    }
    double count = n - start - 1;
    double deviation = sqrt(fmax(0., (squares - sum * sum / count) / (count - 1.)));
    out[0] = deviation > 1e-12 ? sqrt(252.) * sum / (count * deviation) : NAN;
    out[1] = pow(previous / 10000., 1. / years) - 1.;
    out[2] = drawdown;
    out[3] = deviation * sqrt(252.);
    out[4] = fees;
    out[5] = trades;
    out[6] = exposure / (count + 1.);
}
