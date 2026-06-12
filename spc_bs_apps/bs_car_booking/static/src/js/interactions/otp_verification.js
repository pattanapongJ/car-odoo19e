/** @odoo-module **/
/* ================================================================
   BS CAR BOOKING - OTP Verification Interaction (Odoo 19 OWL)
   Handles OTP digit inputs, countdown timer, verify & resend
   ================================================================ */

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";
import { initOtpDigits } from "@bs_car_booking/js/otp_digits";

export class OtpVerification extends Interaction {
    static selector = ".otp_form";

    setup() {
        // Countdown is derived from an absolute expiry anchor (see start());
        // this interval handle is the only timer state we keep.
        this.countdownInterval = null;
    }

    start() {
        // Find booking ID from parent .otp_card element
        const card = this.el.closest("[data-booking-id]");
        const bookingId = parseInt(card?.dataset?.bookingId || "0");
        const accessToken = this.el.closest("[data-access-token]")?.dataset?.accessToken || "";
        if (!bookingId) return;

        const getEl = (id) => document.getElementById(id);
        const digitInputs = this.el.querySelectorAll(".otp_digit");
        const verifyBtn = getEl("otp_verify_btn");
        const resendBtn = getEl("otp_resend_btn");
        const resendLabel = getEl("otp_resend_label") || resendBtn;
        const errorMsgEl = getEl("otp_error_msg");
        const successMsgEl = getEl("otp_success_msg");

        // ── Helpers ────────────────────────────────────────
        const otpDigits = initOtpDigits(digitInputs);
        const getOtpCode = () => otpDigits.getCode();
        // Enable verify button only when all 6 digits are filled.
        if (verifyBtn) verifyBtn.disabled = true;
        const syncVerifyBtn = () => {
            if (verifyBtn) verifyBtn.disabled = getOtpCode().length !== 6;
        };
        digitInputs.forEach((inp) => {
            inp.addEventListener("input", syncVerifyBtn);
            inp.addEventListener("paste", syncVerifyBtn);
        });
        const showError = (msg) => {
            if (errorMsgEl) {
                errorMsgEl.textContent = msg;
                errorMsgEl.parentElement.classList.remove("d-none");
            }
            if (successMsgEl) successMsgEl.parentElement.classList.add("d-none");
        };
        const showSuccess = (msg) => {
            if (successMsgEl) {
                successMsgEl.textContent = msg;
                successMsgEl.parentElement.classList.remove("d-none");
            }
            if (errorMsgEl) errorMsgEl.parentElement.classList.add("d-none");
        };

        // ── Countdown anchored to an absolute expiry (survives refresh) ──
        // The countdown is computed from a stored expiry timestamp, NOT from a
        // fixed duration — so refreshing the page never restarts it, and an
        // expired code stays expired. localStorage keeps the anchor per booking.
        const STORAGE_KEY = `bs_otp_exp_${bookingId}`;
        const readAnchor = () => parseInt(localStorage.getItem(STORAGE_KEY) || "0") || 0;
        const writeAnchor = (ts) => {
            try { localStorage.setItem(STORAGE_KEY, String(ts)); } catch { /* private mode */ }
        };
        const clearAnchor = () => {
            try { localStorage.removeItem(STORAGE_KEY); } catch { /* ignore */ }
        };

        // Server-rendered remaining lifetime (0 = already expired). Honour it
        // verbatim; only a genuinely absent attribute is treated as "unknown".
        const rawExpiry = card?.dataset?.otpExpiry;
        const serverRemaining = (rawExpiry === undefined || rawExpiry === "")
            ? null : (parseInt(rawExpiry) || 0);

        // Adopt the server's expiry as the absolute anchor when it is later than
        // what we have stored (a fresh page render or a newly issued code).
        let anchorTs = readAnchor();
        if (serverRemaining !== null && serverRemaining > 0) {
            const serverAnchor = Date.now() + serverRemaining * 1000;
            if (serverAnchor > anchorTs) {
                anchorTs = serverAnchor;
                writeAnchor(anchorTs);
            }
        } else if (serverRemaining === 0) {
            // Server is authoritative: the code is expired.
            anchorTs = 0;
            clearAnchor();
        }
        const remainingNow = () => (anchorTs ? Math.max(0, Math.round((anchorTs - Date.now()) / 1000)) : 0);

        const fmt = (secs) => {
            const m = Math.floor(secs / 60), s = secs % 60;
            return String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
        };
        // The countdown lives inside the resend button: "Resend in mm:ss" while
        // the code is valid (button disabled), "Resend code" once it expires
        // (button enabled) — so resend is aligned to the expiry.
        const showCounting = (secs) => {
            if (resendBtn) resendBtn.disabled = true;
            if (resendLabel) resendLabel.textContent = "Resend in " + fmt(secs);
        };
        const showResendReady = () => {
            if (resendBtn) resendBtn.disabled = false;
            if (resendLabel) resendLabel.textContent = "Resend code";
        };
        const onExpired = () => {
            if (this.countdownInterval) clearInterval(this.countdownInterval);
            this.countdownInterval = null;
            if (verifyBtn) verifyBtn.disabled = true;
            showResendReady();
        };
        const tick = () => {
            const secs = remainingNow();
            if (secs <= 0) { onExpired(); return; }
            showCounting(secs);
        };
        const startCountdown = () => {
            if (this.countdownInterval) clearInterval(this.countdownInterval);
            if (remainingNow() <= 0) { onExpired(); return; }
            showCounting(remainingNow());
            this.countdownInterval = setInterval(tick, 1000);
        };
        startCountdown();

        // ── Verify OTP ─────────────────────────────────────
        if (verifyBtn) {
            verifyBtn.addEventListener("click", async () => {
                const code = getOtpCode();
                if (code.length !== 6) {
                    showError("Please enter the complete 6-digit code.");
                    return;
                }
                verifyBtn.disabled = true;
                verifyBtn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Verifying...';

                try {
                    const r = await fetch("/car_booking/booking/otp/verify", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            jsonrpc: "2.0",
                            method: "call",
                            params: {
                                booking_id: bookingId,
                                access_token: accessToken,
                                otp_code: code,
                            },
                        }),
                    });
                    const data = await r.json();
                    const result = data.result;
                    if (result?.success) {
                        clearAnchor();
                        showSuccess("Phone verified! Redirecting...");
                        setTimeout(() => {
                            window.location.href = result.redirect_url;
                        }, 1500);
                    } else {
                        showError(result?.error || "Invalid code.");
                        verifyBtn.disabled = false;
                        verifyBtn.innerHTML = '<i class="fa fa-check"></i> Verify';
                        digitInputs.forEach((inp) => (inp.value = ""));
                        digitInputs[0]?.focus();
                    }
                } catch {
                    showError("Network error. Please try again.");
                    verifyBtn.disabled = false;
                    verifyBtn.innerHTML = '<i class="fa fa-check"></i> Verify';
                }
            });
        }

        // ── Resend OTP ─────────────────────────────────────
        const resendOtp = async (channel) => {
            const r = await fetch("/car_booking/booking/otp/resend", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    method: "call",
                    params: {
                        booking_id: bookingId,
                        access_token: accessToken,
                        channel: channel || null,
                    },
                }),
            });
            const data = await r.json();
            return data.result || {};
        };

        if (resendBtn) {
            resendBtn.addEventListener("click", async () => {
                if (resendBtn.disabled) return;
                resendBtn.disabled = true;
                if (resendLabel) resendLabel.textContent = "Sending...";

                try {
                    const result = await resendOtp(null);
                    if (result.success) {
                        // New code issued: anchor a fresh expiry and restart.
                        const secs = result.expires_in || 300;
                        anchorTs = Date.now() + secs * 1000;
                        writeAnchor(anchorTs);
                        startCountdown();
                        if (verifyBtn) verifyBtn.disabled = false;
                        showSuccess("New code sent!");
                        digitInputs.forEach((inp) => (inp.value = ""));
                        digitInputs[0]?.focus();
                        syncVerifyBtn();
                    } else {
                        showError(result.error || "Failed to resend. Please try again.");
                        showResendReady();   // still expired → allow retry
                    }
                } catch {
                    showError("Network error. Please try again.");
                    showResendReady();
                }
            });
        }

        // ── Switch delivery channel (customer-choice websites) ──
        const switchBtn = getEl("otp_switch_btn");
        if (switchBtn) {
            switchBtn.addEventListener("click", async () => {
                const channel = switchBtn.dataset.channel;
                if (!channel) return;
                switchBtn.disabled = true;
                switchBtn.textContent = "Sending...";
                try {
                    const result = await resendOtp(channel);
                    if (result.success) {
                        // Reload so the page copy reflects the new channel
                        // (icon, title, destination, switch direction).
                        window.location.reload();
                    } else {
                        showError(result.error || "Could not switch. Please try again.");
                        switchBtn.disabled = false;
                        switchBtn.textContent = channel === "email"
                            ? "Send to my email instead" : "Send by SMS instead";
                    }
                } catch {
                    showError("Network error. Please try again.");
                    switchBtn.disabled = false;
                }
            });
        }

        this.registerCleanup(() => {
            if (this.countdownInterval) clearInterval(this.countdownInterval);
        });
    }
}

registry
    .category("public.interactions")
    .add("bs_car_booking.otp_verification", OtpVerification);
