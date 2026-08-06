from django import forms


class LoginForm(forms.Form):
    username = forms.CharField(max_length=150, widget=forms.TextInput(attrs={"autofocus": True}))
    password = forms.CharField(widget=forms.PasswordInput)


class TOTPForm(forms.Form):
    code = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            "inputmode": "numeric",
            "pattern": "[0-9]{6}",
            "autocomplete": "one-time-code",
            "autofocus": True,
        }),
        label="6-digit authenticator code",
    )
