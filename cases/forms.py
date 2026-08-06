from django import forms
from .models import FIR, Case


class FIRForm(forms.ModelForm):
    class Meta:
        model = FIR
        fields = ["fir_number", "station", "sections_of_law", "complainant_name", "complainant_contact", "narrative", "is_sealed"]
        widgets = {
            "narrative": forms.Textarea(attrs={"rows": 6, "required": True}),
            "complainant_contact": forms.TextInput(attrs={"pattern": r"^[0-9+\-\s]{6,20}$"}),
        }


class CaseStatusForm(forms.ModelForm):
    class Meta:
        model = Case
        fields = ["status", "assigned_officer", "court_reference", "next_hearing_date"]
        widgets = {"next_hearing_date": forms.DateInput(attrs={"type": "date"})}
