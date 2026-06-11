(function () {
    'use strict';

    function showNotification(message, type) {
        var bg = { success: '#198754', error: '#dc3545', warning: '#ffc107' };
        var color = { success: '#fff', error: '#fff', warning: '#000' };
        var el = document.createElement('div');
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
        var close = '<button style="background:none;border:none;cursor:pointer;font-size:18px;line-height:1;color:inherit;padding:0;margin-left:8px" aria-label="close">&times;</button>';
        el.innerHTML = '<span>' + message + '</span>' + close;
        el.querySelector('button').addEventListener('click', function () { el.remove(); });
        document.body.appendChild(el);
        var timer = setTimeout(function () { el.remove(); }, 6000);
        el.querySelector('button').addEventListener('click', function () { clearTimeout(timer); });
    }

    function initPhoneValidation() {
        document.querySelectorAll('input[type="tel"]').forEach(function (phoneInput) {
            phoneInput.addEventListener('keypress', function (e) {
                if (!/[0-9+\-\s]/.test(e.key) && !['Backspace', 'Delete', 'Tab', 'ArrowLeft', 'ArrowRight'].includes(e.key)) {
                    e.preventDefault();
                }
            });
            phoneInput.addEventListener('input', function () {
                this.value = this.value.replace(/[^0-9+\-\s]/g, '');
            });
        });
    }

    function initTestDriveForm() {
        var form = document.getElementById('testDriveForm');
        if (!form) { return; }

        // Set date min (today) and max (2 years ahead)
        var dateInput = document.getElementById('td_date');
        var today = new Date();
        var maxDate = new Date(today.getFullYear() + 2, today.getMonth(), today.getDate());
        dateInput.min = today.toISOString().split('T')[0];
        dateInput.max = maxDate.toISOString().split('T')[0];

        dateInput.addEventListener('change', function () {
            var val = this.value;
            if (!val) { return; }
            var year = parseInt(val.split('-')[0], 10);
            var selected = new Date(val);
            var todayMidnight = new Date(today.getFullYear(), today.getMonth(), today.getDate());
            if (year < 2000 || year > today.getFullYear() + 2 || selected < todayMidnight) {
                this.value = '';
                showNotification('กรุณาเลือกวันที่ที่ถูกต้อง (ไม่ต่ำกว่าวันนี้) / Please select a valid date (not in the past).', 'warning');
            }
        });

        form.addEventListener('submit', async function (e) {
            e.preventDefault();

            var consent = document.getElementById('td_consent');
            if (!consent.checked) {
                showNotification('กรุณากดยอมรับเงื่อนไขนโยบายความเป็นส่วนตัว / Please accept the Privacy Policy before submitting.', 'warning');
                return;
            }

            var btn = document.getElementById('td_submitBtn');
            btn.textContent = 'Sending...';
            btn.disabled = true;

            var payload = {
                jsonrpc: '2.0',
                method: 'call',
                params: {
                    full_name: document.getElementById('td_fullName').value.trim(),
                    phone: document.getElementById('td_phone').value.trim(),
                    line_id: document.getElementById('td_lineId').value.trim(),
                    email: document.getElementById('td_email').value.trim(),
                    test_drive_date: document.getElementById('td_date').value,
                    test_drive_time: document.querySelector('input[name="preferredTime"]:checked').value,
                    location: document.getElementById('td_location').value.trim(),
                },
            };

            try {
                var res = await fetch('/test-drive/submit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });
                var data = await res.json();
                if (data.result && data.result.success) {
                    showNotification('ข้อมูลถูกส่งเรียบร้อยแล้ว เจ้าหน้าที่จะติดต่อกลับโดยเร็วที่สุด / Your request has been submitted. We will contact you shortly.', 'success');
                    form.reset();
                } else {
                    showNotification('เกิดข้อผิดพลาด กรุณาลองใหม่อีกครั้ง / An error occurred. Please try again.', 'error');
                }
            } catch (err) {
                showNotification('ไม่สามารถเชื่อมต่อกับเซิร์ฟเวอร์ได้ / Unable to connect. Please try again.', 'error');
            } finally {
                btn.textContent = 'ยืนยันการนัดหมาย / Submit Request';
                btn.disabled = false;
            }
        });
    }

    function onReady(fn) {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', fn);
        } else {
            fn();
        }
    }

    onReady(initPhoneValidation);
    onReady(initTestDriveForm);
})();
