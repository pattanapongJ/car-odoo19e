/** @odoo-module **/
/* Contact page helpers. Field visibility per topic is handled NATIVELY by the
   website form framework (s_website_form_field_hidden_if + data-visibility-*
   on the field containers — the framework reactively overrides hand-managed
   d-none/disabled, so do not toggle visibility here). This interaction only:
   - swaps the hidden tag_ids value so the lead is tagged with the topic,
   - enforces the promised 5MB limit on the company-profile PDF. */

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

const MAX_PROFILE_MB = 5;

export class HongqiContactForm extends Interaction {
    static selector = ".bs_contact_form";

    start() {
        const tagInput = this.el.querySelector("#contact_tag_ids");
        if (tagInput) {
            const tagByTopic = {
                "Request E-Catalog": tagInput.dataset.tagCatalog,
                "Dealership Application": tagInput.dataset.tagDealer,
                "Job Application": tagInput.dataset.tagJob,
            };
            const applyTopic = (topic) => {
                tagInput.value = tagByTopic[topic] || "";
            };
            const radios = this.el.querySelectorAll('input.bs_contact_radio[name="name"]');
            radios.forEach((r) => r.addEventListener("change", () => applyTopic(r.value)));
            const checked = this.el.querySelector('input.bs_contact_radio[name="name"]:checked');
            if (checked) applyTopic(checked.value);
        }

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
