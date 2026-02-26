"""CSV export utilities for list views."""
import csv

from django.http import HttpResponse


class CSVExportMixin:
    """Mixin that adds CSV export to any ListView.

    Add ``csv_filename`` and ``csv_columns`` to the view class.
    When ``?export=csv`` is in the query string, returns a CSV file
    instead of the normal HTML response.

    ``csv_columns`` should be a list of tuples:
        (header_name, field_or_callable)

    If *field_or_callable* is a string it is used as a dotted attribute
    path on the object (e.g. ``'grant_program.title'``).  A trailing
    callable (like ``get_status_display``) is invoked automatically.

    If *field_or_callable* is callable it receives the object and should
    return the cell value.
    """

    csv_filename = 'export.csv'
    csv_columns = []

    def get(self, request, *args, **kwargs):
        if request.GET.get('export') == 'csv':
            return self.export_csv()
        return super().get(request, *args, **kwargs)

    def export_csv(self):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{self.csv_filename}"'

        writer = csv.writer(response)
        # Header row
        writer.writerow([col[0] for col in self.csv_columns])

        # Data rows
        queryset = self.get_queryset()
        for obj in queryset:
            row = []
            for _, field in self.csv_columns:
                if callable(field):
                    row.append(field(obj))
                else:
                    # Support dotted attribute paths like 'grant_program.title'
                    value = obj
                    for attr in field.split('.'):
                        value = getattr(value, attr, '') if value else ''
                    # Handle callables (like get_status_display)
                    if callable(value):
                        value = value()
                    row.append(value)
            writer.writerow(row)

        return response
