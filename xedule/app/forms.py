from django import forms

from .models import NostrCredentials
from .models import Note
from .models import TwitterCredentials


class TweetForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = ["content", "scheduled_time", "publish_to_x", "publish_to_nostr"]
        widgets = {
            "scheduled_time": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "publish_to_x": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "publish_to_nostr": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
        }


class ExcelUploadForm(forms.Form):
    excel_file = forms.FileField(
        label="Excel File",
        help_text="Upload an Excel file (.xlsx) with tweets to schedule",
    )


class TwitterCredentialsForm(forms.ModelForm):
    class Meta:
        model = TwitterCredentials
        fields = ["api_key", "api_secret_key", "access_token", "access_token_secret"]
        widgets = {
            "api_key": forms.TextInput(attrs={"placeholder": "Twitter API Key"}),
            "api_secret_key": forms.TextInput(
                attrs={"placeholder": "Twitter API Secret Key"}
            ),
            "access_token": forms.TextInput(
                attrs={"placeholder": "Twitter Access Token"}
            ),
            "access_token_secret": forms.TextInput(
                attrs={"placeholder": "Twitter Access Token Secret"}
            ),
        }


class NostrCredentialsForm(forms.ModelForm):
    class Meta:
        model = NostrCredentials
        fields = ["private_key", "public_key", "relay_urls"]
        widgets = {
            "private_key": forms.TextInput(
                attrs={"placeholder": "Nostr Private Key (nsec format)"}
            ),
            "public_key": forms.TextInput(
                attrs={"placeholder": "Nostr Public Key (npub format)"}
            ),
            "relay_urls": forms.Textarea(
                attrs={
                    "placeholder": "Leave empty if no other relays are known. The application uses by default the following relays: wss://nostr-pub.wellorder.net, wss://relay.primal.net, wss://relay.snort.social and wss://relay.damus.io",
                    "rows": 4,
                }
            ),
        }
        help_texts = {
            "private_key": "Your Nostr private key in nsec format",
            "public_key": "Your Nostr public key in npub format",
            "relay_urls": "Enter one relay URL per line, starting with wss://",
        }
