/** @odoo-module **/
/* Data-driven Hongqi-style home showcase interactions. */

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class HomeShowcase extends Interaction {
    static selector = "#wrapwrap";

    start() {
        this._stageTimers = [];
        this._initStages();
        this._initColorStudios();
        this._initHighlights();
        this.registerCleanup(() => {
            for (const timer of this._stageTimers) {
                clearInterval(timer);
            }
            if (this._hlKey) {
                document.removeEventListener("keydown", this._hlKey);
            }
            this._hlOverlay?.remove();
            document.body.style.overflow = "";
        });
    }

    /* Highlights: click a card to open a split image + info lightbox
       (mirrors the Hongqi Thailand highlights modal). */
    _initHighlights() {
        const cards = Array.from(this.el.querySelectorAll(".bs_highlight_card[data-hl-img]"));
        if (!cards.length) {
            return;
        }
        const pad = (n) => String(n).padStart(2, "0");
        const o = document.createElement("div");
        o.className = "bs_hl_lightbox d-none";
        o.innerHTML =
            '<div class="bs_hl_lb_inner">' +
            '  <div class="bs_hl_lb_media"><img class="bs_hl_lb_img" alt=""/></div>' +
            '  <div class="bs_hl_lb_panel">' +
            '    <button class="bs_hl_lb_close" aria-label="Close">×</button>' +
            '    <span class="bs_hl_lb_kicker"></span>' +
            '    <h3 class="bs_hl_lb_title"></h3>' +
            '    <div class="bs_hl_lb_desc"></div>' +
            '    <span class="bs_hl_lb_count"></span>' +
            '  </div>' +
            '  <button class="bs_hl_lb_nav bs_hl_lb_prev" aria-label="Previous">‹</button>' +
            '  <button class="bs_hl_lb_nav bs_hl_lb_next" aria-label="Next">›</button>' +
            '</div>';
        document.body.appendChild(o);
        this._hlOverlay = o;
        const imgEl = o.querySelector(".bs_hl_lb_img");
        const kEl = o.querySelector(".bs_hl_lb_kicker");
        const tEl = o.querySelector(".bs_hl_lb_title");
        const dEl = o.querySelector(".bs_hl_lb_desc");
        const cEl = o.querySelector(".bs_hl_lb_count");
        let idx = 0;
        const render = (i) => {
            idx = (i + cards.length) % cards.length;
            const c = cards[idx].dataset;
            imgEl.src = c.hlImg;
            kEl.textContent = c.hlKicker || "";
            tEl.textContent = c.hlTitle || "";
            dEl.innerHTML = c.hlDesc || "";
            cEl.textContent = pad(idx + 1) + " / " + pad(cards.length);
        };
        const open = (i) => {
            render(i);
            o.classList.remove("d-none");
            document.body.style.overflow = "hidden";
        };
        const close = () => {
            o.classList.add("d-none");
            document.body.style.overflow = "";
        };
        cards.forEach((card, i) => {
            card.style.cursor = "zoom-in";
            card.addEventListener("click", () => open(i));
            card.addEventListener("keydown", (e) => {
                if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    open(i);
                }
            });
        });
        o.querySelector(".bs_hl_lb_close").addEventListener("click", close);
        o.querySelector(".bs_hl_lb_prev").addEventListener("click", (e) => {
            e.stopPropagation();
            render(idx - 1);
        });
        o.querySelector(".bs_hl_lb_next").addEventListener("click", (e) => {
            e.stopPropagation();
            render(idx + 1);
        });
        o.addEventListener("click", (e) => {
            if (e.target === o || e.target.classList.contains("bs_hl_lb_inner")) {
                close();
            }
        });
        this._hlKey = (e) => {
            if (o.classList.contains("d-none")) {
                return;
            }
            if (e.key === "Escape") close();
            else if (e.key === "ArrowLeft") render(idx - 1);
            else if (e.key === "ArrowRight") render(idx + 1);
        };
        document.addEventListener("keydown", this._hlKey);
    }

    _initStages() {
        for (const stage of this.el.querySelectorAll("[data-bs-showcase-stage]")) {
            const slides = Array.from(stage.querySelectorAll(".bs_model_stage_slide"));
            const dots = Array.from(stage.querySelectorAll("[data-stage-dot]"));
            if (slides.length < 2) {
                continue;
            }
            let index = 0;
            const show = (next) => {
                index = (next + slides.length) % slides.length;
                slides.forEach((slide, i) => slide.classList.toggle("is-active", i === index));
                dots.forEach((dot, i) => dot.classList.toggle("is-active", i === index));
            };
            dots.forEach((dot, i) => dot.addEventListener("click", () => show(i)));
            if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
                this._stageTimers.push(setInterval(() => show(index + 1), 5500));
            }
        }
    }

    _initColorStudios() {
        for (const panel of this.el.querySelectorAll("[data-showcase-group]")) {
            const buttons = Array.from(panel.querySelectorAll("[data-showcase-target]"));
            const images = Array.from(panel.querySelectorAll("[data-showcase-image]"));
            const show = (id) => {
                buttons.forEach((btn) => {
                    btn.classList.toggle("is-active", btn.dataset.showcaseTarget === id);
                });
                images.forEach((img) => {
                    img.classList.toggle("is-active", img.dataset.showcaseImage === id);
                });
            };
            buttons.forEach((btn) => btn.addEventListener("click", () => show(btn.dataset.showcaseTarget)));
        }
    }
}

registry.category("public.interactions").add("bs_car_booking.home_showcase", HomeShowcase);
