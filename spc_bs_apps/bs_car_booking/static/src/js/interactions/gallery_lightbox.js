/** @odoo-module **/
/* Lightweight gallery lightbox: click a gallery image to view it full-size,
   navigate with arrows / swipe-free keyboard, close with Esc or backdrop. */

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class GalleryLightbox extends Interaction {
    static selector = ".bs_gallery";

    start() {
        this.items = Array.from(this.el.querySelectorAll("[data-bs-full]"));
        if (!this.items.length) {
            return;
        }
        this.index = 0;
        this._buildOverlay();

        this.items.forEach((img, i) => {
            img.style.cursor = "zoom-in";
            img.addEventListener("click", () => this._open(i));
        });

        this._onKey = (ev) => {
            if (this.overlay.classList.contains("d-none")) {
                return;
            }
            if (ev.key === "Escape") this._close();
            else if (ev.key === "ArrowLeft") this._show(this.index - 1);
            else if (ev.key === "ArrowRight") this._show(this.index + 1);
        };
        document.addEventListener("keydown", this._onKey);

        this.registerCleanup(() => {
            document.removeEventListener("keydown", this._onKey);
            this.overlay?.remove();
            document.body.style.overflow = "";
        });
    }

    _buildOverlay() {
        const o = document.createElement("div");
        o.className = "bs_lightbox d-none";
        o.innerHTML =
            '<button class="bs_lb_btn bs_lb_close" aria-label="Close">×</button>' +
            '<button class="bs_lb_btn bs_lb_prev" aria-label="Previous">‹</button>' +
            '<img class="bs_lb_img" alt=""/>' +
            '<button class="bs_lb_btn bs_lb_next" aria-label="Next">›</button>';
        document.body.appendChild(o);
        this.overlay = o;
        this.imgEl = o.querySelector(".bs_lb_img");
        o.querySelector(".bs_lb_close").addEventListener("click", () => this._close());
        o.querySelector(".bs_lb_prev").addEventListener("click", (e) => {
            e.stopPropagation();
            this._show(this.index - 1);
        });
        o.querySelector(".bs_lb_next").addEventListener("click", (e) => {
            e.stopPropagation();
            this._show(this.index + 1);
        });
        o.addEventListener("click", (e) => {
            if (e.target === o) this._close();
        });
    }

    _open(i) {
        this._show(i);
        this.overlay.classList.remove("d-none");
        document.body.style.overflow = "hidden";
    }

    _close() {
        this.overlay.classList.add("d-none");
        document.body.style.overflow = "";
    }

    _show(i) {
        const n = this.items.length;
        this.index = ((i % n) + n) % n;
        this.imgEl.src = this.items[this.index].dataset.bsFull;
    }
}

registry.category("public.interactions").add("bs_car_booking.gallery_lightbox", GalleryLightbox);
