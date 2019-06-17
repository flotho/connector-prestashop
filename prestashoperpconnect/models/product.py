# -*- coding: utf-8 -*-
###############################################################################
#                                                                             #
#   Prestashoperpconnect for OpenERP                                          #
#   Copyright (C) 2013 Akretion                                               #
#                                                                             #
#   This program is free software: you can redistribute it and/or modify      #
#   it under the terms of the GNU Affero General Public License as            #
#   published by the Free Software Foundation, either version 3 of the        #
#   License, or (at your option) any later version.                           #
#                                                                             #
#   This program is distributed in the hope that it will be useful,           #
#   but WITHOUT ANY WARRANTY; without even the implied warranty of            #
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the             #
#   GNU Affero General Public License for more details.                       #
#                                                                             #
#   You should have received a copy of the GNU Affero General Public License  #
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.     #
#                                                                             #
###############################################################################

import logging
from openerp.osv import fields, orm
from datetime import datetime
from datetime import timedelta
from prestapyt import PrestaShopWebServiceError
from ..unit.backend_adapter import (
                            GenericAdapter, 
                            PrestaShopCRUDAdapter)
from openerp.addons.connector.unit.backend_adapter import BackendAdapter                            
from openerp.addons.connector.connector import ConnectorUnit
from openerp.addons.connector.exception import FailedJobError
from openerp.addons.connector.exception import NothingToDoJob
from openerp.addons.connector.queue.job import job
from openerp.addons.connector.unit.synchronizer import ImportSynchronizer
from ..unit.import_synchronizer import (PrestashopImportSynchronizer, 
                        TranslatableRecordImport,
                        import_product_image,
                        import_batch,
                        import_record)
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from ..backend import prestashop
from ..connector import add_checkpoint
from ..connector import get_environment
from ..unit.exception import OrderImportRuleRetry
from .product_combination import (
                #ProductCombinationBatchImporter, 
                ProductCombinationRecordImport)

_logger = logging.getLogger(__name__)

class product_template(orm.Model):
    _inherit = 'product.template'

    _columns = {
        'prestashop_bind_ids': fields.one2many(
            'prestashop.product.template',
            'openerp_id',
            string='PrestaShop Bindings'
        ),
        'final_price': fields.float('Final Price'),
        'list_price_tax': fields.float('Sale Price Including Tax'),
    }

    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        default['prestashop_bind_ids'] = []
        return super(product_template, self).copy(
            cr, uid, id, default=default, context=context
        )

    def update_prestashop_quantities(self, cr, uid, ids, context=None):
        _logger.debug("update_prestashop_quantities context %s and datas %s" % (context, ids))
        for template in self.browse(cr, uid, ids, context=context):
#             for prestashop_template in template.prestashop_bind_ids:
#                 prestashop_template.recompute_prestashop_qty()
#             prestashop_combinations = template.product_variant_ids
#             for prestashop_combination in prestashop_combinations:
#                 prestashop_combination.recompute_prestashop_qty()
                
            prestashop_combinations = (
                len(template.product_variant_ids) > 1
                and template.product_variant_ids) or []
            if not prestashop_combinations:
                for prestashop_product in template.prestashop_bind_ids:
                    prestashop_product.recompute_prestashop_qty()
            else:
                for prestashop_combination in prestashop_combinations:
                    for combination_binding in \
                            prestashop_combination.prestashop_bind_ids:
                        combination_binding.recompute_prestashop_qty()
        return True


class prestashop_product_template(orm.Model):
    _name = 'prestashop.product.template'
    _inherit = 'prestashop.binding'
    _inherits = {'product.template': 'openerp_id'}
        
    _columns = {
        'openerp_id': fields.many2one(
            'product.template',
            string='Template',
            required=True,
            ondelete='cascade'
        ),
        # TODO FIXME what name give to field present in
        # prestashop_product_product and product_product
        'always_available': fields.boolean(
            'Active',
            help='if check, this object is always available'),
        'quantity': fields.float(
            'Computed Quantity',
            help="Last computed quantity to send on Prestashop."
        ),
        'description_html': fields.html(
            'Description',
            translate=True,
            help="Description html from prestashop",
        ),
        'description_short_html': fields.html(
            'Short Description',
            translate=True,
        ),
        'date_add': fields.datetime(
            'Created At (on Presta)',
            readonly=True
        ),
        'date_upd': fields.datetime(
            'Updated At (on Presta)',
            readonly=True
        ),
        'default_shop_id': fields.many2one(
            'prestashop.shop',
            'Default shop',
            required=True
        ),
        'link_rewrite': fields.char(
            'Friendly URL',
            translate=True,
            required=False,
        ),
        'available_for_order': fields.boolean(
            'Available For Order'
        ),
        'show_price': fields.boolean(
            'Show Price'
        ),
        'combinations_ids': fields.one2many(
            'prestashop.product.combination',
            'main_template_id',
            string='Combinations'
        ),
        'reference': fields.char('Original reference'),
    }

    _defaults = {
        'available_for_order': True,
        'show_price': True,
        'always_available': True
    }
    _sql_constraints = [
        ('prestashop_uniq', 'unique(backend_id, prestashop_id)',
         "A product with the same ID on Prestashop already exists")
    ]

    def recompute_prestashop_qty(self, cr, uid, ids, context=None):
        if not hasattr(ids, '__iter__'):
            ids = [ids]

        for product in self.browse(cr, uid, ids, context=context):
            
            new_qty = self._prestashop_qty(cr, uid, product, context=context)
            self.write(
                cr, uid, product.id,
                {'quantity': new_qty},
                context=context
            )
            
        return True

    def _prestashop_qty(self, cr, uid, product, context=None):
        if context is None:
            context = {}
        backend = product.backend_id
        stock = backend.warehouse_id.lot_stock_id
        stock_field = backend.quantity_field        
        location_ctx = context.copy()
        location_ctx['location'] = stock.id
        product_stk = self.read(
            cr, uid, product.id, [stock_field], context=location_ctx
        )
        return product_stk[stock_field]


@prestashop
class TemplateRecordImport(TranslatableRecordImport):

    """ Import one translatable record """
    _model_name = [
        'prestashop.product.template',
    ]

    _translatable_fields = {
        'prestashop.product.template': [
            'name',
            'description',
            'link_rewrite',
            'description_short',
        ],
    }

    def _import_dependencies(self):
        self._import_default_category()
        self._import_categories()
        self.import_product_options()
        
    def _after_import(self, erp_id):
        #self.import_images(erp_id.id) # This one is commented because of PS error unsolved : PrestaShopWebServiceError: 'PrestaShop error: 500 Internal Server Error. [PHP Notice #8] Undefined index: id_image (
        # TODO : check what's wrong in this mapper
#        self.import_default_image(erp_id.id)
        self.import_supplierinfo(erp_id.id)
        self.import_combinations()
        self.attribute_line(erp_id.id)
        self.deactivate_default_product(erp_id.id)

    def deactivate_default_product(self, erp_id):
        template = self.session.browse(
            'prestashop.product.template', erp_id)
                
        if template.product_variant_count != 1:
            for product in template.product_variant_ids:                
                if not product.attribute_value_ids:
                    self.session.write('product.product', [product.id],
                                       {'active': False})

    def attribute_line(self, erp_id):        
        template = self.session.browse(
            'prestashop.product.template', erp_id)
        attr_line_value_ids = []
        _logger.debug("Manage template %s Attribute Lines %s" % (template, template.attribute_line_ids))
        for attr_line in template.attribute_line_ids:
            attr_line_value_ids.extend(attr_line.value_ids.ids)
        template_id = template.openerp_id.id
        product_ids = self.session.search('product.product', [
            ('product_tmpl_id', '=', template_id)]
        )
        if product_ids:
            products = self.session.browse('product.product',
                                           product_ids)
            attribute_ids = []            
            for product in products:
                for attribute_value in product.attribute_value_ids:
                    attribute_ids.append(attribute_value.attribute_id.id)
                    # filter unique id for create relation
#            _logger.debug("Attributes to ADD")
#            _logger.debug(attribute_ids)
            if attribute_ids:
                for attribute_id in set(attribute_ids):
                    value_ids = []
                    for product in products:                        
                        for attribute_value in product.attribute_value_ids:                                                      
                            if (attribute_value.attribute_id.id == attribute_id
                                and attribute_value.id not in
                                    attr_line_value_ids):
                                value_ids.append(attribute_value.id)
                    if value_ids:
                        self.session.create('product.attribute.line', {
                            'attribute_id': attribute_id,
                            'product_tmpl_id': template_id,
                            'value_ids': [(6, 0, set(value_ids))]}
                        )

    def import_product_options(self):
        prestashop_record = self._get_prestashop_data()
        associations = prestashop_record.get('associations', {})

        option_values = associations.get('product_option_values', {}).get(
            'product_options_values', [])
        if not isinstance(option_values, list):
            option_values = [option_values]
        
        _logger.debug("OPTIONS in TEMPLATE %s" % option_values)
#        _logger.debug(prestashop_record)
#        _logger.debug(associations)
#        _logger.debug(option_values)
        backend_adapter = self.get_connector_unit_for_model(
            BackendAdapter,
            'prestashop.product.combination.option.value'
        )
        for option_value in option_values:
            
            option = backend_adapter.read(option_value['id'])
            _logger.debug("import option value %s for optoin %s" % (option_value, option))
            #TODO: S'assurer qu'on n'importe pas inutilement
            import_record(
                self.session,
                'prestashop.product.combination.option.value',
                self.backend_record.id,
                option_value['id'],                                       
            )
    
    def import_combinations(self):
        
        prestashop_record = self._get_prestashop_data()
        associations = prestashop_record.get('associations', {})

        combinations = associations.get('combinations', {}).get(
            self.backend_record.get_version_ps_key('combination'), [])
        
        if not isinstance(combinations, list):
            combinations = [combinations]
        
        priority = 15
#        variant_adapter = self.get_connector_unit_for_model(
#                ProductCombinationRecordImport, 'prestashop.product.combination')
#        importer = self.unit_for(ProductCombinationBatchImporter, model='prestashop.product.combination')
#        self.import_product_options()
        _logger.debug("IMPORT COMBINATIONS %s from associations %s" % (combinations, associations ))
        for combination in combinations:            
#            variant_adapter._import_record(
#                        combination['id'], priority
#                        )
#            priority += 15
            _logger.debug("IMPORT COMBINATION %s From template %s" % (combination, prestashop_record))
            import_record(
                self.session,
                'prestashop.product.combination',
                self.backend_record.id,
                combination['id'],                                       
            )

    def import_images(self, erp_id):
        prestashop_record = self._get_prestashop_data()
        associations = prestashop_record.get('associations', {})
        
        images = associations.get('images', {}).get(
            self.backend_record.get_version_ps_key('image'), {})

        if not isinstance(images, list):
            images = [images]
        for image in images:
            if image.get('id'):
                import_product_image.delay(
                    self.session,
                    'prestashop.product.image',
                    self.backend_record.id,
                    prestashop_record['id'],
                    image['id'],
                    priority=10,
                )

    def import_supplierinfo(self, erp_id):
        ps_id = self._get_prestashop_data()['id']
        filters = {
            'filter[id_product]': ps_id,
            'filter[id_product_attribute]': 0
        }
        import_batch(
            self.session,
            'prestashop.product.supplierinfo',
            self.backend_record.id,
            filters=filters
        )
        template = self.session.browse(
            'prestashop.product.template', erp_id)
        template_id = template.openerp_id.id
        ps_supplierinfo_ids = self.session.search(
            'prestashop.product.supplierinfo',
            [('product_tmpl_id', '=', template_id)]
        )
        ps_supplierinfos = self.session.browse(
            'prestashop.product.supplierinfo', ps_supplierinfo_ids
        )
        for ps_supplierinfo in ps_supplierinfos:
            try:
                ps_supplierinfo.resync()
            except PrestaShopWebServiceError:
                ps_supplierinfo.openerp_id.unlink()

    def import_default_image(self, erp_id):
        record = self._get_prestashop_data()
        if record['id_default_image']['value'] == '':
            return
        adapter = self.get_connector_unit_for_model(
            PrestaShopCRUDAdapter,
            'prestashop.product.image'
        )
        binder = self.get_binder_for_model()
        template_id = binder.to_openerp(record['id'])
        _logger.debug("Template default image")
        _logger.debug(template_id)
        
        try:
            image = adapter.read(record['id'],
                                 record['id_default_image']['value'])
            
            ctx = self.session.context.copy()
            ctx['connector_no_export'] = True
            _logger.debug("Template image")
            _logger.debug(image)
                        
            self.session.pool['prestashop.product.template'].write(
                self.session.cr, self.session.uid, [template_id],
                {"image": image['content']},
                context=ctx
                )
#            model = self.env['prestashop.product.template']
#                       .with_context(connector_no_export=True)
#            _logger.debug("Model : %s ", model)
#            binding = model.search(template_id)
#            _logger.debug("binding :")
#            _logger.debug(binding)
#            template_id.write({'image': image['content']})
#            self.session.write(
#                'prestashop.product.template',
#                [template_id],
#                {"image": image['content']}
#            )
        except PrestaShopWebServiceError:
            pass
        except IOError:
            pass

    def get_template_model_id(self):
        ids = self.session.search('ir.model', [
            ('model', '=', 'product.template')]
        )
        assert len(ids) == 1
        return ids[0]

    def _import_default_category(self):
        record = self.prestashop_record
        if int(record['id_category_default']):
            try:
                self._check_dependency(record['id_category_default'],
                                       'prestashop.product.category')
            except PrestaShopWebServiceError:
                pass

    def _import_categories(self):
        record = self.prestashop_record
        associations = record.get('associations', {})
        categories = associations.get('categories', {}).get('category', [])
        _logger.debug("IMPORT CATEGORIES %s" %  categories)
        if not isinstance(categories, list):
            categories = [categories]
        for category in categories:
            self._check_dependency(category['id'],
                                   'prestashop.product.category')


#
#class product_product(orm.Model):
#    _inherit = 'product.product'
#
#    _columns = {
#        'prestashop_bind_ids': fields.one2many(
#            'prestashop.product.combination',
#            'openerp_id',
#            string='PrestaShop Bindings'
#        ),
#        # This one is useful in order to override the template price. 
#        # In PS it's not possible to find extra price from combination so we have to compute it on the fly
##        'final_price': fields.float('Final Price'),
##        'list_price_tax': fields.float('Sale Price Including Tax'),
#    }
#
#    def copy(self, cr, uid, id, default=None, context=None):
#        if default is None:
#            default = {}
#        default['prestashop_bind_ids'] = []
#        return super(product_product, self).copy(
#            cr, uid, id, default=default, context=context
#        )
#        
#    def update_prestashop_quantities(self, cr, uid, ids, context=None):
#        for product in self.browse(cr, uid, ids, context=context):
#            product_template = product.product_tmpl_id
#            prestashop_combinations = (
#                len(product_template.product_variant_ids) > 1
#                and product_template.product_variant_ids) or []
#            if not prestashop_combinations:
#                for prestashop_product in product_template.prestashop_bind_ids:
#                    prestashop_product.recompute_prestashop_qty()
#            else:
#                for prestashop_combination in prestashop_combinations:
#                    for combination_binding in \
#                            prestashop_combination.prestashop_bind_ids:
#                        combination_binding.recompute_prestashop_qty()
#        return True

#
#class prestashop_product_product(orm.Model):
#    _name = 'prestashop.product.product'
#    _inherit = 'prestashop.binding'
#    _inherits = {'product.product': 'openerp_id'}

#    _columns = {
#        'openerp_id': fields.many2one(
#            'product.product',
#            string='Product',
#            required=True,
#            ondelete='cascade'
#        ),
#        # TODO FIXME what name give to field present in
#        # prestashop_product_product and product_product
#        'always_available': fields.boolean(
#            'Active',
#            help='if check, this object is always available'),
#        'quantity': fields.float(
#            'Computed Quantity',
#            help="Last computed quantity to send on Prestashop."
#        ),
#        'description_html': fields.html(
#            'Description',
#            translate=True,
#            help="Description html from prestashop",
#        ),
#        'description_short_html': fields.html(
#            'Short Description',
#            translate=True,
#        ),
#        'date_add': fields.datetime(
#            'Created At (on Presta)',
#            readonly=True
#        ),
#        'date_upd': fields.datetime(
#            'Updated At (on Presta)',
#            readonly=True
#        ),
#        'default_shop_id': fields.many2one(
#            'prestashop.shop',
#            'Default shop',
#            required=True
#        ),
#        'link_rewrite': fields.char(
#            'Friendly URL',
#            translate=True,
#            required=False,
#        ),
#        'reference': fields.char('Original reference'),
#    }
#
#    def recompute_prestashop_qty(self, cr, uid, ids, context=None):
#        if not hasattr(ids, '__iter__'):
#            ids = [ids]
#
#        for product in self.browse(cr, uid, ids, context=context):
#            new_qty = self._prestashop_qty(cr, uid, product, context=context)
#            self.write(
#                cr, uid, product.id,
#                {'quantity': new_qty},
#                context=context
#            )
#        return True
#
#    def _prestashop_qty(self, cr, uid, product, context=None):
#        if context is None:
#            context = {}
#        backend = product.backend_id
#        stock = backend.warehouse_id.lot_stock_id
#        stock_field = 'qty_available'
#        location_ctx = context.copy()
#        location_ctx['location'] = stock.id
#        product_stk = self.read(
#            cr, uid, product.id, [stock_field], context=location_ctx
#        )
#        return product_stk[stock_field]
#
#    _sql_constraints = [
#        ('prestashop_uniq', 'unique(backend_id, prestashop_id)',
#         "A product with the same ID on Prestashop already exists")
#    ]


class PConfiguration(orm.Model):
    _name = 'p.configuration'

    _columns = {
        'prestashop_config_ids': fields.one2many(
            'prestashop.configuration',
            'openerp_id',
            string='Prestashop configuration'
        ),
        'name': fields.char('Name', size=64),
        'value': fields.char('Value', size=64),
    }


class prestashop_configuration(orm.Model):
    _name = 'prestashop.configuration'
    _inherit = 'prestashop.binding'
    _inherits = {'p.configuration': 'openerp_id'}

    _columns = {
        'openerp_id': fields.many2one(
            'p.configuration',
            string='Openerp prestashop configuration',
            required=True,
            ondelete='cascade'
        ),
    }


class product_pricelist(orm.Model):
    _inherit = 'product.pricelist'

    _columns = {
        'prestashop_groups_bind_ids': fields.one2many(
            'prestashop.groups.pricelist',
            'openerp_id',
            string='Prestashop user groups'
        ),
    }


class prestashop_groups_pricelist(orm.Model):
    _name = 'prestashop.groups.pricelist'
    _inherit = 'prestashop.binding'
    _inherits = {'product.pricelist': 'openerp_id'}

    _columns = {
        'openerp_id': fields.many2one(
            'product.pricelist',
            string='Openerp Pricelist',
            required=True,
            ondelete='cascade'
        ),
    }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
