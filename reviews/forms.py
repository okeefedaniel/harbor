from django import forms

from .models import ReviewAssignment


class ReviewScoreForm(forms.Form):
    """Form for scoring a single rubric criterion.

    One instance of this form is rendered per criterion in the review
    interface.  The ``criterion_id`` hidden field ties the score back to
    the corresponding ``RubricCriterion``.
    """

    criterion_id = forms.UUIDField(widget=forms.HiddenInput)
    score = forms.IntegerField(min_value=0)
    comment = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
    )


class ReviewAssignmentForm(forms.ModelForm):
    """Form for assigning a reviewer to an application."""

    class Meta:
        model = ReviewAssignment
        fields = ['reviewer', 'rubric']

    def __init__(self, *args, application=None, **kwargs):
        super().__init__(*args, **kwargs)
        from core.models import User
        self.fields['reviewer'].queryset = User.objects.filter(
            role__in=['reviewer', 'program_officer', 'system_admin'],
            is_active=True,
        )
        if application:
            self.fields['rubric'].queryset = (
                application.grant_program.rubrics.filter(is_active=True)
            )
