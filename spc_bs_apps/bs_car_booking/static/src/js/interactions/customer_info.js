/** @odoo-module **/
/* ================================================================
   BS CAR BOOKING — Customer Info Interaction (Odoo 19)
   Individual/Company toggle, conditional fields, document uploads
   (base64) and agreement checkboxes. Server validates + creates the
   partner (company => VAT invoice) and sale order.
   ================================================================ */

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class CustomerInfoForm extends Interaction {
    static selector = "#bs_info_form";

    setup() {
        this.bookingId = parseInt(this.el.dataset.bookingId || "0");
        this.accessToken = this.el.dataset.accessToken || "";
        this.maxMb = parseInt(this.el.dataset.maxMb || "10") || 10;
        this.errorEl = this.el.querySelector("#info_error");
    }

    start() {
        this.submitBtn = this.el.querySelector(".info_submit_btn");
        this.hintEl = this.el.querySelector(".info_submit_hint");
        this.el.addEventListener("submit", (e) => this._onSubmit(e));

        // Single handler for every change: keep the type groups, the file
        // "remove" buttons and the submit-button gating in sync.
        const onChange = (ev) => {
            const t = ev.target;
            if (t && t.name === "customer_type") {
                this._applyType(this._currentType());
            }
            if (t && t.classList && t.classList.contains("info_doc_input")) {
                this._toggleClear(t);
            }
            this._refresh();
        };
        this.el.addEventListener("input", onChange);
        this.el.addEventListener("change", onChange);

        // Clearing a file input does not fire 'change', so refresh explicitly.
        this.el.querySelectorAll(".info_doc_clear").forEach((btn) =>
            btn.addEventListener("click", () => {
                const input = btn.closest(".input-group")?.querySelector(".info_doc_input");
                if (input) {
                    input.value = "";
                    this._toggleClear(input);
                    this._refresh();
                }
            })
        );

        // Optional: prefill from the logged-in account (button is outside the form).
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
                this._refresh();
            });
        }

        this._applyType(this._currentType());
        this._refresh();   // start disabled until the form is complete
    }

    /** True only when every requirement for the selected type is satisfied. */
    _validate() {
        const type = this._currentType();
        const val = (sel) => (this.el.querySelector(sel)?.value || "").trim();
        if (type === "company") {
            if (!val('[name="company_name"]') || !val('[name="tax_id"]') || !val('[name="contact_person"]')) {
                return false;
            }
        } else if (!val('[name="customer_name"]') || !val('[name="customer_nrc"]')) {
            return false;
        }
        // Required documents for this type must have a file — OR already be
        // uploaded (rehydrated after Back), so we don't force a re-upload.
        for (const f of this.el.querySelectorAll(".info_doc_field")) {
            if (f.classList.contains("d-none") || f.dataset.required !== "1") {
                continue;
            }
            const input = f.querySelector(".info_doc_input");
            const hasFile = input && input.files && input.files.length;
            if (!hasFile && f.dataset.uploaded !== "1") {
                return false;
            }
        }
        // Required agreements for this type must be ticked.
        for (const a of this.el.querySelectorAll(".info_agreement")) {
            if (a.classList.contains("d-none") || a.dataset.required !== "1") {
                continue;
            }
            const cb = a.querySelector(".info_agree_check");
            if (!(cb && cb.checked)) {
                return false;
            }
        }
        return true;
    }

    /** Enable/disable the deposit button + hint from the live form state. */
    _refresh() {
        const ok = this._validate();
        if (this.submitBtn) {
            this.submitBtn.disabled = !ok;
            this.submitBtn.classList.toggle("is-disabled", !ok);
        }
        if (this.hintEl) {
            this.hintEl.classList.toggle("d-none", ok);
        }
    }

    _currentType() {
        const checked = this.el.querySelector('input[name="customer_type"]:checked');
        return checked ? checked.value : "individual";
    }

    _toggleClear(input) {
        const has = !!(input.files && input.files.length);
        const btn = input.closest(".input-group")?.querySelector(".info_doc_clear");
        if (btn) {
            btn.classList.toggle("d-none", !has);
        }
        input.closest(".info_doc_field")?.classList.toggle("has-file", has);
    }

    _matches(el, type) {
        const a = el.dataset.appliesTo;
        return a === "both" || a === type;
    }

    _applyType(type) {
        this.el.querySelectorAll("[data-type-group]").forEach((g) =>
            g.classList.toggle("d-none", g.dataset.typeGroup !== type)
        );
        this.el.querySelectorAll(".info_doc_field").forEach((f) =>
            f.classList.toggle("d-none", !this._matches(f, type))
        );
        this.el.querySelectorAll(".info_agreement").forEach((f) =>
            f.classList.toggle("d-none", !this._matches(f, type))
        );
    }

    _showError(msg) {
        if (this.errorEl) {
            this.errorEl.textContent = msg;
            this.errorEl.classList.remove("d-none");
        }
        this.errorEl?.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    _readFile(file) {
        return new Promise((resolve, reject) => {
            const r = new FileReader();
            r.onload = () => resolve(String(r.result).split(",").pop());
            r.onerror = reject;
            r.readAsDataURL(file);
        });
    }

    async _collectDocuments(type) {
        const docs = [];
        for (const f of this.el.querySelectorAll(".info_doc_field")) {
            if (!this._matches(f, type)) {
                continue;
            }
            const input = f.querySelector(".info_doc_input");
            const file = input && input.files && input.files[0];
            if (file) {
                if (file.size > this.maxMb * 1024 * 1024) {
                    throw new Error(`"${file.name}" is larger than ${this.maxMb} MB.`);
                }
                docs.push({
                    document_type_id: parseInt(input.dataset.docTypeId),
                    filename: file.name,
                    data: await this._readFile(file),
                });
            }
        }
        return docs;
    }

    _collectAgreements(type) {
        const ids = [];
        this.el.querySelectorAll(".info_agreement").forEach((f) => {
            if (!this._matches(f, type)) {
                return;
            }
            const cb = f.querySelector(".info_agree_check");
            if (cb && cb.checked) {
                ids.push(parseInt(cb.dataset.agreementId));
            }
        });
        return ids;
    }

    async _onSubmit(e) {
        e.preventDefault();
        const type = this._currentType();
        const fd = new FormData(this.el);
        const g = (k) => (fd.get(k) || "").trim();

        // Light client checks; the server re-validates everything authoritatively.
        if (type === "company") {
            if (!g("company_name") || !g("tax_id") || !g("contact_person")) {
                this._showError("Company name, Tax ID and contact person are required.");
                return;
            }
        } else if (!g("customer_name") || !g("customer_nrc")) {
            this._showError("Full name and NRC/ID are required.");
            return;
        }

        const btn = this.el.querySelector(".info_submit_btn");
        const orig = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Saving...';

        try {
            const documents = await this._collectDocuments(type);
            const agreements = this._collectAgreements(type);
            const resp = await fetch("/shop/booking/info", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    method: "call",
                    params: {
                        booking_id: this.bookingId,
                        access_token: this.accessToken,
                        customer_type: type,
                        name: g("customer_name"),
                        email: g("customer_email"),
                        nrc: g("customer_nrc"),
                        address: g("customer_address"),
                        company_name: g("company_name"),
                        tax_id: g("tax_id"),
                        contact_person: g("contact_person"),
                        documents: documents,
                        agreements: agreements,
                    },
                }),
            });
            const data = await resp.json();
            const res = data.result || data;
            if (res.success) {
                window.location.href = res.redirect_url;
                return;
            }
            this._showError(res.error || "Something went wrong.");
        } catch (err) {
            this._showError(err?.message || "Network error. Please try again.");
        }
        btn.disabled = false;
        btn.innerHTML = orig;
    }
}

registry
    .category("public.interactions")
    .add("bs_car_booking.customer_info", CustomerInfoForm);
