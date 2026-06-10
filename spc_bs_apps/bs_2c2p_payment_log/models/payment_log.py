# -*- coding: utf-8 -*-
import json
from odoo import api, fields, models


class BsPayment2c2pLog(models.Model):
    _name = 'bs.payment.2c2p.log'
    _description = '2C2P Payment Callback Log'
    _order = 'create_date desc'
    _rec_name = 'reference'

    log_type = fields.Selection(
        selection=[('notify', 'Backend Webhook'), ('return', 'Frontend Return')],
        string='Type',
        required=True,
        index=True,
    )
    reference = fields.Char(string='Order Reference', index=True)
    payment_status = fields.Char(string='Payment Status Code')
    status_label = fields.Char(
        string='Status',
        compute='_compute_status_label',
        store=True,
    )
    transaction_ref = fields.Char(string='2C2P Transaction Ref')
    channel_response = fields.Char(string='Channel Response')
    raw_data = fields.Text(string='Raw POST Data')
    transaction_id = fields.Many2one(
        'payment.transaction',
        string='Odoo Transaction',
        compute='_compute_transaction_id',
        store=True,
    )
    transaction_state = fields.Selection(
        related='transaction_id.state',
        string='Odoo State',
        store=True,
    )

    @api.depends('payment_status')
    def _compute_status_label(self):
        mapping = {
            '000': 'Success',
            '001': 'Pending',
            '003': 'Cancelled',
        }
        for rec in self:
            rec.status_label = mapping.get(
                rec.payment_status,
                f'Error ({rec.payment_status})' if rec.payment_status else '',
            )

    @api.depends('reference')
    def _compute_transaction_id(self):
        for rec in self:
            if rec.reference:
                rec.transaction_id = self.env['payment.transaction'].search(
                    [('reference', '=', rec.reference)], limit=1
                )
            else:
                rec.transaction_id = False

    @classmethod
    def _build_from_post(cls, log_type, post):
        return {
            'log_type': log_type,
            'reference': post.get('order_id') or post.get('reference', ''),
            'payment_status': post.get('payment_status', ''),
            'transaction_ref': post.get('transaction_ref', ''),
            'channel_response': post.get('channel_response_desc', ''),
            'raw_data': json.dumps(post, indent=2, default=str),
        }
