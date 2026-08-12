from django import forms

from cases.models import Case
from cases.views import visible_firs_for
from .models import Vehicle


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ["registration_number", "make", "model", "owner_name", "owner_contact", "status", "case"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            # Same sealed-FIR row-level security as visible_vehicles_for --
            # the dropdown must not disclose a case's FIR number/status to
            # a user who couldn't see that FIR directly (see cases/views.py).
            self.fields["case"].queryset = Case.objects.filter(fir__in=visible_firs_for(user))
