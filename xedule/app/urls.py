# tweets/urls.py
from django.urls import path

from . import views

urlpatterns = [
    path("", views.TweetListView.as_view(), name="tweet_list"),
    path("note/<int:pk>/", views.TweetDetailView.as_view(), name="tweet_detail"),
    path("note/new/", views.TweetCreateView.as_view(), name="tweet_create"),
    path("note/<int:pk>/edit/", views.TweetUpdateView.as_view(), name="tweet_update"),
    path(
        "note/<int:pk>/delete/",
        views.TweetDeleteView.as_view(),
        name="tweet_delete",
    ),
    # En app/urls.py, añade esta nueva URL:
    path(
        "tweets/bulk-delete/",
        views.BulkDeleteTweetsView.as_view(),
        name="bulk_delete_tweets",
    ),
    path(
        "note/bulk-upload/",
        views.TweetBulkUploadView.as_view(),
        name="tweet_bulk_upload",
    ),
    path(
        "note/download-template/",
        views.DownloadTemplateView.as_view(),
        name="download_template",
    ),
    path(
        "credentials/twitter/",
        views.TwitterCredentialsUpdateView.as_view(),
        name="twitter_credentials",
    ),
    path(
        "credentials/nostr/",
        views.NostrCredentialsUpdateView.as_view(),
        name="nostr_credentials",
    ),
]
