/** @odoo-module **/
/* ================================================================
   BS CAR BOOKING - OTP Verification Interaction (Odoo 19 OWL)
   Handles OTP digit inputs, countdown timer, verify & resend
   ================================================================ */

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class OtpVerification extends Interaction {
    static selector = ".otp_form";

    setup() {
        this.countdownSecs = 300; // 5 minutes
        this.countdownInterval = null;
        this.resendCooldown = 0;
        this.resendTimer = null;
    }

    start() {
        // Find booking ID from parent .otp_card element
        const bookingId = parseInt(
            this.el.closest("[data-booking-id]")?.dataset?.bookingId || "0"
        );
        const accessToken = this.el.closest("[data-access-token]")?.dataset?.accessToken || "";
        if (!bookingId) return;

        const getEl = (id) => document.getElementById(id);
        const digitInputs = this.el.querySelectorAll(".otp_digit");
        const verifyBtn = getEl("otp_verify_btn");
        const resendBtn = getEl("otp_resend_btn");
        const countdownEl = getEl("otp_countdown");
        const errorMsgEl = getEl("otp_error_msg");
        const successMsgEl = getEl("otp_success_msg");

        // ── Helpers ────────────────────────────────────────
        const getOtpCode = () => {
            let code = "";
            digitInputs.forEach((inp) => (code += inp.value));
            return code;
        };
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

        // ── OTP Digit Inputs ───────────────────────────────
        digitInputs.forEach((input, idx) => {
            input.addEventListener("input", () => {
                const val = input.value.replace(/[^0-9]/g, "");
                input.value = val.slice(0, 1);
                if (val && idx < 5) digitInputs[idx + 1].focus();
            });
            input.addEventListener("keydown", (e) => {
                if (e.key === "Backspace" && !input.value && idx > 0) {
                    digitInputs[idx - 1].focus();
                }
            });
        });
        digitInputs[0]?.addEventListener("paste", (e) => {
            e.preventDefault();
            const paste = (
                (e.clipboardData || window.clipboardData).getData("text") || ""
            ).replace(/[^0-9]/g, "");
            paste.split("").slice(0, 6).forEach((ch, i) => {
                if (digitInputs[i]) digitInputs[i].value = ch;
            });
        });

        // ── Countdown Timer ────────────────────────────────
        const updateCountdown = () => {
            const mins = Math.floor(this.countdownSecs / 60);
            const secs = this.countdownSecs % 60;
            if (countdownEl) {
                countdownEl.textContent =
                    String(mins).padStart(2, "0") + ":" +
                    String(secs).padStart(2, "0");
            }
            if (this.countdownSecs <= 0) {
                clearInterval(this.countdownInterval);
                if (countdownEl) countdownEl.textContent = "Expired";
                if (verifyBtn) verifyBtn.disabled = true;
            }
            this.countdownSecs--;
        };
        this.countdownInterval = setInterval(updateCountdown, 1000);

        // ── Resend Cooldown ────────────────────────────────
        const startResendCooldown = () => {
            if (resendBtn) resendBtn.disabled = true;
            this.resendCooldown = 30;
            if (resendBtn) resendBtn.textContent = "Resend in 30s";
            this.resendTimer = setInterval(() => {
                this.resendCooldown--;
                if (this.resendCooldown <= 0) {
                    clearInterval(this.resendTimer);
                    if (resendBtn) {
                        resendBtn.textContent = "Resend Code";
                        resendBtn.disabled = false;
                    }
                } else if (resendBtn) {
                    resendBtn.textContent = "Resend in " + this.resendCooldown + "s";
                }
            }, 1000);
        };
        startResendCooldown();

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
        if (resendBtn) {
            resendBtn.addEventListener("click", async () => {
                if (this.resendCooldown > 0) return;
                resendBtn.disabled = true;
                resendBtn.textContent = "Sending...";

                try {
                    const r = await fetch("/car_booking/booking/otp/resend", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            jsonrpc: "2.0",
                            method: "call",
                            params: {
                                booking_id: bookingId,
                                access_token: accessToken,
                            },
                        }),
                    });
                    const data = await r.json();
                    if (data.result?.success) {
                        this.countdownSecs = 300;
                        if (countdownEl) countdownEl.textContent = "05:00";
                        if (verifyBtn) verifyBtn.disabled = false;
                        startResendCooldown();
                        showSuccess("New code sent!");
                        digitInputs.forEach((inp) => (inp.value = ""));
                        digitInputs[0]?.focus();
                    } else {
                        showError("Failed to resend. Please try again.");
                        if (this.resendCooldown <= 0) {
                            resendBtn.disabled = false;
                            resendBtn.textContent = "Resend Code";
                        }
                    }
                } catch {
                    showError("Network error. Please try again.");
                    if (this.resendCooldown <= 0) {
                        resendBtn.disabled = false;
                        resendBtn.textContent = "Resend Code";
                    }
                }
            });
        }

        this.registerCleanup(() => {
            if (this.countdownInterval) clearInterval(this.countdownInterval);
            if (this.resendTimer) clearInterval(this.resendTimer);
        });
    }
}

registry
    .category("public.interactions")
    .add("bs_car_booking.otp_verification", OtpVerification);
