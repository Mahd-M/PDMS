from django import forms
from .models import MissingPerson


class MissingPersonForm(forms.ModelForm):
    class Meta:
        model = MissingPerson
        fields = [
            "full_name", "last_seen_date", "last_seen_location",
            "reporting_relative_name", "reporting_relative_contact",
            "description", "photo", "status",
        ]
        widgets = {
            "last_seen_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }