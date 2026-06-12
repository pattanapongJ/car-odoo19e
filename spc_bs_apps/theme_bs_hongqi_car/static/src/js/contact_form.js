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
        // PDPA consent gates the submit button (UX layer — the framework's
        // required-validation and the server-side filter are the real guards).
        const consent = this.el.querySelector("#privacy_consent");
        const submit = this.el.querySelector(".s_website_form_send");
        if (consent && submit) {
            const sync = () => {
                submit.classList.toggle("disabled", !consent.checked);
                submit.setAttribute("aria-disabled", String(!consent.checked));
            };
            consent.addEventListener("change", sync);
            sync();
        }

        // Company-profile + CV size guard (the label promises max 5MB).
        const guard = (selector) => {
            const el = this.el.querySelector(selector);
            el?.addEventListener("change", () => {
                const f = el.files && el.files[0];
                if (f && f.size > MAX_PROFILE_MB * 1024 * 1024) {
                    el.value = "";
                    el.setCustomValidity(`File too large — max ${MAX_PROFILE_MB}MB.`);
                    el.reportValidity();
                } else {
                    el.setCustomValidity("");
                }
            });
        };
        guard("#contact_attachment");
        guard("#contact_cv");
    }
}

registry
    .category("public.interactions")
    .add("theme_bs_hongqi_car.contact_form", HongqiContactForm);
