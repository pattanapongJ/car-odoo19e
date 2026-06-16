/** @odoo-module **/
/* Auto-advancing hero slider for bs.car.website.slide sections. */

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

const SWIPE_THRESHOLD_PX = 50;
const INTERVAL_MIN_MS = 1000;   // guard: ไม่ให้ตั้งน้อยกว่า 1s

export class HeroSlider extends Interaction {
    static selector = ".car_hero_slider";

    start() {
        this._slides = Array.from(this.el.querySelectorAll(".bs_slide"));
        this._dots = Array.from(this.el.querySelectorAll(".bs_slider_dot"));
        this._current = 0;
        this._timer = null;
        this._paused = false;
        this._reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

        // Read interval from data-interval (ms). 0 = disabled.
        const raw = parseInt(this.el.dataset.interval || "5000", 10);
        this._intervalMs = raw >= INTERVAL_MIN_MS ? raw : raw === 0 ? 0 : 5000;

        // Read Ken Burns toggle
        this._kenBurns = this.el.dataset.kenBurns === "1";

        if (this._slides.length === 0) return;

        // Slide 0 is already .active from server-rendered HTML — just sync state
        // without triggering the fade-in animation (which would cause a dip from
        // opacity:0.3 on a slide the user is already seeing).
        this._slides.forEach((slide, i) => {
            slide.classList.toggle("active", i === 0);
            slide.setAttribute("aria-hidden", i === 0 ? "false" : "true");
        });
        this._dots.forEach((dot, i) => {
            dot.classList.toggle("active", i === 0);
            dot.setAttribute("aria-pressed", i === 0 ? "true" : "false");
        });

        // Auto-advance only when motion is allowed and interval is set
        if (!this._reducedMotion && this._intervalMs > 0) {
            this._startAuto();
        }

        this._bindControls();
        this._bindReducedMotionListener();

        this.registerCleanup(() => this._stopAuto());
    }

    // ── Slide display ──────────────────────────────────────────────────

    _showSlide(index) {
        const total = this._slides.length;
        if (total === 0) return;

        if (index >= total) index = 0;
        if (index < 0) index = total - 1;
        this._current = index;

        this._slides.forEach((slide, i) => {
            const isActive = i === this._current;
            slide.setAttribute("aria-hidden", isActive ? "false" : "true");

            if (isActive) {
                // Reset Ken Burns before making slide visible
                if (!this._reducedMotion) {
                    const media = slide.querySelectorAll(".bs_slide_img, .bs_slide_video");
                    media.forEach((el) => {
                        el.style.animation = "none";
                        void el.offsetWidth;
                        el.style.animation = "";
                    });
                }
                slide.classList.add("active");
            } else {
                slide.classList.remove("active");
            }
        });

        this._dots.forEach((dot, i) => {
            dot.classList.toggle("active", i === this._current);
            dot.setAttribute("aria-pressed", i === this._current ? "true" : "false");
        });

        // Announce to screen readers via ARIA live region
        const live = this.el.querySelector(".bs_slider_live");
        if (live) {
            const title = this._slides[this._current].querySelector(
                ".bs_slide_title, .bs_slide_title_img"
            );
            live.textContent = `Slide ${this._current + 1} of ${total}${title ? ": " + (title.alt || title.textContent || "") : ""}`;
        }
    }

    _next() { this._showSlide(this._current + 1); }
    _prev() { this._showSlide(this._current - 1); }

    // ── Auto-advance ───────────────────────────────────────────────────

    _startAuto() {
        this._stopAuto();
        if (!this._intervalMs) return;
        this._timer = setInterval(() => {
            if (!this._paused) this._next();
        }, this._intervalMs);
    }

    _stopAuto() {
        if (this._timer) {
            clearInterval(this._timer);
            this._timer = null;
        }
    }

    _resetAuto() {
        if (!this._reducedMotion && this._intervalMs > 0) this._startAuto();
    }

    // ── Controls ───────────────────────────────────────────────────────

    _bindControls() {
        const prevBtn = this.el.querySelector(".bs_slider_prev");
        const nextBtn = this.el.querySelector(".bs_slider_next");

        if (prevBtn) {
            this.addListener(prevBtn, "click", () => {
                this._prev();
                this._resetAuto();
            });
        }
        if (nextBtn) {
            this.addListener(nextBtn, "click", () => {
                this._next();
                this._resetAuto();
            });
        }

        // Dot clicks
        this._dots.forEach((dot, i) => {
            this.addListener(dot, "click", () => {
                this._showSlide(i);
                this._resetAuto();
            });
        });

        // Pause auto-advance on hover (desktop)
        this.addListener(this.el, "mouseenter", () => { this._paused = true; });
        this.addListener(this.el, "mouseleave", () => { this._paused = false; });

        // Keyboard: ← → arrow keys when slider is focused
        this.addListener(this.el, "keydown", (e) => {
            if (e.key === "ArrowLeft") {
                e.preventDefault();
                this._prev();
                this._resetAuto();
            } else if (e.key === "ArrowRight") {
                e.preventDefault();
                this._next();
                this._resetAuto();
            }
        });

        // Make slider focusable for keyboard nav
        if (!this.el.hasAttribute("tabindex")) {
            this.el.setAttribute("tabindex", "0");
        }

        // Touch swipe
        let touchStartX = 0;
        this.addListener(this.el, "touchstart", (e) => {
            touchStartX = e.touches[0].clientX;
        }, { passive: true });
        this.addListener(this.el, "touchend", (e) => {
            const diff = touchStartX - e.changedTouches[0].clientX;
            if (Math.abs(diff) > SWIPE_THRESHOLD_PX) {
                diff > 0 ? this._next() : this._prev();
                this._resetAuto();
            }
        }, { passive: true });

        // iframe fallback: hide overlay once iframe loads
        this.el.querySelectorAll(".bs_slide_bg iframe").forEach((iframe) => {
            this.addListener(iframe, "load", () => {
                const fallback = iframe.closest(".bs_slide_bg")?.querySelector(".bs_slide_iframe_fallback");
                if (fallback) fallback.style.display = "none";
            });
            this.addListener(iframe, "error", () => {
                const fallback = iframe.closest(".bs_slide_bg")?.querySelector(".bs_slide_iframe_fallback");
                if (fallback) fallback.style.display = "block";
            });
        });
    }

    // ── Reduced-motion: listen for OS setting change at runtime ────────

    _bindReducedMotionListener() {
        const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
        const handler = (e) => {
            this._reducedMotion = e.matches;
            if (this._reducedMotion || !this._intervalMs) {
                this._stopAuto();
            } else {
                this._startAuto();
            }
        };
        mq.addEventListener("change", handler);
        this.registerCleanup(() => mq.removeEventListener("change", handler));
    }
}

registry.category("public.interactions").add("HeroSlider", HeroSlider);
