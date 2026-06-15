import json
import logging

import requests as _requests

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class BsTestDriveController(http.Controller):

    @http.route('/test-drive/submit', type='jsonrpc', auth='public', website=True, csrf=False)
    def submit_test_drive(self, full_name=None, phone=None, line_id=None, email=None,
                          test_drive_date=None, test_drive_time=None, location=None,
                          recaptcha_token_response=None, **kwargs):
        ip_addr = request.httprequest.remote_addr
        recaptcha_result = request.env['ir.http']._verify_recaptcha_token(
            ip_addr, recaptcha_token_response or '', 'test_drive'
        )
        if recaptcha_result not in ('is_human', 'no_secret'):
            _logger.warning(
                'TestDrive: reCAPTCHA failed (%s) for ip %s',
                recaptcha_result, ip_addr,
            )
            return {'success': False, 'error': 'recaptcha_failed'}

        if not full_name or not phone:
            return {'success': False, 'error': 'required_fields_missing'}

        config = request.env['bs.api.testdrive.config'].sudo().search([], limit=1)
        if not config or not config.api_key or not config.api_url:
            _logger.warning('TestDrive: API config not found or incomplete')
            return {'success': False, 'error': 'api_not_configured'}

        parts = full_name.strip().split(' ', 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else '-'

        custom_fields = [{'field_name': 'Interest', 'field_value': 'testdrive'}]
        if test_drive_date:
            custom_fields.append({'field_name': 'TestDrive_Date', 'field_value': test_drive_date})
        if test_drive_time:
            custom_fields.append({'field_name': 'TestDrive_Time', 'field_value': test_drive_time})
        if location:
            custom_fields.append({'field_name': 'Preferred_Location', 'field_value': location})
        if line_id:
            custom_fields.append({'field_name': 'Line_ID', 'field_value': line_id})

        crm_payload = {
            'business_id': config.business_id or '',
            'source': {
                'type': 'website_form',
                'ref': request.httprequest.referrer or request.httprequest.url,
                'data': {'google-cid': '', 'google-ua': '', 'google-gclid': ''},
            },
            'data': {
                'first_name': first_name,
                'last_name': last_name,
                'phone': phone,
                'email': email or '',
                'custom': custom_fields,
            },
            'gate_id': config.gate_id or '',
            'specified_recipient': '',
        }

        request_str = json.dumps(crm_payload, ensure_ascii=False)
        state = 'error'
        response_str = ''
        http_status = 0
        error_message = ''

        try:
            resp = _requests.post(
                config.api_url,
                data=request_str.encode('utf-8'),
                headers={
                    'Content-Type': 'application/json',
                    'cache-control': 'no-cache',
                    'Authorization': config.api_key,
                },
                timeout=30,
            )
            http_status = resp.status_code
            response_str = resp.text
            if resp.status_code == 200:
                state = 'success'
            else:
                error_message = 'HTTP %d: %s' % (resp.status_code, resp.text[:300])
        except _requests.exceptions.Timeout:
            error_message = 'Request timeout (30s)'
        except _requests.exceptions.RequestException as exc:
            error_message = str(exc)[:500]
            _logger.exception('TestDrive: API call failed for %s', phone)

        request.env['bs.api.testdrive.log'].sudo().create({
            'full_name': full_name,
            'phone': phone,
            'email': email or '',
            'line_id': line_id or '',
            'test_drive_date': test_drive_date or '',
            'test_drive_time': test_drive_time or '',
            'preferred_location': location or '',
            'request_payload': request_str,
            'response_payload': response_str,
            'state': state,
            'http_status': http_status,
            'error_message': error_message,
        })

        return {'success': state == 'success'}
