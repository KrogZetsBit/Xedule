# tweets/views.py
from io import BytesIO

import pandas as pd
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView
from django.views.generic import DeleteView
from django.views.generic import DetailView
from django.views.generic import ListView
from django.views.generic import UpdateView
from django.views.generic.edit import FormView

from .forms import ExcelUploadForm
from .forms import NostrCredentialsForm
from .forms import TweetForm
from .forms import TwitterCredentialsForm
from .models import NostrCredentials
from .models import Note
from .models import TwitterCredentials
from .utils import process_excel_file

EXCEPTION = "You do not have permission to modify/delete this note"
LENGTH_ERROR_MESSAGE = 10


class UserOwnsTweetMixin:
    def dispatch(self, request, *args, **kwargs):
        note = self.get_object()
        if note.user != request.user:
            raise PermissionDenied(EXCEPTION)
        return super().dispatch(request, *args, **kwargs)


class TweetListView(LoginRequiredMixin, ListView):
    model = Note
    template_name = "app/tweet_list.html"
    context_object_name = "tweets"
    paginate_by = 20

    def get_queryset(self):
        return Note.objects.filter(user=self.request.user).order_by("created_at")


class TweetDetailView(LoginRequiredMixin, DetailView):
    model = Note
    template_name = "app/tweet_detail.html"
    context_object_name = "note"


class TweetCreateView(LoginRequiredMixin, CreateView):
    model = Note
    form_class = TweetForm
    template_name = "app/tweet_form.html"
    success_url = reverse_lazy("tweet_list")

    def form_valid(self, form):
        form.instance.user = self.request.user  # Asigna el usuario actual al note
        return super().form_valid(form)


class TweetUpdateView(LoginRequiredMixin, UserOwnsTweetMixin, UpdateView):
    model = Note
    form_class = TweetForm
    template_name = "app/tweet_form.html"
    success_url = reverse_lazy("tweet_list")

    def get_queryset(self):
        # Solo permite editar tweets del usuario actual
        return super().get_queryset().filter(user=self.request.user)


class TweetDeleteView(LoginRequiredMixin, UserOwnsTweetMixin, DeleteView):
    model = Note
    template_name = "app/tweet_confirm_delete.html"
    success_url = reverse_lazy("tweet_list")

    def get_queryset(self):
        # Solo permite borrar tweets del usuario actual
        return super().get_queryset().filter(user=self.request.user)


class BulkDeleteTweetsView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        tweet_ids = request.POST.getlist("tweet_ids")
        if tweet_ids:
            tweets = Note.objects.filter(id__in=tweet_ids, user=request.user)
            count = tweets.count()
            tweets.delete()
            messages.success(request, f"{count} note(s) eliminados correctamente.")
        else:
            messages.warning(request, "No se seleccionaron tweets para eliminar.")
        return redirect("tweet_list")


class TweetBulkUploadView(LoginRequiredMixin, FormView):
    form_class = ExcelUploadForm
    template_name = "app/tweet_bulk_upload.html"
    success_url = reverse_lazy("tweet_list")

    def form_valid(self, form):
        excel_file = self.request.FILES["excel_file"]

        # Check file extension
        if not excel_file.name.endswith(".xlsx"):
            messages.error(self.request, "Please upload an Excel file (.xlsx)")
            return self.form_invalid(form)

        # Process the Excel file
        result = process_excel_file(excel_file, self.request.user)

        if result["success"]:
            messages.success(
                self.request,
                f"Successfully created {result['tweets_created']} tweets. "
                f"Failed: {result['tweets_failed']}.",
            )

            # If there are error messages, show them
            if result["error_messages"]:
                error_list = "<br>".join(
                    result["error_messages"][:LENGTH_ERROR_MESSAGE]
                )
                if len(result["error_messages"]) > LENGTH_ERROR_MESSAGE:
                    error_list += "<br>...and more."
                messages.warning(
                    self.request, f"Errors: {error_list}", extra_tags="safe"
                )
        else:
            messages.error(self.request, f"Error: {result['message']}")
            return self.form_invalid(form)

        return super().form_valid(form)


class DownloadTemplateView(View):
    def get(self, request, *args, **kwargs):
        # Create a sample dataframe with the expected structure
        notes_template_df = pd.DataFrame(
            {
                "content": [
                    "This is a sample note content. Replace with your actual note.",
                    "Another example note. You can add as many rows as needed.",
                ],
                "scheduled_time": [
                    pd.Timestamp("2025-05-01 10:00:00"),
                    pd.Timestamp("2025-05-02 15:30:00"),
                ],
                "publish_to_x": [
                    "yes",
                    "no",
                ],
                "publish_to_nostr": [
                    "yes",
                    "no",
                ],
            }
        )

        # Create a BytesIO object to save the Excel file
        buffer = BytesIO()

        # Create the Excel writer using the BytesIO object as the file
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            notes_template_df.to_excel(writer, index=False, sheet_name="Notes")

            # Auto-adjust columns' width
            worksheet = writer.sheets["Notes"]
            for i, col in enumerate(notes_template_df.columns):
                max_length = max(
                    notes_template_df[col].astype(str).map(len).max(), len(col)
                )
                # Adding a little extra space
                worksheet.column_dimensions[chr(65 + i)].width = max_length + 2

        # Set up the response
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = (
            "attachment; filename=notes_upload_template.xlsx"
        )

        return response


class TwitterCredentialsUpdateView(LoginRequiredMixin, UpdateView):
    model = TwitterCredentials
    form_class = TwitterCredentialsForm
    template_name = "app/twitter_credentials_form.html"

    def get_object(self, queryset=None):
        obj, _ = TwitterCredentials.objects.get_or_create(user=self.request.user)
        return obj

    def get_success_url(self):
        messages.success(self.request, "Twitter credentials updated successfully.")
        return reverse("users:detail", kwargs={"username": self.request.user.username})


class NostrCredentialsUpdateView(LoginRequiredMixin, UpdateView):
    model = NostrCredentials
    form_class = NostrCredentialsForm
    template_name = "app/nostr_credentials_form.html"

    def get_object(self, queryset=None):
        obj, _ = NostrCredentials.objects.get_or_create(user=self.request.user)
        return obj

    def get_success_url(self):
        messages.success(self.request, "Nostr credentials updated successfully.")
        return reverse("users:detail", kwargs={"username": self.request.user.username})
