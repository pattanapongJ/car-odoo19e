/** @odoo-module **/
/* Contact page: the Proposed Location + Company Profile fields belong to the
   "Dealership Application" topic only. They start hidden AND disabled in the
   template (disabled inputs are skipped by the form submit and by native
   required-validation); this interaction reveals/enables them when the
   dealership topic is picked, and enforces the 5MB PDF limit. */

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

const MAX_PROFILE_MB = 5;

export class HongqiContactForm extends Interaction {
    static selector = ".bs_contact_form";

    start() {
        this.dealerFields = this.el.querySelectorAll(".bs_contact_dealer_field");
        if (!this.dealerFields.length) return;
        const radios = this.el.querySelectorAll('input.bs_contact_radio[name="name"]');
        radios.forEach((r) =>
            r.addEventListener("change", () => this._applyTopic(r.value))
        );
        const checked = this.el.querySelector('input.bs_contact_radio[name="name"]:checked');
        this._applyTopic(checked ? checked.value : "");

        // Company-profile size guard (the label promises max 5MB).
        const file = this.el.querySelector("#contact_attachment");
        file?.addEventListener("change", () => {
            const f = file.files && file.files[0];
            if (f && f.size > MAX_PROFILE_MB * 1024 * 1024) {
                file.value = "";
                file.setCustomValidity(`File too large — max ${MAX_PROFILE_MB}MB.`);
                file.reportValidity();
            } else {
                file.setCustomValidity("");
            }
        });
    }

    _applyTopic(topic) {
        const isDealer = topic === "Dealership Application";
        this.dealerFields.forEach((field) => {
            field.classList.toggle("d-none", !isDealer);
            field.querySelectorAll("input, select").forEach((input) => {
                input.disabled = !isDealer;
                if (input.id === "proposed_location") input.required = isDealer;
                if (!isDealer) input.value = "";
            });
        });
    }
}

registry
    .category("public.interactions")
    .add("theme_bs_hongqi_car.contact_form", HongqiContactForm);
