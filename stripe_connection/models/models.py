# -*- coding: utf-8 -*-

from odoo import models, fields, api
import stripe
from odoo.exceptions import UserError, ValidationError


class stripe_connection(models.Model):
    _name = 'stripe_connection.stripe_connection'
    _rec_name = 'customer_name'

    cqpture_payment = fields.Char()
    capture_payment_intent_id = fields.Char()
    invoice_number = fields.Char('Invoice No.')
    customer_name = fields.Char('Customer')
    capture_payment_json = fields.Char('Capture Payment JSON')
    refunded = fields.Char('Refunded')

    @api.model
    def create(self, vals):
        res = super(stripe_connection, self).create(vals)
        return res

    def action_refund(self):
        stripe.api_key = self.env['payment.acquirer'].search([('name', '=', 'Stripe')]).stripe_secret_key
        try:
            intent = stripe.PaymentIntent.retrieve(self.capture_payment_intent_id)
            intent['charges']['data'][0].refund()
            self.write({'refunded': 'yes'})
            pass
        except:
            raise ValidationError('Payment already refunded')

class CustomInvoiceAccount(models.Model):
    _inherit = 'account.invoice'

    pickup_form = fields.Binary('Powder Pickup Form', description = '')

class CustomAnswersReportPdf(models.AbstractModel):
    _name = 'report.stripe_connection.custom_pickup_form_report'

    @api.model
    def _get_report_values(self,docids, data):
        if data:
            return {
                'doc_model': 'stripe_connection.stripe_connection',
                'data': data,
                'report_type': data.get('report_type') if data else '',
            }

