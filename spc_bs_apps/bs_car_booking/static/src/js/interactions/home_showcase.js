/** @odoo-module **/
/* Data-driven home showcase interactions. */

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class HomeShowcase extends Interaction {
    static selector = "#wrapwrap";

    start() {
        this._stageTimers = [];
        this._initStages();
        this._initColorStudios();
        this._initLinkedColorStudios();
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

    /* Highlights: click a card to open a split image + info lightbox. */
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
            '  <div class="bs_hl_lb_media">' +
            '    <img class="bs_hl_lb_img" alt=""/>' +
            '    <div class="bs_hl_lb_thumbs"></div>' +
            '  </div>' +
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
        const thumbsEl = o.querySelector(".bs_hl_lb_thumbs");
        const kEl = o.querySelector(".bs_hl_lb_kicker");
        const tEl = o.querySelector(".bs_hl_lb_title");
        const dEl = o.querySelector(".bs_hl_lb_desc");
        const cEl = o.querySelector(".bs_hl_lb_count");
        let idx = 0;
        let gallery = [];
        let galleryIdx = 0;
        const parseGallery = (card) => {
            try {
                const parsed = JSON.parse(card.dataset.hlGallery || "[]");
                if (Array.isArray(parsed) && parsed.length) {
                    return parsed;
                }
            } catch {
                // Fall back to the legacy single-image attributes below.
            }
            return [{
                src: card.dataset.hlImg || "",
                thumb: card.dataset.hlImg || "",
                alt: card.dataset.hlTitle || "",
                title: card.dataset.hlTitle || "",
            }];
        };
        const renderGalleryImage = (i) => {
            if (!gallery.length) {
                return;
            }
            galleryIdx = (i + gallery.length) % gallery.length;
            const current = gallery[galleryIdx] || {};
            imgEl.src = current.src || "";
            imgEl.alt = current.alt || "";
            thumbsEl.querySelectorAll("button").forEach((btn, thumbIdx) => {
                btn.classList.toggle("is-active", thumbIdx === galleryIdx);
            });
            cEl.textContent = pad(idx + 1) + " / " + pad(cards.length) +
                (gallery.length > 1 ? " · Image " + pad(galleryIdx + 1) + " / " + pad(gallery.length) : "");
        };
        const renderThumbs = () => {
            thumbsEl.replaceChildren();
            thumbsEl.classList.toggle("d-none", gallery.length < 2);
            gallery.forEach((image, imageIdx) => {
                const btn = document.createElement("button");
                btn.type = "button";
                btn.className = "bs_hl_lb_thumb";
                btn.setAttribute("aria-label", image.title || image.alt || "Highlight image");
                const thumb = document.createElement("img");
                thumb.src = image.thumb || image.src;
                thumb.alt = image.alt || "";
                btn.appendChild(thumb);
                btn.addEventListener("click", (ev) => {
                    ev.stopPropagation();
                    renderGalleryImage(imageIdx);
                });
                thumbsEl.appendChild(btn);
            });
        };
        const render = (i) => {
            idx = (i + cards.length) % cards.length;
            const c = cards[idx].dataset;
            kEl.textContent = c.hlKicker || "";
            tEl.textContent = c.hlTitle || "";
            dEl.innerHTML = c.hlDesc || "";
            gallery = parseGallery(cards[idx]);
            galleryIdx = 0;
            renderThumbs();
            renderGalleryImage(0);
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
            else if (e.key === "ArrowUp" && gallery.length > 1) renderGalleryImage(galleryIdx - 1);
            else if (e.key === "ArrowDown" && gallery.length > 1) renderGalleryImage(galleryIdx + 1);
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
            // Linked (option-driven) studios are handled by _initLinkedColorStudios
            // so their exterior/interior panels stay in sync — skip them here.
            if (panel.closest("[data-color-studio-linked]")) {
                continue;
            }
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

    /* Option-driven Colour Studio.
       Picking an exterior shows the body image and filters the interior
       swatches to those offered with it. If interiors exist, the first
       available interior is selected on load so the section never starts
       half-empty. */
    _initLinkedColorStudios() {
        for (const studio of this.el.querySelectorAll("[data-color-studio-linked]")) {
            const extGroup = studio.querySelector('[data-showcase-group="exterior"]');
            const intGroup = studio.querySelector('[data-showcase-group="interior"]');
            const sharedStage = studio.querySelector('[data-cs-stage="1"]');
            const extStage = studio.querySelector('[data-cs-stage="exterior"]') || sharedStage;
            const intStage = studio.querySelector('[data-cs-stage="interior"]') || sharedStage;
            const extBtns = extGroup ? Array.from(extGroup.querySelectorAll("[data-showcase-target]")) : [];
            const intBtns = intGroup ? Array.from(intGroup.querySelectorAll("[data-showcase-target]")) : [];
            if (!extBtns.length && !intBtns.length) {
                continue;
            }
            const labelOf = (btn) => (btn.querySelector(".bs_color_label")?.textContent || btn.title || "").trim();
            const showInStage = (stage, btn) => {
                if (!stage) {
                    return;
                }
                const target = btn.dataset.showcaseTarget;
                stage.querySelectorAll("[data-showcase-image]").forEach(
                    (i) => i.classList.toggle("is-active", i.dataset.showcaseImage === target));
                const caption = stage.querySelector("[data-cs-caption]");
                if (caption) {
                    caption.textContent = labelOf(btn);
                }
            };
            const setActive = (btns, btn) => {
                btns.forEach((b) => b.classList.toggle("is-active", b === btn));
            };
            // Interior image lives in its own full-width stage below the selector.
            const selectInterior = (btn) => {
                setActive(intBtns, btn);
                showInStage(intStage, btn);
            };
            // A single highlight box wraps the selected exterior swatch together
            // with its interior swatches. We move both into a combo element so
            // there is one highlight around the pair, restoring the swatch to its
            // original slot when another exterior is chosen.
            let combo = null;
            let wrappedBtn = null;
            const unwrapCombo = () => {
                if (!combo) {
                    return;
                }
                if (wrappedBtn) {
                    combo.replaceWith(wrappedBtn);             // swatch back in place
                }
                if (intGroup) {
                    intGroup.classList.remove("is-open");
                }
                combo = null;
                wrappedBtn = null;
            };
            const wrapCombo = (btn) => {
                unwrapCombo();
                combo = document.createElement("div");
                combo.className = "bs_cs_combo";
                btn.replaceWith(combo);
                combo.appendChild(btn);
                wrappedBtn = btn;
                if (intGroup) {
                    combo.appendChild(intGroup);
                }
            };
            const expandInteriors = (btn) => {
                const allowed = (btn.dataset.interiorIds || "").split(",").filter(Boolean);
                let first = null;
                intBtns.forEach((b) => {
                    const ok = !allowed.length || allowed.includes(b.dataset.showcaseTarget);
                    b.classList.toggle("d-none", !ok);
                    if (ok && !first) {
                        first = b;
                    }
                });
                if (first) {
                    wrapCombo(btn);
                    if (intGroup) {
                        intGroup.classList.add("is-open");
                    }
                    if (intStage) {
                        intStage.classList.remove("d-none");
                    }
                    selectInterior(first);
                } else {
                    unwrapCombo();
                    if (intStage) {
                        intStage.classList.add("d-none");
                    }
                }
            };
            const selectExterior = (btn) => {
                setActive(extBtns, btn);
                showInStage(extStage, btn);
                expandInteriors(btn);
            };
            extBtns.forEach((b) => b.addEventListener("click", () => selectExterior(b)));
            intBtns.forEach((b) => b.addEventListener("click", () => selectInterior(b)));
            if (extBtns.length) {
                selectExterior(extBtns[0]);
            } else if (intBtns.length) {
                if (intGroup) {
                    intGroup.classList.add("is-open");
                }
                if (intStage) {
                    intStage.classList.remove("d-none");
                }
                selectInterior(intBtns[0]);
            }
        }
    }
}

registry.category("public.interactions").add("bs_car_booking.home_showcase", HomeShowcase);
