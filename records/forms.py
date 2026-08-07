from django import forms
from .models import CourtDate, CriminalRecord


class CriminalRecordForm(forms.ModelForm):
    class Meta:
        model = CriminalRecord
        fields = [
            "full_name", "cnic", "aliases", "fingerprint_id",
            "photo", "status", "charges", "notes",
        ]
        widgets = {
            "charges": forms.Textarea(attrs={"rows": 4}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }


class CourtDateForm(forms.ModelForm):
    class Meta:
        model = CourtDate
        fields = ["date", "court_name", "outcome"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }