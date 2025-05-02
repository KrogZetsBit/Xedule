import logging
import ssl
import time

import nostr.key as nk
import tweepy
from celery import shared_task
from django.utils import timezone
from nostr.event import Event
from nostr.relay_manager import RelayManager

from xedule.users.models import User

from .models import NostrCredentials
from .models import Note
from .models import TwitterCredentials

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BACKOFF_BASE = 2  # seconds


@shared_task
def publish_tweet():
    """Process pending tweets and publish them to Twitter and/or Nostr."""
    # Include notes that are pending or partially published
    pending_notes = Note.objects.filter(
        status__in=["pending", "published_x", "published_n"],
        scheduled_time__lte=timezone.now(),
    )

    if not pending_notes.exists():
        return "There are no tweets pending to be published."

    # Group notes by user
    grouped_notes = _group_tweets_by_user(pending_notes)

    # Process tweets by user
    published_count = _process_grouped_tweets(grouped_notes)

    return f"Se publicaron {published_count} tweets"


def _group_tweets_by_user(pending_notes):
    """Group tweets by user_id."""
    grouped_notes = {}
    for note in pending_notes:
        if note.user_id not in grouped_notes:
            grouped_notes[note.user_id] = []
        grouped_notes[note.user_id].append(note)
    return grouped_notes


def _process_grouped_tweets(grouped_notes):
    """Process tweets grouped by user."""
    published_count = 0

    for user_id, user_tweets in grouped_notes.items():
        try:
            user_published = _process_user_tweets(user_id, user_tweets)
            published_count += user_published
        except Exception:
            logger.exception("Error processing tweets for user %s", user_id)

    return published_count


def _process_user_tweets(user_id, user_notes):
    """Process tweets for a specific user."""
    try:
        user = User.objects.get(id=user_id)

        # Initialize clients as None to track which platforms are available
        twitter_client = None
        nostr_client_data = None

        # Try to get Twitter credentials
        try:
            twitter_credentials = TwitterCredentials.objects.get(user=user)
            twitter_client = _create_twitter_client(twitter_credentials)
            logger.info("Twitter client created successfully for user %s", user_id)
        except TwitterCredentials.DoesNotExist:
            logger.info(
                "User %s does not have Twitter credentials configured.", user_id
            )

        # Try to get Nostr credentials
        try:
            nostr_credentials = NostrCredentials.objects.get(user=user)
            if nostr_credentials.private_key:
                nostr_client_data = {
                    "private_key": nostr_credentials.private_key,
                    "public_key": nostr_credentials.public_key,
                    "relays": nostr_credentials.get_relay_list(),
                }
                logger.info(
                    "Nostr credentials loaded successfully for user %s", user_id
                )
            else:
                logger.warning(
                    "User %s has incomplete Nostr credentials (missing private key or relays)",
                    user_id,
                )
        except NostrCredentials.DoesNotExist:
            logger.info("User %s does not have Nostr credentials configured.", user_id)

        # Check if we have any platform to publish to
        if not twitter_client and not nostr_client_data:
            _mark_tweets_with_error(
                user_notes, "User does not have any platform credentials configured"
            )
            logger.error(
                "User %s has no platform credentials. No notes published.", user_id
            )
            return 0

        # Publish the tweets to available platforms
        return _publish_user_tweets_refactored(
            user_notes, twitter_client, nostr_client_data
        )

    except User.DoesNotExist:
        _mark_tweets_with_error(user_notes, "User does not exist")
        for note in user_notes:
            logger.exception(
                "User %s does not exist. Note %s not published.", user_id, note.id
            )
        return 0


def _create_twitter_client(credentials):
    """Create a Twitter API client using user credentials."""
    return tweepy.Client(
        consumer_key=credentials.api_key,
        consumer_secret=credentials.api_secret_key,
        access_token=credentials.access_token,
        access_token_secret=credentials.access_token_secret,
    )


def _publish_user_tweets_refactored(notes, twitter_client, nostr_client_data):
    """Publish notes for a user with the given clients."""
    published_count = 0

    for note in notes:
        # Actualizar la nota desde la base de datos para evitar usar datos en caché
        note.refresh_from_db()

        # Procesar la nota para su publicación
        result = _process_single_tweet(note, twitter_client, nostr_client_data)

        if result["all_completed"]:
            published_count += 1
            _log_successful_publish(note, result["twitter_id"], result["nostr_id"])

    return published_count


def _process_single_tweet(note, twitter_client, nostr_client_data):
    """Process a single note for publishing to available platforms."""
    # Check which platforms need publishing
    needs_twitter = note.publish_to_x and not note.tweet_id
    needs_nostr = note.publish_to_nostr and not note.nostr_id

    # Track results
    twitter_success = bool(note.tweet_id)  # Already published?
    nostr_success = bool(note.nostr_id)  # Already published?
    twitter_id = note.tweet_id
    nostr_id = note.nostr_id

    # If nothing to do, return early
    if not needs_twitter and not needs_nostr:
        return {"all_completed": True, "twitter_id": twitter_id, "nostr_id": nostr_id}

    # Try to publish to Twitter if needed
    if needs_twitter and twitter_client:
        tw_success, tw_id = _publish_note_to_twitter(note, twitter_client)
        if tw_success:
            # Update note immediately to prevent duplicate publishing
            note.tweet_id = tw_id
            note.save(update_fields=["tweet_id"])
            twitter_success = True
            twitter_id = tw_id
            logger.info(
                "Note %s successfully published to Twitter with ID %s", note.id, tw_id
            )
        else:
            logger.error("Failed to publish note %s to Twitter", note.id)
    elif needs_twitter and not twitter_client:
        _update_tweet_error(
            note, "User does not have Twitter API credentials configured"
        )
        logger.error(
            "Note %s not published to Twitter: No Twitter credentials", note.id
        )

    # Check again if we need to publish to Nostr (get fresh data)
    note.refresh_from_db()
    if note.publish_to_nostr and not note.nostr_id and nostr_client_data:
        ns_success, ns_id = _publish_note_to_nostr(note, nostr_client_data)
        if ns_success:
            # Update note immediately to prevent duplicate publishing
            note.nostr_id = ns_id
            note.save(update_fields=["nostr_id"])
            nostr_success = True
            nostr_id = ns_id
            logger.info(
                "Note %s successfully published to Nostr with ID %s", note.id, ns_id
            )
        else:
            logger.error("Failed to publish note %s to Nostr", note.id)
    elif needs_nostr and not nostr_client_data:
        _update_tweet_error(note, "User does not have Nostr credentials configured")
        logger.error("Note %s not published to Nostr: No Nostr credentials", note.id)

    # Update the overall status based on publishing results
    _update_note_final_status(
        note, needs_twitter, needs_nostr, twitter_success, nostr_success
    )

    # Determine if all required platforms were published to
    all_completed = (not needs_twitter or twitter_success) and (
        not needs_nostr or nostr_success
    )

    return {
        "all_completed": all_completed,
        "twitter_id": twitter_id,
        "nostr_id": nostr_id,
    }


def _update_note_final_status(
    note, needs_twitter, needs_nostr, twitter_success, nostr_success
):
    """Update the final status of the note based on publishing results."""
    # Refresh to get the most current state
    note.refresh_from_db()

    # Determine the appropriate status
    if needs_twitter and needs_nostr:
        if twitter_success and nostr_success:
            note.status = "published"
            note.published_at = timezone.now()
            note.last_error = ""
        elif twitter_success:
            note.status = "published_x"
            note.last_error = "Published to X/Twitter but failed to publish to Nostr"
        elif nostr_success:
            note.status = "published_n"
            note.last_error = "Published to Nostr but failed to publish to X/Twitter"
    elif (needs_twitter and twitter_success) or (needs_nostr and nostr_success):
        note.status = "published"
        note.published_at = timezone.now()
        note.last_error = ""

    # Save the updated note
    note.save()


def _log_successful_publish(note, twitter_id, nostr_id):
    """Log successful publishing of a note."""
    platforms = []
    if twitter_id:
        platforms.append("Twitter")
    if nostr_id:
        platforms.append("Nostr")
    platform_str = " and ".join(platforms)
    logger.info("Note %s successfully published to %s", note.id, platform_str)


def _publish_note_to_twitter(note, client):
    """Attempt to publish a note to Twitter with retries."""
    # Double-check if already published to Twitter
    if note.tweet_id:
        logger.info(
            "Note %s already published to Twitter (ID: %s), skipping",
            note.id,
            note.tweet_id,
        )
        return True, note.tweet_id

    retries = 0
    success = False
    tweet_id = ""

    while retries < MAX_RETRIES and not success:
        try:
            response = client.create_tweet(text=note.content)
            tweet_id = response.data["id"]
            success = True

        except tweepy.errors.TweepyException as e:
            _handle_api_error(note, str(e), retries, "Twitter")
            retries += 1

        except Exception as e:
            error_msg = f"Twitter error: {e!s}"
            _update_tweet_error(note, error_msg)
            logger.exception(
                "Unexpected error when posting note %s to Twitter", note.id
            )
            break

    if not success:
        logger.error(
            "Could not post note %s to Twitter after %s attempts.",
            note.id,
            MAX_RETRIES,
        )

    return success, tweet_id


def _publish_note_to_nostr(note, client_data):
    """Attempt to publish a note to Nostr with retries."""
    # Double-check if already published to Nostr
    if note.nostr_id:
        logger.info(
            "Note %s already published to Nostr (ID: %s), skipping",
            note.id,
            note.nostr_id,
        )
        return True, note.nostr_id

    consistent_timestamp = (
        int(note.scheduled_time.timestamp())
        if note.scheduled_time
        else int(note.created_at.timestamp())
    )

    retries = 0
    success = False
    note_id = ""

    while retries < MAX_RETRIES and not success:
        # Intentamos una sola vez la publicación - si falla por completo, pasamos a los retries
        try:
            # Crear un evento con timestamp consistente
            private_key = nk.PrivateKey.from_nsec(client_data["private_key"])

            # Crear un evento con ID consistente
            event = Event(
                content=note.content,
                public_key=private_key.public_key.hex(),
                kind=1,  # Regular note
                tags=[],  # No tags for simple notes
                created_at=consistent_timestamp,  # Timestamp consistente
            )

            # Firmar el evento para finalizar su ID
            private_key.sign_event(event)
            note_id = event.id

            # Guardar el ID inmediatamente para evitar duplicados en caso de reintento
            note.nostr_id = note_id
            note.save(update_fields=["nostr_id"])

            # Ahora publicamos a los relays, incluso si falla esto, ya tenemos el ID
            success = _publish_to_relays(client_data["relays"], event)

            if success:
                logger.info(
                    "Note %s successfully published to Nostr with ID %s",
                    note.id,
                    note_id,
                )

        except Exception:
            logger.exception("Error creating Nostr event for note %s", note.id)
            _update_tweet_error(note, "Nostr error")
            success = False
            retries += 1

    if not success:
        logger.error(
            "Could not post note %s to Twitter after %s attempts.",
            note.id,
            MAX_RETRIES,
        )

    return success, note_id


def _publish_to_relays(relays, event):
    """Publish an event to the given relays."""
    try:
        # Create a relay manager
        relay_manager = RelayManager()

        # Add all the relays
        for relay_url in relays:
            relay_manager.add_relay(relay_url)
            logger.debug("Added relay: %s", relay_url)

        relay_manager.add_relay("wss://nostr-pub.wellorder.net")
        relay_manager.add_relay("wss://relay.damus.io")
        relay_manager.add_relay("wss://relay.snort.social")
        relay_manager.add_relay("wss://relay.primal.net")

        # Connect to all relays
        relay_manager.open_connections(
            {
                "cert_reqs": ssl.CERT_NONE
            }  # NOTE: This disables ssl certificate verification
        )
        time.sleep(1.5)  # Give time for connections to establish

        # Publish the event to all relays
        relay_manager.publish_event(event)
        time.sleep(1)  # Give time for the event to be published

        # Close all relay connections
        relay_manager.close_connections()

    except Exception:
        logger.exception("Error publishing to Nostr relays")
        return False
    else:
        logger.info("Event %s published to all relays", event.id)
        return True


def _handle_api_error(note, error_message, retry_count, platform):
    """Handle API errors with exponential backoff."""
    _update_tweet_error(note, f"{platform} error: {error_message}")

    # Calculate backoff time with exponential increase
    backoff_time = BACKOFF_BASE * (2**retry_count)
    logger.warning(
        "Error publishing note %s to %s (attempt %s): %s. Retrying in %s seconds.",
        note.id,
        platform,
        retry_count + 1,
        error_message,
        backoff_time,
    )

    # Sleep for the calculated backoff time
    time.sleep(backoff_time)


def _update_tweet_error(note, error_message):
    """Update the note with the error message."""
    note.last_error = error_message
    note.save(update_fields=["last_error"])


def _mark_tweets_with_error(tweets, error_message):
    """Mark multiple tweets with the same error message."""
    for note in tweets:
        note.status = "error"
        note.last_error = error_message
        note.save(update_fields=["status", "last_error"])


@shared_task
def schedule_pending_tweets():
    """
    Periodic task to check and publish scheduled tweets
    """
    return publish_tweet.delay()
