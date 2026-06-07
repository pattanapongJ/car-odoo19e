/** @odoo-module **/
/* ================================================================
   BS CAR BOOKING - Customer Info Interaction (Odoo 19 OWL)
   Collects name/email/NRC/address, creates partner + sale order.
   ================================================================ */

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class CustomerInfoForm extends Interaction {
    static selector = "#bs_info_form";

    setup() {
        this.bookingId = parseInt(this.el.dataset.bookingId || "0");
        this.accessToken = this.el.dataset.accessToken || "";
        this.errorEl = this.el.querySelector("#info_error");
    }

    start() {
        this.el.addEventListener("submit", (e) => this._onSubmit(e));

        // Explicit opt-in: fill the (editable) form from the logged-in account.
        // The button lives outside the form; it only populates inputs client-side.
        const useBtn = document.getElementById("info_use_my_details");
        if (useBtn) {
            useBtn.addEventListener("click", () => {
                const set = (sel, val) => {
                    const el = this.el.querySelector(sel);
                    if (el && val) el.value = val;
                };
                set('[name="customer_name"]', useBtn.dataset.name);
                set('[name="customer_email"]', useBtn.dataset.email);
                set('[name="customer_address"]', useBtn.dataset.street);
            });
        }
    }

    _showError(msg) {
        if (this.errorEl) {
            this.errorEl.textContent = msg;
            this.errorEl.classList.remove("d-none");
        }
    }

    async _onSubmit(e) {
        e.preventDefault();
        const fd = new FormData(this.el);
        const name = (fd.get("customer_name") || "").trim();
        if (!name) {
            this._showError("Please enter your full name.");
            return;
        }
        const btn = this.el.querySelector(".info_submit_btn");
        const orig = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Saving...';

        try {
            const resp = await fetch("/shop/booking/info", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    method: "call",
                        params: {
                            booking_id: this.bookingId,
                            access_token: this.accessToken,
                            name: name,
                            email: (fd.get("customer_email") || "").trim(),
                        nrc: (fd.get("customer_nrc") || "").trim(),
                        address: (fd.get("customer_address") || "").trim(),
                    },
                }),
            });
            const data = await resp.json();
            const res = data.result || data;
            if (res.success) {
                window.location.href = res.redirect_url;
            } else {
                this._showError(res.error || "Something went wrong.");
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
    .add("bs_car_booking.customer_info", CustomerInfoForm);
