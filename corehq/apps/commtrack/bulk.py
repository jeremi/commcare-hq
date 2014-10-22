from corehq.apps.commtrack.models import *
from corehq.apps.custom_data_fields.models import CustomDataFieldsDefinition
from django.utils.translation import ugettext as _


def set_error(row, msg, override=False):
    """set an error message on a stock report to be imported"""
    if override or 'error' not in row:
        row['error'] = msg


def import_products(domain, importer):
    from .views import ProductFieldsView
    messages = []
    to_save = []
    product_count = 0
    seen_product_ids = set()

    product_data_model = CustomDataFieldsDefinition.get_or_create(
        domain,
        ProductFieldsView.field_type
    )

    for row in importer.worksheet:
        try:
            p = Product.from_excel(row, product_data_model)
        except Exception, e:
            messages.append(
                _(u'Failed to import product {name}: {ex}'.format(
                    name=row['name'] or '',
                    ex=e,
                ))
            )
            continue

        importer.add_progress()
        if not p:
            # skip if no product is found (or the row is blank)
            continue
        if not p.domain:
            # if product doesn't have domain, use from context
            p.domain = domain
        elif p.domain != domain:
            # don't let user import against another domains products
            messages.append(
                _(u"Product {product_name} belongs to another domain and was not updated").format(
                    product_name=p.name
                )
            )
            continue

        product_count += 1
        to_save.append(p)

        if len(to_save) > 500:
            Product.get_db().bulk_save(to_save)
            to_save = []

    if to_save:
        Product.get_db().bulk_save(to_save)

    if product_count:
        messages.insert(0, _('Successfullly updated {number_of_products} products with {errors} errors.').format(
            number_of_products=product_count, errors=len(messages))
        )
    return messages
