/** @odoo-module **/
/* Finance calculator: estimate the monthly payment from price, down payment,
   term and APR. Standard amortization formula; live on any input change. */

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class FinanceCalc extends Interaction {
    static selector = ".bs_finance";

    start() {
        this.priceEl = this.el.querySelector(".bs_fin_price");
        this.downEl = this.el.querySelector(".bs_fin_down");
        this.termEl = this.el.querySelector(".bs_fin_term");
        this.aprEl = this.el.querySelector(".bs_fin_apr");
        this.outEl = this.el.querySelector(".bs_fin_monthly");
        this.currency = this.el.dataset.currency || "";

        // Initialise APR/term from backend config defaults (data attributes).
        if (this.aprEl && !this.aprEl.value) {
            this.aprEl.value = this.el.dataset.apr || "3.5";
        }
        if (this.termEl && this.el.dataset.term) {
            this.termEl.value = this.el.dataset.term;
        }

        for (const el of [this.priceEl, this.downEl, this.termEl, this.aprEl]) {
            if (el) {
                el.addEventListener("input", () => this._calc());
                el.addEventListener("change", () => this._calc());
            }
        }
        this._calc();
    }

    _calc() {
        const price = parseFloat(this.priceEl && this.priceEl.value) || 0;
        const down = parseFloat(this.downEl && this.downEl.value) || 0;
        const n = parseInt(this.termEl && this.termEl.value) || 0;
        const apr = parseFloat(this.aprEl && this.aprEl.value) || 0;
        const principal = Math.max(price - down, 0);

        let monthly = 0;
        if (n > 0) {
            const r = apr / 100 / 12;
            monthly = r > 0
                ? (principal * r) / (1 - Math.pow(1 + r, -n))
                : principal / n;
        }
        if (this.outEl) {
            const amount = monthly.toLocaleString(undefined, { maximumFractionDigits: 0 });
            this.outEl.textContent = `${this.currency} ${amount} /mo`;
        }
    }
}

registry.category("public.interactions").add("bs_car_booking.finance_calc", FinanceCalc);
