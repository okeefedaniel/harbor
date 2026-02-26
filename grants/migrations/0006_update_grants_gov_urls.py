"""Data migration to update Grants.gov URLs from the old format
(www.grants.gov/search-results-detail/) to the new working format
(simpler.grants.gov/opportunity/).
"""

from django.db import migrations


def update_grants_gov_urls(apps, schema_editor):
    FederalOpportunity = apps.get_model('grants', 'FederalOpportunity')
    old_base = 'https://www.grants.gov/search-results-detail/'
    new_base = 'https://simpler.grants.gov/opportunity/'
    for opp in FederalOpportunity.objects.filter(grants_gov_url__startswith=old_base):
        opp.grants_gov_url = opp.grants_gov_url.replace(old_base, new_base)
        opp.save(update_fields=['grants_gov_url'])


def reverse_grants_gov_urls(apps, schema_editor):
    FederalOpportunity = apps.get_model('grants', 'FederalOpportunity')
    old_base = 'https://www.grants.gov/search-results-detail/'
    new_base = 'https://simpler.grants.gov/opportunity/'
    for opp in FederalOpportunity.objects.filter(grants_gov_url__startswith=new_base):
        opp.grants_gov_url = opp.grants_gov_url.replace(new_base, old_base)
        opp.save(update_fields=['grants_gov_url'])


class Migration(migrations.Migration):

    dependencies = [
        ('grants', '0005_savedprogram'),
    ]

    operations = [
        migrations.RunPython(update_grants_gov_urls, reverse_grants_gov_urls),
    ]
