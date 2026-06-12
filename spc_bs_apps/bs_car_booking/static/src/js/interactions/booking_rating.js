/** @odoo-module **/
import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

const LABELS = ['', 'ต้องปรับปรุง', 'พอใช้', 'ปานกลาง', 'ดี', 'ดีมาก'];

publicWidget.registry.BookingRating = publicWidget.Widget.extend({
    selector: '.conf_rating_block',
    events: {
        'mouseover .conf_star': '_onStarHover',
        'mouseout .conf_star': '_onStarOut',
        'click .conf_star': '_onStarClick',
        'click #conf_rating_submit': '_onSubmit',
        'click #conf_rating_skip': '_onSkip',
    },

    start() {
        this._selected = 0;
        this._bookingId = parseInt(this.el.dataset.bookingId, 10);
        this._accessToken = this.el.dataset.accessToken;
        return this._super(...arguments);
    },

    _renderStars(value) {
        this.el.querySelectorAll('.conf_star').forEach((s, i) => {
            s.classList.toggle('conf_star_lit', i < value);
        });
    },

    _onStarHover(ev) {
        this._renderStars(parseInt(ev.currentTarget.dataset.value, 10));
    },

    _onStarOut() {
        this._renderStars(this._selected);
    },

    _onStarClick(ev) {
        this._selected = parseInt(ev.currentTarget.dataset.value, 10);
        this._renderStars(this._selected);
        this.el.querySelector('#conf_rating_desc').textContent =
            '★'.repeat(this._selected) + '  ' + LABELS[this._selected];
        this.el.querySelector('#conf_rating_submit').disabled = false;
    },

    async _onSubmit() {
        if (!this._selected) return;
        const submitBtn = this.el.querySelector('#conf_rating_submit');
        const errorEl = this.el.querySelector('#conf_rating_error');
        const commentEl = this.el.querySelector('#conf_rating_comment');
        submitBtn.disabled = true;
        errorEl.classList.add('d-none');
        try {
            const result = await rpc(
                `/booking/${this._bookingId}/submit_rating`,
                {
                    access_token: this._accessToken,
                    rating: this._selected,
                    comment: (commentEl && commentEl.value) || '',
                }
            );
            if (result && result.error) {
                errorEl.textContent = result.error;
                errorEl.classList.remove('d-none');
                submitBtn.disabled = false;
                return;
            }
            const filled = '<i class="fa fa-star conf_star_lit"></i>'.repeat(this._selected);
            const empty = '<i class="fa fa-star-o"></i>'.repeat(5 - this._selected);
            this.el.outerHTML = `
                <div class="conf_rating_done text-center py-3">
                    <div class="conf_rating_stars">${filled}${empty}</div>
                    <p class="conf_rating_thanks mt-2">ขอบคุณสำหรับคะแนน!</p>
                    <p class="text-muted small">${this._selected}/5 — ${LABELS[this._selected]}</p>
                </div>`;
        } catch {
            errorEl.textContent = 'เกิดข้อผิดพลาด กรุณาลองใหม่อีกครั้ง';
            errorEl.classList.remove('d-none');
            submitBtn.disabled = false;
        }
    },

    _onSkip() {
        this.el.style.display = 'none';
    },
});

export default publicWidget.registry.BookingRating;
