/** @odoo-module **/
/* Contact page helpers. Field visibility per topic is handled NATIVELY by the
   website form framework (s_website_form_field_hidden_if + data-visibility-*
   on the field containers), and the topic tag is stamped SERVER-SIDE
   (crm_lead.website_form_input_filter) — never from the client. This
   interaction only enforces the promised 5MB limit on the company-profile PDF. */

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

const MAX_PROFILE_MB = 5;

export class HongqiContactForm extends Interaction {
    static selector = ".bs_contact_form";

    start() {
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
}

registry
    .category("public.interactions")
    .add("theme_bs_hongqi_car.contact_form", HongqiContactForm);
