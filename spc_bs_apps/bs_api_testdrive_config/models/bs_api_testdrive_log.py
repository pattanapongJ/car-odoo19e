from __future__ import annotations

from odoo import fields, models


class BsApiTestdriveLog(models.Model):
    _name = 'bs.api.testdrive.log'
    _description = 'Test Drive Submission Log'
    _order = 'create_date desc'
    _rec_name = 'full_name'

    # Customer info (immutable — snapshot of what was submitted)
    full_name: str = fields.Char(string='Full Name', readonly=True)
    phone: str = fields.Char(string='Phone', readonly=True, index=True)
    email: str = fields.Char(string='Email', readonly=True)
    line_id: str = fields.Char(string='Line ID', readonly=True)
    test_drive_date: str = fields.Char(string='Preferred Date', readonly=True)
    test_drive_time: str = fields.Char(string='Preferred Time', readonly=True)
    preferred_location: str = fields.Char(string='Preferred Location', readonly=True)

    # API result
    state: str = fields.Selection(
        selection=[('success', 'Success'), ('error', 'Error')],
        string='Status',
        readonly=True,
        index=True,
    )
    http_status: int = fields.Integer(string='HTTP Status', readonly=True)
    error_message: str = fields.Text(string='Error Detail', readonly=True)

    # Raw payloads for debugging
    request_payload: str = fields.Text(string='Request (JSON)', readonly=True)
    response_payload: str = fields.Text(string='Response (JSON)', readonly=True)
