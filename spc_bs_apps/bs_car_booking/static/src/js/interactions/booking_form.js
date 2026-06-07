/** @odoo-module **/
/* ================================================================
   BS CAR BOOKING - Configurator Interaction (Odoo 19 OWL)
   Live attribute selection + price, dealer + phone, create booking.
   ================================================================ */

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

async function jsonrpc(route, params) {
    const resp = await fetch(route, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jsonrpc: "2.0", method: "call", params }),
    });
    const data = await resp.json();
    return data.result || data;
}

export class CarConfigurator extends Interaction {
    static selector = "#bs_configurator_form";

    setup() {
        this.modelId = parseInt(this.el.dataset.modelId || "0");
        this.priceEl = document.getElementById("cfg_price");
        this.errorEl = document.getElementById("cfg_error");
        this.selectedListEl = document.getElementById("cfg_selected_list");
    }

    start() {
        // Visual selection + live price on any input change.
        for (const input of this.el.querySelectorAll(".cfg_input")) {
            input.addEventListener("change", () => this._onChange(input));
        }
        for (const input of this.el.querySelectorAll('input[name="dealer_id"]')) {
            input.addEventListener("change", () => this._refreshDealerStyles());
        }
        // PDPA consent gates the submit button: enable only when ticked.
        this.pdpaEl = document.getElementById("cfg_pdpa");
        this.submitBtn = this.el.querySelector(".cfg_submit_btn");
        if (this.pdpaEl && this.submitBtn) {
            const sync = () => { this.submitBtn.disabled = !this.pdpaEl.checked; };
            this.pdpaEl.addEventListener("change", sync);
            sync();
        }

        // Initialise selected styles + price.
        this._refreshSelectedStyles();
        this._refreshDealerStyles();
        this._refreshSummary();
        this._updatePrice();

        this.el.addEventListener("submit", (e) => this._onSubmit(e));
    }

    _selectedPtavIds() {
        const ids = [];
        for (const input of this.el.querySelectorAll(".cfg_input")) {
            if (input.checked && input.dataset.ptavId) {
                ids.push(parseInt(input.dataset.ptavId));
            }
        }
        return ids;
    }

    _refreshSelectedStyles() {
        for (const input of this.el.querySelectorAll(".cfg_input")) {
            const label = input.closest("label");
            if (label) label.classList.toggle("is-selected", input.checked);
        }
    }

    _refreshDealerStyles() {
        for (const input of this.el.querySelectorAll('input[name="dealer_id"]')) {
            const label = input.closest("label");
            if (label) label.classList.toggle("is-selected", input.checked);
        }
    }

    _refreshSummary() {
        if (!this.selectedListEl) return;
        const selected = Array.from(this.el.querySelectorAll(".cfg_input:checked"))
            .map((input) => input.dataset.summaryLabel)
            .filter(Boolean);
        this.selectedListEl.innerHTML = "";
        for (const label of selected.slice(0, 6)) {
            const chip = document.createElement("span");
            chip.textContent = label;
            this.selectedListEl.appendChild(chip);
        }
        if (!selected.length) {
            const chip = document.createElement("span");
            chip.textContent = "Standard configuration";
            this.selectedListEl.appendChild(chip);
        }
    }

    _onChange() {
        this._refreshSelectedStyles();
        this._refreshSummary();
        this._updatePrice();
    }

    async _updatePrice() {
        if (!this.priceEl) return;
        this.priceEl.classList.add("is-updating");
        try {
            const res = await jsonrpc("/shop/car/price", {
                model_id: this.modelId,
                ptav_ids: this._selectedPtavIds(),
            });
            if (res.success && res.price_formatted) {
                this.priceEl.textContent = res.price_formatted;
            }
        } catch {
            /* keep last shown price */
        } finally {
            window.setTimeout(() => this.priceEl?.classList.remove("is-updating"), 180);
        }
    }

    _showError(msg) {
        if (this.errorEl) {
            this.errorEl.textContent = msg;
            this.errorEl.classList.remove("d-none");
        }
        this.errorEl?.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    async _onSubmit(e) {
        e.preventDefault();
        const phoneEl = document.getElementById("cfg_phone");
        const phone = (phoneEl && phoneEl.value || "").trim();
        const dealer = this.el.querySelector('input[name="dealer_id"]:checked');
        const dealerOptions = this.el.querySelectorAll('input[name="dealer_id"]');

        if (phone.length < 7) {
            this._showError("Please enter a valid mobile number.");
            return;
        }
        if (dealerOptions.length && !dealer) {
            this._showError("Please select a preferred dealer.");
            return;
        }
        const pdpaEl = document.getElementById("cfg_pdpa");
        if (pdpaEl && !pdpaEl.checked) {
            this._showError("Please accept the Privacy Policy (PDPA) to continue.");
            return;
        }

        const btn = this.el.querySelector(".cfg_submit_btn");
        const orig = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Creating...';

        try {
            const res = await jsonrpc("/shop/car/book", {
                model_id: this.modelId,
                ptav_ids: this._selectedPtavIds(),
                dealer_id: dealer ? dealer.value : null,
                phone: phone,
                pdpa_consent: !!(pdpaEl && pdpaEl.checked),
            });
            if (res.success) {
                window.location.href = res.redirect_url;
            } else {
                this._showError(res.error || "Something went wrong. Please try again.");
                btn.disabled = false;
                btn.innerHTML = orig;
            }
        } catch {
            this._showError("Network error. Please try again.");
            btn.disabled = false;
            btn.innerHTML = orig;
        }
    }
}

registry
    .category("public.interactions")
    .add("bs_car_booking.car_configurator", CarConfigurator);
