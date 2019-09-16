# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import models, fields, api
from odoo.addons.queue_job.job import job, related_action
from odoo.addons.connector.exception import RetryableJobError


class PrestashopBinding(models.AbstractModel):
    _inherit = 'prestashop.binding'
    

    @api.multi
    def resync_export(self):
        for record in self:
            if self.env.context.get('connector_delay'):
                record.with_context({'lang': 'en_US'}).with_delay().export_record()
            for record in self:
                record.with_context({'lang': 'en_US'}).export_record()

        return True


