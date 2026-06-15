/** @odoo-module **/
import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";
import { ReCaptcha } from "@google_recaptcha/js/recaptcha";

class TestDriveForm extends Interaction {
    static selector = "#testDriveForm";

    setup() {
        this.recaptcha = new ReCaptcha();
    }

    async start() {
        await this.recaptcha.loadLibs();
        this._initPhoneValidation();
        this._initDateValidation();
        this.el.addEventListener("submit", (e) => this._onSubmit(e));
    }

    _showNotification(message, type) {
        const bg = { success: '#198754', error: '#dc3545', warning: '#ffc107' };
        const color = { success: '#fff', error: '#fff', warning: '#000' };
        const el = document.createElement('div');
        el.setAttribute('role', 'alert');
        el.style.cssText = [
            'position:fixed', 'top:70px', 'left:50%', 'transform:translateX(-50%)',
            'min-width:300px', 'max-width:560px', 'padding:14px 20px',
            'border-radius:6px', 'font-size:14px', 'font-weight:600',
            'z-index:99999', 'box-shadow:0 4px 20px rgba(0,0,0,.3)',
            'display:flex', 'align-items:center', 'justify-content:space-between', 'gap:12px',
            'background:' + (bg[type] || bg.error),
            'color:' + (color[type] || '#fff'),
        ].join(';');
        el.innerHTML = '<span>' + message + '</span>'
            + '<button style="background:none;border:none;cursor:pointer;font-size:18px;line-height:1;color:inherit;padding:0;margin-left:8px" aria-label="close">&times;</button>';
        const btn = el.querySelector('button');
        document.body.appendChild(el);
        const timer = setTimeout(() => el.remove(), 6000);
        btn.addEventListener('click', () => { clearTimeout(timer); el.remove(); });
    }

    _initPhoneValidation() {
        this.el.querySelectorAll('input[type="tel"]').forEach((phoneInput) => {
            phoneInput.addEventListener('keypress', (e) => {
                if (!/[0-9+\-\s]/.test(e.key) && !['Backspace', 'Delete', 'Tab', 'ArrowLeft', 'ArrowRight'].includes(e.key)) {
                    e.preventDefault();
                }
            });
            phoneInput.addEventListener('input', function () {
                this.value = this.value.replace(/[^0-9+\-\s]/g, '');
            });
        });
    }

    _initDateValidation() {
        const dateInput = this.el.querySelector('#td_date');
        if (!dateInput) { return; }
        const today = new Date();
        const maxDate = new Date(today.getFullYear() + 2, today.getMonth(), today.getDate());
        dateInput.min = today.toISOString().split('T')[0];
        dateInput.max = maxDate.toISOString().split('T')[0];
        dateInput.addEventListener('change', () => {
            const val = dateInput.value;
            if (!val) { return; }
            const year = parseInt(val.split('-')[0], 10);
            const selected = new Date(val);
            const todayMidnight = new Date(today.getFullYear(), today.getMonth(), today.getDate());
            if (year < 2000 || year > today.getFullYear() + 2 || selected < todayMidnight) {
                dateInput.value = '';
                this._showNotification('กรุณาเลือกวันที่ที่ถูกต้อง (ไม่ต่ำกว่าวันนี้) / Please select a valid date (not in the past).', 'warning');
            }
        });
    }

    async _onSubmit(e) {
        e.preventDefault();

        const consent = this.el.querySelector('#td_consent');
        if (!consent || !consent.checked) {
            this._showNotification('กรุณากดยอมรับเงื่อนไขนโยบายความเป็นส่วนตัว / Please accept the Privacy Policy before submitting.', 'warning');
            return;
        }

        const tokenObj = await this.recaptcha.getToken('test_drive');
        if (tokenObj.error) {
            this._showNotification('การตรวจสอบ reCAPTCHA ล้มเหลว กรุณาลองใหม่อีกครั้ง / reCAPTCHA verification failed. Please try again.', 'error');
            return;
        }

        const submitBtn = this.el.querySelector('#td_submitBtn');
        submitBtn.textContent = 'Sending...';
        submitBtn.disabled = true;

        const payload = {
            jsonrpc: '2.0',
            method: 'call',
            params: {
                full_name: this.el.querySelector('#td_fullName').value.trim(),
                phone: this.el.querySelector('#td_phone').value.trim(),
                line_id: this.el.querySelector('#td_lineId').value.trim(),
                email: this.el.querySelector('#td_email').value.trim(),
                test_drive_date: this.el.querySelector('#td_date').value,
                test_drive_time: this.el.querySelector('input[name="preferredTime"]:checked').value,
                location: this.el.querySelector('#td_location').value.trim(),
                recaptcha_token_response: tokenObj.token || '',
            },
        };

        try {
            const res = await fetch('/test-drive/submit', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const data = await res.json();
            if (data.result && data.result.success) {
                this._showNotification('ข้อมูลถูกส่งเรียบร้อยแล้ว เจ้าหน้าที่จะติดต่อกลับโดยเร็วที่สุด / Your request has been submitted. We will contact you shortly.', 'success');
                this.el.reset();
            } else {
                this._showNotification('เกิดข้อผิดพลาด กรุณาลองใหม่อีกครั้ง / An error occurred. Please try again.', 'error');
            }
        } catch {
            this._showNotification('ไม่สามารถเชื่อมต่อกับเซิร์ฟเวอร์ได้ / Unable to connect. Please try again.', 'error');
        } finally {
            submitBtn.textContent = 'ยืนยันการนัดหมาย / Submit Request';
            submitBtn.disabled = false;
        }
    }
}

registry.category("public.interactions").add("theme_bs_hongqi_car.test_drive_form", TestDriveForm);
