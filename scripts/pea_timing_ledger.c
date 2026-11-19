// Research ledger: one path, multiple declared strategies. Each decision is
// executed delay closes later. No borrowing, prior holdings or final sale.
#include <math.h>

double pea_book(int n, int lo, int delay, double fee, double years,
              const double *prices, const signed char *defensive,
              const int *monthly, int cadence, double floor_weight, double *out) {
    double cash = 10000., units = 0., peak = 10000., drawdown = 0.;
    double previous = 10000., sum = 0., squares = 0., costs = 0., exposures = 0.;
    int trades = 0, last_mode = -1;
    for (int i = lo; i < n; ++i) {
        const int signal = i - delay;
        const double price = prices[i];
        if (signal >= lo &&
            (signal == lo || (cadence == 0 ? monthly[signal] : (signal-lo)%cadence == 0))) {
            const int mode = defensive[signal];
            if (mode != last_mode) {
                const double target = mode ? floor_weight : 1.;
                const double old = units*price, nav = old+cash;
                const double signed_fee = target*nav > old ? fee : -fee;
                const double new_units = floor(target*(nav+signed_fee*old) /
                                               (price*(1.+target*signed_fee))+1e-10);
                const double amount = (new_units-units)*price, cost = fabs(amount)*fee;
                cash -= amount+cost;
                costs += cost;
                trades += new_units != units;
                units = new_units;
                last_mode = mode;
            }
        }
        const double nav = cash + units*price;
        if (cash < -1e-6 || units < 0.) {out[0] = NAN; return NAN;}
        peak = fmax(peak,nav);
        drawdown = fmin(drawdown,nav/peak-1.);
        if (i > lo) {
            const double ret = nav/previous-1.;
            sum += ret;
            squares += ret*ret;
        }
        previous=nav;
        exposures += units*price/nav;
    }
    double m = n-lo-1;
    out[0] = pow(previous/10000.,1./years)-1.;
    out[1] = drawdown;
    out[2] = sqrt(fmax(0.,(squares-sum*sum/m)/(m-1.))*252.);
    out[3] = costs;
    out[4] = trades;
    out[5] = exposures/(n-lo);
    return out[2] > sqrt(252.)*1e-12 ? (sum/m)*252./out[2] : NAN;
}
