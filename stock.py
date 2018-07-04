# -*- coding: utf-8 -*-

from openerp import models, fields, api, _
from openerp.exceptions import UserError

# SOLUCIONA CUALQUIER ERROR DE ENCODING (CARACTERES ESPECIALES)
import sys
reload(sys)
sys.setdefaultencoding('utf8')


class stock_move(models.Model):
    _inherit = "stock.move"

    new_bom_line = fields.Boolean('Nueva linea', help='INDICA QUE ES UNA LINEA QUE NO SE ENCUENTRA EN LA LDM ORIGINAL')

    @api.multi
    def action_consume_cancel(self):
        """Cancel the moves and if all moves are cancelled it cancels the picking."""
        # TDE DUMB: why is cancel_procuremetn in ctx we do quite nothing ?? like not updating the move ??
        if any(move.state == 'done' for move in self):
            raise UserError(_('You cannot cancel a stock move that has been set to \'Done\'.'))
        procurements = self.env['procurement.order']
        for move in self:
            if move.reserved_quant_ids:
                move.quants_unreserve()
            if self.env.context.get('cancel_procurement'):
                if move.propagate:
                    pass
            else:
                if move.move_dest_id:
                    if move.propagate:
                        move.move_dest_id.action_cancel()
                    elif move.move_dest_id.state == 'waiting':
                        # If waiting, the chain will be broken and we are not sure if we can still wait for it (=> could take from stock instead)
                        move.move_dest_id.write({'state': 'confirmed'})
                if move.procurement_id:
                    procurements |= move.procurement_id
        self.write({'state': 'cancel', 'move_dest_id': False})
        if procurements:
            procurements.check()
        return True
