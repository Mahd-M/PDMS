from django import forms
from .models import Vehicle


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ["registration_number", "make", "model", "owner_name", "owner_contact", "status", "case"]
