# -*- coding: utf-8 -*-

from openerp import models, fields, api, _
from openerp.exceptions import UserError, RedirectWarning, ValidationError

#PARA FECHAS
from datetime import datetime, timedelta

#OTROS
import openerp.addons.decimal_precision as dp

##### SOLUCIONA CUALQUIER ERROR DE ENCODING (CARACTERES ESPECIALES)
import sys
reload(sys)  
sys.setdefaultencoding('utf8')

class stock_move_add(models.TransientModel):
    _name = "stock.move.add"
    _description = "Add new Move for Production Order"


    def _get_default_location(self):
        location = False
        if self._context.get('default_picking_type_id'):
            location = self.env['stock.picking.type'].browse(self.env.context['default_picking_type_id']).default_location_src_id
        if not location:
            location = self.env.ref('stock.stock_location_stock', raise_if_not_found=False)
        return location and location.id or False



    date_expected = fields.Datetime('Scheduled Date', required=True, default=fields.Datetime.now)
    product_id = fields.Many2one('product.product', 'Product', required=True, domain=[('type','<>','service')])

    #digits_compute
    product_qty = fields.Float('Quantity', default=1.0, digits=dp.get_precision('Product Unit of Measure'), required=True)
    product_uom = fields.Many2one('product.uom', 'Unit of Measure')
    product_uos_qty = fields.Float('Quantity (UOS)', digits=dp.get_precision('Product Unit of Measure'))
    product_uos = fields.Many2one('product.uom', 'Product UOS')
    location_id = fields.Many2one('stock.location', 'Source Location', required=True, default=_get_default_location)
    location_dest_id = fields.Many2one('stock.location', 'Destination Location', required=True)
    prodlot_id = fields.Many2one('stock.production.lot', 'Serial Number')

 
    ###########################################
    #METODOS ON_CHANGE
    ###########################################

    @api.onchange('product_id') # if these fields are changed, call method
    def onchange_product_id(self):
        vals = {}

        if self.product_id != False:
            product_uom = self.product_id.uom_id.id
        else:
            product_uom = False

        vals['product_uom'] = product_uom
        self.update(vals)



    def add_production_consume_line(self, new_move, production):
        stock_move = self.env['stock.move']
        procurement_order = self.env['procurement.order']
        
        # Internal shipment is created for Stockable and Consumer Products
        if new_move.product_id.type not in ('product', 'consu'):
            return False
        destination_location_id = new_move.location_dest_id.id or production.product_id.property_stock_production.id
        source_location_id = new_move.location_id.id or production.location_src_id.id
        original_quantity = production.product_qty - production.qty_produced
        move_id = stock_move.create({
            'name': production.name,
            'date': new_move.date_expected,
            'date_expected': new_move.date_expected,
            'product_id': new_move.product_id.id,
            'product_uom_qty': new_move.product_qty,
            'product_uom': new_move.product_id.uom_id.id,
            'product_uos_qty': new_move.product_uos and new_move.product_uos_qty or False,
            'product_uos': new_move.product_uos and new_move.product_uos.id or False,
            'location_id': source_location_id,
            'location_dest_id': destination_location_id,
            #'move_dest_id': production.move_prod_id.id,
            #'production_id': production.id,
            'state': 'confirmed',
            'origin': production.name,
            'group_id': production.procurement_group_id.id,
            'company_id': production.company_id.id,
            'procurement_id': production.procurement_ids and production.procurement_ids[0].id or False,
            'unit_factor': new_move.product_qty / original_quantity,
            'warehouse_id': (new_move.location_id or production.location_src_id).get_warehouse().id,
            'price_unit': new_move.product_id.standard_price,
            'bom_line_id': production.bom_id.bom_line_ids[0].id,
            'new_bom_line': True, #INDICA QUE ES UNA LINEA QUE NO SE ENCUENTRA EN LA LDM ORIGINAL
            'propagate': False,
            #'has_tracking': 'none',
        })
        #print 'procurement: ',production.procurement_ids and production.procurement_ids[0].id or False,
        #print 'move_id ', move_id.id
        production.write({'move_raw_ids': [(4, move_id.id)]})
        #SE REVISA SI TIENEN PROCUREMENTS Y SE CREAN
        production._adjust_procure_method()
        #print 'move_id.procure_method: ',move_id.procure_method
        procurements = False
        # create procurements for make to order moves
        if move_id.procure_method == 'make_to_order':
            move_id.state = 'waiting'
            procurements = self.env['procurement.order']
            procurements |= procurements.create(move_id._prepare_procurement_from_move())
        if procurements:
            procurements.run()

        #SI LAS ORDENES DE TRABAJAO YA HAVIAN SIDO CREADAS CON ANTERIORIDAD SE REPASAN Y SE CREAN LOS LOTES
        #print 'production.workorder_ids: ',production.workorder_ids
        #if production.workorder_ids != False:
        if production.state not in ('confirmed','cancel','done'):
            #print 'production.workorder_ids[-1].id: ',production.workorder_ids[-1].id
            if move_id.product_id.tracking != 'none':
                #print 'entro'
                self.add_lot_id2(move_id,production.workorder_ids[-1])

        return move_id

    def add_lot_id2(self, move, workorder):
        self.ensure_one()
        MoveLot = self.env['stock.move.lots']
        qty = move.unit_factor * workorder.qty_producing
        #print 'move.product_id.name: ',move.product_id.name
        if move.product_id.tracking == 'serial':
            while float_compare(qty, 0.0, precision_rounding=move.product_uom.rounding) > 0:
                MoveLot.create({
                    'move_id': move.id,
                    'quantity': min(1, qty),
                    'quantity_done': min(1, qty),
                    'production_id': workorder.production_id.id,
                    'workorder_id': workorder.id,
                    'product_id': move.product_id.id,
                    'done_wo': False,
                })
                qty -= 1
        else:
            MoveLot.create({
                'move_id': move.id,
                'quantity': qty,
                'quantity_done': qty,
                'product_id': move.product_id.id,
                'production_id': workorder.production_id.id,
                'workorder_id': workorder.id,
                'done_wo': False,
                })


    def add_mo_product(self):
        """ Add new move.
        @return: True.
        """        
        if self.env.context is None:
            self.env.context = {}
        
        if not self.env.context.get('mo_id', False) or not self.env.context.get('active_id', False) :
            raise osv.except_osv(_('Exception!'), _('Can not create the Move related to MO'))
        
        new_move = self.browse(self.ids)[0]
        
        mrp_obj = self.env['mrp.production']
        production = mrp_obj.browse(self.env.context.get('mo_id', False) or self.env.context.get('active_id', False))


            
        found = False
        for move in production.move_raw_ids:
            if (move.product_id.id == new_move.product_id.id) and (move.state not in ('cancel','done')):
                if move.procure_method != 'make_to_order': #SI ES BAJO PEDIDO SE TIENE QUE AGREGAR EN OTRA LINEA, NO LA MISMA
                    qty_in_line_uom = self.product_qty
                    # vals={'product_uom_qty': move.product_qty + qty_in_line_uom}
                    # # if qty_in_line_uos:
                    # #     vals={'product_uos_qty': move.product_uos_qty or 0.0 + qty_in_line_uos}
                    # self.env['stock.move'].browse(move.id).write(vals)
                    # found = True
                    # break

                    #NUEVA VERSION
                    old_move = self.env['stock.move'].browse(move.id)
                    new_qty = old_move.product_qty + new_move.product_qty
                    vals={'product_uom_qty': move.product_qty + qty_in_line_uom,'unit_factor': new_qty / (production.product_qty - production.qty_produced)}
                    self.env['stock.move'].browse(move.id).write(vals)
                    found = True
                    break
        consume_move_id = False
        if not found:
            #print 'NOT FOUND'
            consume_move_id = self.add_production_consume_line(new_move, production)
            #print 'consume_move_id, ',consume_move_id


        return True

