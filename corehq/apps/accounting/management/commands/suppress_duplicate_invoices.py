import datetime
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db.models import Count
from corehq.apps.accounting.interface import get_subtotal_and_deduction
from corehq.apps.accounting.models import CreditAdjustment, Invoice, CreditLine, FeatureType
from corehq.util.dates import get_first_last_days
from dimagi.utils.dates import add_months


class Command(BaseCommand):
    help = 'Put credit back for duplicate invoices and suppress them'

    def add_arguments(self, parser):
        parser.add_argument('year', type=int, help='The year of the statement period.')
        parser.add_argument('month', type=int, help='The month of the statement period.')
        parser.add_argument('note', type=str,
                            help='A note to be added when crediting back the amount')
        parser.add_argument('--dry-run', action='store_true', default=False)

    def handle(self, *args, **kwargs):
        year = kwargs['year']
        month = kwargs['month']
        note = kwargs['note']
        dry_run = kwargs['dry_run']
        dry_run_tag = '[DRY_RUN] ' if dry_run else ''

        start_date, end_date = get_first_last_days(year, month)

        # Filter the Invoice objects based on the date_start
        invoices_of_given_date = Invoice.objects.filter(date_start__range=(start_date, end_date),
                                                        is_hidden_to_ops=False)

        # Extract the subscription ids that have duplicate invoices
        duplicate_subs_ids = invoices_of_given_date.values('subscription').annotate(
            count=Count('id')).filter(count__gt=1).values_list('subscription', flat=True)

        suppressed_count = 0
        for sub_id in duplicate_subs_ids:
            related_invoices = list(Invoice.objects.filter(is_hidden_to_ops=False,
                subscription_id=sub_id, date_start__range=(start_date, end_date)).order_by('-date_created'))
            first_created_invoice_id = related_invoices[0].id
            for invoice in related_invoices[:-1]:
                custom_note = f"{note}. Referenced to invoice {first_created_invoice_id}."
                self.revert_invoice_payment(invoice, custom_note, year, month, dry_run)
                # suppress invoice
                print(f'{dry_run_tag}Suppressing invoice {invoice.id} for domain '
                      f'{invoice.subscription.subscriber.domain} ', end='')
                if not dry_run:
                    invoice.is_hidden_to_ops = True
                    invoice.save()
                suppressed_count += 1
                print("✓")

        self.stdout.write(self.style.SUCCESS(f'{dry_run_tag}Successfully suppressed {suppressed_count} '
                                             f'duplicate invoices for Statement Period: {year}-{month}'))

    def revert_invoice_payment(self, invoice, note, year, month, dry_run=False):
        dry_run_tag = '[DRY_RUN] ' if dry_run else ''
        payment_by_other = invoice.subtotal
        reverted = False

        # Plan Credit
        if not invoice.subscription.auto_generate_credits:
            plan_subtotal, plan_deduction = get_subtotal_and_deduction(
                invoice.lineitem_set.get_products().all()
            )
            plan_credit = -plan_deduction
            if plan_credit:
                reverted = True
                print(f'{dry_run_tag}Adding plan credit: {plan_credit} to '
                    f'domain {invoice.subscription.subscriber.domain}')
                if not dry_run:
                    CreditLine.add_credit(amount=plan_credit, subscription=invoice.subscription,
                                        is_product=True, note=note)
        else:
            # Check if we generate duplicate product credit line
            current_year, current_month = add_months(year, month, 1)

            date_start = datetime.datetime(current_year, current_month, 1)
            date_end = date_start + timedelta(days=1) - timedelta(seconds=1)
            try:
                CreditLine.objects.get(account=invoice.subscription.account,
                                       subscription=invoice.subscription, is_product=True, is_active=True)
            except CreditLine.MultipleObjectsReturned:
                print(f"{dry_run_tag}Multiple plan credit lines found for subscription"
                      f" {invoice.subscription.plan_version.plan.name}.")
                duplicate_cl = CreditLine.objects.filter(account=invoice.subscription.account,
                                                         subscription=invoice.subscription, is_product=True,
                                                         is_active=True,
                                                         date_created__range=(date_start, date_end)).first()
                if not dry_run:
                    CreditAdjustment.objects.filter(credit_line=duplicate_cl).delete()
                    duplicate_cl.delete()
                    print("Duplicate Plan Credit Line deleted")

        # Feature Credit
        for feature in FeatureType.CHOICES:
            feature_subtotal, feature_deduction = get_subtotal_and_deduction(
                invoice.lineitem_set.get_feature_by_type(feature[0]).all()
            )
            feature_credit = -feature_deduction
            if feature_credit:
                reverted = True
                print(f"{dry_run_tag}Adding {feature[0]} credit: {feature_credit} to "
                      f"domain {invoice.subscription.subscriber.domain}")
                if not dry_run:
                    CreditLine.add_credit(amount=feature_credit, subscription=invoice.subscription,
                                        feature_type=feature[0], note=note)

        # Any Credit
        any_credit = -invoice.applied_credit
        if any_credit:
            reverted = True
            payment_by_other -= any_credit
            print(f"{dry_run_tag}Adding type Any credit: {any_credit} to "
                  f"domain {invoice.subscription.subscriber.domain}")
            if not dry_run:
                CreditLine.add_credit(amount=any_credit, subscription=invoice.subscription, note=note)

        # Calculate the amount paid not by credit
        payment_by_other -= invoice.balance
        if payment_by_other:
            reverted = True
            print(f"{dry_run_tag}Adding credit for other payments: {payment_by_other} "
                  f"to domain {invoice.subscription.subscriber.domain}")
            if not dry_run:
                CreditLine.add_credit(amount=payment_by_other, subscription=invoice.subscription, note=note)

        if reverted:
            print(f'{dry_run_tag}Successfully reverted payment for Invoice Id: {invoice.id}, '
              f'Domain: {invoice.subscription.subscriber.domain}')
