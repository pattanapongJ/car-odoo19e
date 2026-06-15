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
        // Thai input filters: strip disallowed characters as the customer types
        // or pastes ("input" fires after a paste too), keeping the caret in place.
        // Soft validation only \u2014 the server re-validates everything authoritatively.
        //  \u2022 .thai-input-only \u2014 Thai letters + spaces (names as on the ID/invoice).
        //  \u2022 .thai-text-only  \u2014 Thai + digits + address punctuation, no English
        //                       (addresses & company names that need numbers).
        const bindThaiFilter = (selector, disallowed) =>
            this.el.querySelectorAll(selector).forEach((input) =>
                input.addEventListener("input", () => {
                    const before = input.value;
                    const cleaned = before.replace(disallowed, "");
                    if (cleaned === before) {
                        return;
                    }
                    // Preserve the caret: re-place it after the kept characters.
                    const caret = input.selectionStart ?? cleaned.length;
                    const keptBeforeCaret = before.slice(0, caret).replace(disallowed, "").length;
                    input.value = cleaned;
                    if (input.setSelectionRange) {
                        input.setSelectionRange(keptBeforeCaret, keptBeforeCaret);
                    }
                })
            );
        bindThaiFilter(".thai-input-only", /[^\u0E00-\u0E7F\s]/g);
        bindThaiFilter(".thai-text-only", /[^\u0E00-\u0E7F0-9\s.,\-/()#]/g);

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
            this._saveDraft();
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

        // ── Review confirmation modal wiring ──
        this.reviewModal = this.el.querySelector("[data-review-modal]");
        this.reviewProceedBtn = this.el.querySelector("[data-review-proceed]");
        this.reviewConfirmCheck = this.el.querySelector("[data-review-confirm]");
        this.reviewCustomerEl = this.el.querySelector("[data-review-customer]");
        this.reviewDocsEl = this.el.querySelector("[data-review-docs]");
        this.reviewNoDocsEl = this.el.querySelector("[data-review-nodocs]");
        this.reviewErrorEl = this.el.querySelector("[data-review-error]");
        this.reviewStatusEl = this.el.querySelector("[data-review-status]");
        this.reviewPreview = this.el.querySelector("[data-review-preview]");
        this.reviewPreviewTitle = this.el.querySelector("[data-review-preview-title]");
        this.reviewPreviewBody = this.el.querySelector("[data-review-preview-body]");
        this._reviewUrls = [];
        if (this.reviewModal) {
            // Collapsible sections.
            this.el.querySelectorAll("[data-review-toggle]").forEach((h) =>
                h.addEventListener("click", () => {
                    const sec = h.closest(".bs_review_section");
                    sec?.classList.toggle("is-collapsed");
                    sec?.querySelector(".bs_review_section_body")?.classList.toggle("is-open");
                }));
            // Confirm checkbox gates the proceed button + shows the status bar.
            this.reviewConfirmCheck?.addEventListener("change", () => {
                const ok = this.reviewConfirmCheck.checked;
                if (this.reviewProceedBtn) this.reviewProceedBtn.disabled = !ok;
                this.reviewStatusEl?.classList.toggle("d-none", !ok);
            });
            this.el.querySelector("[data-review-edit]")?.addEventListener("click", () => this._closeReview());
            this.reviewProceedBtn?.addEventListener("click", () => this._submitToServer());
            // Backdrop click = edit (return to the form).
            this.reviewModal.addEventListener("click", (e) => {
                if (e.target === this.reviewModal) this._closeReview();
            });
            // Document preview overlay.
            this.el.querySelector("[data-review-preview-close]")?.addEventListener("click", () => this._closePreview());
            this.reviewPreview?.addEventListener("click", (e) => {
                if (e.target === this.reviewPreview) this._closePreview();
            });
        }

        this.registerCleanup(() => {
            this._revokeReviewUrls();
            document.body.style.overflow = "";
        });

        // Restore an in-progress draft (saved on every change) so a page refresh
        // keeps what the customer already typed. Cleared after a successful confirm.
        this._loadDraft();

        this._applyType(this._currentType());
        this._refresh();   // start disabled until the form is complete
    }

    // ── Draft persistence (survives refresh; per booking) ───────────────
    _draftKey() {
        return `bs_info_draft_${this.bookingId}`;
    }

    _saveDraft() {
        if (!this.bookingId) return;
        const data = {};
        this.el.querySelectorAll("input[name], textarea[name], select[name]").forEach((el) => {
            if (el.type === "file" || el.disabled) return;
            if (el.type === "radio") {
                if (el.checked) data[el.name] = el.value;
            } else if (el.type === "checkbox") {
                // handled via __agreements below
            } else {
                data[el.name] = el.value;
            }
        });
        data.__agreements = Array.from(this.el.querySelectorAll(".info_agree_check"))
            .filter((cb) => cb.checked)
            .map((cb) => cb.dataset.agreementId);
        try {
            localStorage.setItem(this._draftKey(), JSON.stringify(data));
        } catch { /* storage unavailable (private mode) — skip */ }
    }

    _loadDraft() {
        if (!this.bookingId) return;
        let data;
        try {
            data = JSON.parse(localStorage.getItem(this._draftKey()) || "null");
        } catch { data = null; }
        if (!data) return;
        for (const [k, v] of Object.entries(data)) {
            if (k === "__agreements") continue;
            if (k === "customer_type") {
                const r = this.el.querySelector(`input[name="customer_type"][value="${v}"]`);
                if (r) r.checked = true;
                continue;
            }
            const el = this.el.querySelector(`[name="${k}"]`);
            if (el && el.type !== "file" && !el.disabled) {
                el.value = v;
            }
        }
        for (const id of data.__agreements || []) {
            const cb = this.el.querySelector(`.info_agree_check[data-agreement-id="${id}"]`);
            if (cb) cb.checked = true;
        }
    }

    _clearDraft() {
        try {
            localStorage.removeItem(this._draftKey());
        } catch { /* ignore */ }
    }

    /** True only when every requirement for the selected type is satisfied. */
    _validate() {
        const type = this._currentType();
        const val = (sel) => (this.el.querySelector(sel)?.value || "").trim();
        if (type === "company") {
            if (!val('[name="company_name"]') || !val('[name="tax_id"]') || !val('[name="customer_name"]')) {
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

    /* Submitting the form opens the review modal instead of saving directly.
       The actual save/redirect happens only after the customer confirms. */
    _onSubmit(e) {
        e.preventDefault();
        const type = this._currentType();
        const g = (sel) => (this.el.querySelector(sel)?.value || "").trim();

        // Light client checks; the server re-validates everything authoritatively.
        if (type === "company") {
            if (!g('[name="company_name"]') || !g('[name="tax_id"]') || !g('[name="customer_name"]')) {
                this._showError("Company name, Tax ID and contact person are required.");
                return;
            }
        } else if (!g('[name="customer_name"]') || !g('[name="customer_nrc"]')) {
            this._showError("Full name and NRC/ID are required.");
            return;
        }

        if (this.reviewModal) {
            this._openReview();
        } else {
            this._submitToServer();   // graceful fallback if the modal is absent
        }
    }

    /* Persist the info + documents and move to the deposit step. Triggered by
       the modal's Confirm button (or directly if there's no modal). */
    async _submitToServer() {
        const type = this._currentType();
        const fd = new FormData(this.el);
        const g = (k) => (fd.get(k) || "").trim();

        const btn = this.reviewProceedBtn || this.submitBtn;
        const orig = btn ? btn.innerHTML : "";
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Saving...';
        }
        this._reviewError("");

        try {
            const documents = await this._collectDocuments(type);
            const agreements = this._collectAgreements(type);
            const resp = await fetch("/car_booking/booking/info", {
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
                        documents: documents,
                        agreements: agreements,
                    },
                }),
            });
            const data = await resp.json();
            const res = data.result || data;
            if (res.success) {
                this._clearDraft();   // confirmed → drop the saved draft
                window.location.href = res.redirect_url;
                return;
            }
            this._reviewError(res.error || "Something went wrong.");
        } catch (err) {
            this._reviewError(err?.message || "Network error. Please try again.");
        }
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = orig;
        }
    }

    // ── Review modal helpers ────────────────────────────────────────────
    _openReview() {
        this._reviewError("");
        this._fillReviewCustomer();
        this._fillReviewDocs();
        if (this.reviewConfirmCheck) this.reviewConfirmCheck.checked = false;
        if (this.reviewProceedBtn) this.reviewProceedBtn.disabled = true;
        this.reviewStatusEl?.classList.add("d-none");
        this.reviewModal.classList.remove("d-none");
        document.body.style.overflow = "hidden";
    }

    _closeReview() {
        this._closePreview();
        this.reviewModal?.classList.add("d-none");
        document.body.style.overflow = "";
        this._revokeReviewUrls();
    }

    _openPreview(file, title) {
        if (!this.reviewPreview || !this.reviewPreviewBody) {
            // No preview overlay available — fall back to a new tab.
            const url = URL.createObjectURL(file);
            this._reviewUrls.push(url);
            window.open(url, "_blank", "noopener");
            return;
        }
        if (this.reviewPreviewTitle) this.reviewPreviewTitle.textContent = title || file.name;
        const url = URL.createObjectURL(file);
        this._reviewUrls.push(url);
        this.reviewPreviewBody.replaceChildren();
        let viewer;
        if (file.type === "application/pdf") {
            viewer = document.createElement("iframe");
            viewer.className = "bs_review_preview_frame";
            viewer.src = url;
        } else if (file.type.startsWith("image/")) {
            viewer = document.createElement("img");
            viewer.className = "bs_review_preview_img";
            viewer.src = url;
            viewer.alt = title || file.name;
        } else {
            viewer = document.createElement("div");
            viewer.className = "bs_review_preview_fallback";
            viewer.innerHTML = '<i class="fa fa-file-o"/>';
            const fn = document.createElement("p");
            fn.textContent = file.name;
            viewer.appendChild(fn);
        }
        this.reviewPreviewBody.appendChild(viewer);
        this.reviewPreview.classList.remove("d-none");
    }

    _closePreview() {
        this.reviewPreview?.classList.add("d-none");
        this.reviewPreviewBody?.replaceChildren();
    }

    _reviewError(msg) {
        if (this.reviewErrorEl) {
            this.reviewErrorEl.textContent = msg || "";
            this.reviewErrorEl.classList.toggle("d-none", !msg);
        } else if (msg) {
            this._showError(msg);
        }
    }

    _fillReviewCustomer() {
        const el = this.reviewCustomerEl;
        if (!el) return;
        const type = this._currentType();
        const v = (sel) => (this.el.querySelector(sel)?.value || "").trim();
        const phone = (this.el.querySelector('input[type="tel"]')?.value || "").trim();
        const rows = [["ประเภท", type === "company" ? "นิติบุคคล" : "บุคคลธรรมดา"]];
        if (type === "company") {
            rows.push(["ชื่อบริษัท", v('[name="company_name"]')]);
            rows.push(["เลขประจำตัวผู้เสียภาษี", v('[name="tax_id"]')]);
            rows.push(["ผู้ติดต่อ", v('[name="customer_name"]')]);
        } else {
            rows.push(["ชื่อ-นามสกุล", v('[name="customer_name"]')]);
            rows.push(["เลขบัตรประชาชน", v('[name="customer_nrc"]')]);
        }
        if (phone) rows.push(["โทรศัพท์", phone]);
        const email = v('[name="customer_email"]');
        if (email) rows.push(["อีเมล", email]);
        const addr = v('[name="customer_address"]');
        if (addr) rows.push(["ที่อยู่", addr]);

        el.replaceChildren();
        for (const [k, val] of rows) {
            const row = document.createElement("div");
            row.className = "bs_review_row";
            const ks = document.createElement("span");
            ks.className = "bs_review_k";
            ks.textContent = k;
            const vs = document.createElement("span");
            vs.className = "bs_review_v";
            vs.textContent = val || "—";
            row.append(ks, vs);
            el.appendChild(row);
        }
    }

    _fillReviewDocs() {
        const wrap = this.reviewDocsEl;
        if (!wrap) return;
        this._revokeReviewUrls();
        wrap.replaceChildren();
        const type = this._currentType();
        let count = 0;
        for (const f of this.el.querySelectorAll(".info_doc_field")) {
            if (f.classList.contains("d-none") || !this._matches(f, type)) continue;
            const input = f.querySelector(".info_doc_input");
            const file = input && input.files && input.files[0];
            const label = (f.querySelector(".form-label")?.textContent || "Document").replace("*", "").trim();
            if (file) {
                wrap.appendChild(this._docCard(label, file.name, this._fmtSize(file.size), file));
                count++;
            } else if (f.dataset.uploaded === "1") {
                wrap.appendChild(this._docCard(label, "อัปโหลดไว้ก่อนหน้า", "", null));
                count++;
            }
        }
        this.reviewNoDocsEl?.classList.toggle("d-none", count > 0);
    }

    _docCard(label, filename, size, file) {
        const card = document.createElement("div");
        card.className = "bs_review_doc";
        const icon = document.createElement("div");
        icon.className = "bs_review_doc_icon";
        icon.innerHTML = '<i class="fa fa-file-o"/>';
        const meta = document.createElement("div");
        meta.className = "bs_review_doc_meta";
        const n = document.createElement("p");
        n.className = "bs_review_doc_name";
        n.textContent = label;
        const fm = document.createElement("p");
        fm.className = "bs_review_doc_file";
        fm.textContent = size ? `${filename} · ${size}` : filename;
        meta.append(n, fm);
        const actions = document.createElement("div");
        actions.className = "bs_review_doc_actions";
        const badge = document.createElement("span");
        badge.className = "bs_review_badge bs_review_badge_ok";
        badge.textContent = "อัปโหลดแล้ว";
        actions.appendChild(badge);
        if (file) {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "btn btn-sm btn-outline-secondary bs_review_doc_view";
            btn.innerHTML = '<i class="fa fa-eye"/> ดู';
            btn.addEventListener("click", () => this._openPreview(file, label));
            actions.appendChild(btn);
        }
        card.append(icon, meta, actions);
        return card;
    }

    _fmtSize(b) {
        if (b >= 1048576) return (b / 1048576).toFixed(1) + " MB";
        if (b >= 1024) return Math.round(b / 1024) + " KB";
        return b + " B";
    }

    _revokeReviewUrls() {
        (this._reviewUrls || []).forEach((u) => URL.revokeObjectURL(u));
        this._reviewUrls = [];
    }
}

registry
    .category("public.interactions")
    .add("bs_car_booking.customer_info", CustomerInfoForm);
