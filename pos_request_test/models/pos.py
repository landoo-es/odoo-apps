# -*- encoding: utf-8 -*-

import re
from datetime import datetime

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import Warning
import odoo.addons.decimal_precision as dp


class PosRequest(models.Model):
    _name = 'pos.request'
    _order = 'date DESC'

    name = fields.Char('Number', default='/', required=True, states={'done': [('readonly', True)]})
    partner_id = fields.Many2one('res.partner', string='Partner', states={'done': [('readonly', True)]})
    homedelivery_client = fields.Many2one('res.partner', string='Home delivery partner',
                                          states={'done': [('readonly', True)]})
    reference = fields.Char('Reference', states={'done': [('readonly', True)]})
    barcode = fields.Char('Barcode', oldname='ean13', states={'done': [('readonly', True)]})
    date = fields.Datetime('Date', default=fields.Datetime.now, states={'done': [('readonly', True)]})
    date_to_deliver = fields.Datetime('Date to deliver', states={'done': [('readonly', True)]})
    date_cancel = fields.Datetime('Date cancel', readonly=True, states={'done': [('readonly', True)]})
    date_delivered = fields.Datetime('Date delivered', readonly=True, states={'done': [('readonly', True)]})
    user_id = fields.Many2one('res.users', string='User', states={'done': [('readonly', True)]})
    pos_session_id = fields.Many2one('pos.session', string='POS Session', states={'done': [('readonly', True)]})
    pos_config_id = fields.Many2one('pos.config', related='pos_session_id.config_id', string='POS',
                                    states={'done': [('readonly', True)]})
    company_id = fields.Many2one('res.company', string='Company', required=True, states={'done': [('readonly', True)]},
                                 default=lambda self: self.env.user.company_id)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string="Company Currency",
                                  readonly=True, store=True, states={'done': [('readonly', True)]})
    line_ids = fields.One2many('pos.request.line', 'request_id', 'Lines', states={'done': [('readonly', True)]})
    state = fields.Selection([
        ('cancel', 'Cancel'),
        ('in_progress', 'Waiting availability'),
        ('to_deliver', 'To deliver'),
        ('delivered', 'Delivered'),
        ('done', 'Done')
    ], string='State', default='in_progress')

    prepaid_qty = fields.Float('Amount prepaid', digits=dp.get_precision('Product Price'),
                               states={'done': [('readonly', True)]})
    amount_to_paid = fields.Float('Amount to paid', compute='_rest_to_paid', digits=dp.get_precision('Product Price'),
                                  readonly=True, store=True, track_visibility='always',
                                  states={'done': [('readonly', True)]})
    amount_untaxed = fields.Float('Untaxed Amount', compute='_amount_all', digits=dp.get_precision('Product Price'),
                                  readonly=True, store=True, track_visibility='always',
                                  states={'done': [('readonly', True)]})
    amount_tax = fields.Float('Taxes', compute='_amount_all', digits=dp.get_precision('Product Price'),
                              readonly=True, store=True, track_visibility='always',
                              states={'done': [('readonly', True)]})
    amount_total = fields.Float('Total', compute='_amount_all', digits=dp.get_precision('Product Price'),
                                readonly=True, store=True, track_visibility='always',
                                states={'done': [('readonly', True)]})
    receipt_html = fields.Text('Receipt Arch', states={'done': [('readonly', True)]})
    notes = fields.Text('Home delivery description', states={'done': [('readonly', True)]})
    can_to_deliver = fields.Boolean('Can pass to delivery', compute='_compute_can_to_deliver',
                                    states={'done': [('readonly', True)]})

    def _compute_can_to_deliver(self):
        value = True
        if self.state not in 'delivered':
            for line in self.line_ids:
                if line.state != 'to_deliver':
                    value = False
                break
        return value

    @api.depends('prepaid_qty')
    def _rest_to_paid(self):
        for request in self:
            request.update({
                'amount_to_paid': request.amount_total - request.prepaid_qty
            })

    @api.depends('line_ids.price_total')
    def _amount_all(self):
        for request in self:
            amount_untaxed = amount_tax = 0.0
            for line in request.line_ids:
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_tax
            request.update({
                'amount_untaxed': request.currency_id.round(amount_untaxed),
                'amount_tax': request.currency_id.round(amount_tax),
                'amount_total': amount_untaxed + amount_tax,
            })


class PosRequestLine(models.Model):
    _name = 'pos.request.line'
    _rec_name = 'product_id'

    product_id = fields.Many2one('product.product', string='Product', require=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string="Company Currency",
                                  readonly=True, store=True)
    qty = fields.Float('Quantity', default=1.0, digits=dp.get_precision('Unit of Measure'))
    request_id = fields.Many2one('pos.request', string='Request')
    note = fields.Text('Notes', placeholder="Comments...")
    date = fields.Datetime('Date', related='request_id.date')

    tax_id = fields.Many2many('account.tax', string='Taxes',
                              domain=['|', ('active', '=', False), ('active', '=', True)])

    price_unit = fields.Float('Unit Price', required=True, digits=dp.get_precision('Product Price'), default=0.0)
    price_subtotal = fields.Monetary(compute='_compute_amount', string='Subtotal', readonly=True, store=True)
    price_tax = fields.Monetary(compute='_compute_amount', string='Taxes', readonly=True, store=True)
    price_total = fields.Monetary(compute='_compute_amount', string='Total', readonly=True, store=True)
    procurement_order_id = fields.Many2one('procurement.order', string='Procurement order')
    v_procurement_order_id = fields.Many2one('procurement.order', string='Virtual procurement order')
    state = fields.Selection([
        ('cancel', 'Canceled'),
        ('in_progress', 'Waiting availability'),
        ('to_deliver', 'To deliver'),
        ('delivered', 'Delivered'),
    ], string='State', default='in_progress')

    def action_done(self):
        self.write({'state': 'to_deliver'})
        self.request_id.check_change_done()

    def cancel(self):
        self.write({'state': 'cancel'})
        if self.procurement_order_id:
            self.procurement_order_id.cancel()
        if self.v_procurement_order_id:
            self.v_procurement_order_id.cancel()

    def change_state(self, state):
        self.write({'state': state})

    @api.multi
    @api.onchange('product_id')
    def onchange_product(self):
        if self.product_id:
            self._compute_tax_id()
            self.price_unit = self.product_id.lst_price

    @api.multi
    def _compute_tax_id(self):
        for line in self:
            fpos = line.request_id.pos_session_id.config_id.default_fiscal_position_id.id if line.request_id.pos_session_id.config_id.default_fiscal_position_id else False
            fpos = line.request_id.partner_id.property_account_position_id if line.request_id.partner_id else fpos
            if not fpos:
                break
            taxes = line.product_id.taxes_id.filtered(lambda r: not line.company_id or r.company_id == line.company_id)
            line.tax_id = fpos.map_tax(taxes, line.product_id, line.request_id.partner_id) if fpos else taxes

    @api.depends('price_unit', 'tax_id')
    def _compute_amount(self):
        for line in self:
            price = line.price_unit
            taxes = line.tax_id.compute_all(price, line.request_id.currency_id, line.qty,
                                            product=line.product_id, partner=line.request_id.partner_id)
            line.update({
                'price_tax': taxes['total_included'] - taxes['total_excluded'],
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })


class PosOrder(models.Model):
    _inherit = "pos.order"

    @api.model
    def _order_fields(self, ui_order):
        request_ids = []
        for l in ui_order['lines']:
            line = l[2]
            request = line.get('request_info', {})
            request = request.get('id', False) if request else False
            request_deliver = line.get('request_deliver', False)
            if request_deliver and request and request not in request_ids:
                request_ids.append(request)

        for request in self.env['pos.request'].browse(request_ids):
            request.do_done()

        return super(PosOrder, self)._order_fields(ui_order)


class PosConfig(models.Model):
    _inherit = 'pos.config'

    request_product_id = fields.Many2one('product.product', string='Product to request',
                                         default=lambda self: self._default_request_product())
    request_previous_days = fields.Integer('Previous days', default=15,
                                           help='To avoid a massive load of requests you can set a number of days to load requests from the opening date of the session less the number of days established, example: 16/01/1970 - 15 days = 01/01/1970 it will be the date from which the requests will be loaded')
    request_procurement_order = fields.Boolean('Procurement order', default=False)
    request_warehouse_id = fields.Many2one('stock.warehouse', string='Procurement warehouse')
    request_v_location_id = fields.Many2one('stock.location', string='Virtual location')

    request_reference = fields.Boolean('Allow Reference', default=False)
    request_filter_products = fields.Boolean('Filter products', default=False,
                                             help="If you activate this option, you must check the 'Available POS request' field in the products to be ordered.")
    request_show_all = fields.Boolean('Show all request', default=False,
                                      help='This option allows to load the requests of all the stores and that can be delivered in the different POS')
    request_client_required = fields.Boolean('Customer required')
    request_date_required = fields.Boolean('Delivery date required')

    @api.model
    def _default_request_product(self):
        try:
            product_id = self.env['ir.model.data'].get_object_reference('pos_request_test', 'product_pos_request')[1]
        except ValueError:
            product_id = False
        return product_id
