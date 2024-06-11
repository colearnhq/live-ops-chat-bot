import os
import re
import json
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
import logging
from datetime import datetime
from slack_sdk.errors import SlackApiError
from database import SheetManager
import pytz

load_dotenv(".env")

creds_dict = {
    "type": os.getenv("GOOGLE_CREDENTIALS_TYPE"),
    "project_id": os.getenv("GOOGLE_PROJECT_ID"),
    "private_key_id": os.getenv("GOOGLE_PRIVATE_KEY_ID"),
    "private_key": os.getenv("GOOGLE_PRIVATE_KEY").replace("\\n", "\n"),
    "client_email": os.getenv("GOOGLE_CLIENT_EMAIL"),
    "client_id": os.getenv("GOOGLE_CLIENT_ID"),
    "auth_uri": os.getenv("GOOGLE_AUTH_URI"),
    "token_uri": os.getenv("GOOGLE_TOKEN_URI"),
    "auth_provider_x509_cert_url": os.getenv("GOOGLE_AUTH_PROVIDER_CERT_URL"),
    "client_x509_cert_url": os.getenv("GOOGLE_CLIENT_CERT_URL"),
    "universe_domain": os.getenv("GOOGLE_UNIVERSE_DOMAIN"),
}

app = App(token=os.getenv("SLACK_BOT_TOKEN"))
sheet_manager = SheetManager(creds_dict, "1dPXiGBN2dDyyQ9TnO6Hi8cQtmbkFBU4O7sI5ztbXT90")

reflected_cn = "C05Q52ZTQ3X"

greetings_response = {
    "morning": "Good Morning",
    "hello": "Hello",
    "hi": "Hi",
    "hai": "Hai",
    "hej": "Hej",
    "assalamu'alaikum": "Wa'alaikumussalam",
    "assalamualaikum": "Wa'alaikumussalam",
    "hey": "Hey",
    "afternoon": "Good Afternoon",
    "evening": "Good Evening",
    "shalom": "Shalom",
    "pagi": "Selamat Pagi",
    "siang": "Selamat Siang",
    "malam": "Selamat Malam",
}

thank_you_response = {
    "makasih": "Iyaa, sama sama :pray:",
    "thank you": "yap, my pleasure :pray:",
    "thx": "yuhu, you're welcome",
    "maaci": "hihi iaa, maaciw juga :wink:",
    "suwun": "enggeh, sami sami :pray:",
    "nuhun": "muhun, sami sami :pray:",
}

greeting_pattern = re.compile(
    r".*(morning|hello|hi|assalamu'alaikum|evening|hey|assalamualaikum|afternoon|shalom|hai|hej|pagi|siang|malam).*",
    re.IGNORECASE,
)

thank_you_pattern = re.compile(
    r".*(makasih|thank|thx|maaci|suwun|nuhun).*", re.IGNORECASE
)


def convert_utc_to_jakarta(time):
    utc_time = time.replace(tzinfo=pytz.utc)
    jakarta_tz = pytz.timezone("Asia/Jakarta")
    changed_timezone = utc_time.astimezone(jakarta_tz)
    return changed_timezone.strftime("%Y-%m-%d %H:%M:%S")


class TicketManager:
    def __init__(self):
        self.reflected_timestamps = {}

    def store_reflected_ts(self, thread_ts, reflected_ts):
        self.reflected_timestamps[thread_ts] = reflected_ts

    def get_reflected_ts(self, thread_ts):
        return self.reflected_timestamps.get(thread_ts)

    def clear_reflected_ts(self, thread_ts):
        if thread_ts in self.reflected_timestamps:
            del self.reflected_timestamps[thread_ts]


ticket_manager = TicketManager()


@app.event("message")
def handle_message_events(body, say, client):
    event = body.get("event", {})
    user_id = event.get("user")
    chat_timestamp = event["ts"]
    timestamp_utc = datetime.utcnow()

    try:
        user_info = client.users_info(user=user_id)
        text = event.get("text", "").strip().lower()
        email = user_info["user"].get("name", "unknown") + "@colearn.id"
        full_name = user_info["user"]["profile"].get("real_name", "unknown")
        phone_number = user_info["user"]["profile"].get("phone", "unknown")
        match_greeting = greeting_pattern.search(text)
        match_thank_you = thank_you_pattern.search(text)

        if match_greeting:
            greeting = match_greeting.group(1)
            if greeting in greetings_response:
                response = greetings_response[greeting]
                say(
                    f"{response} <@{event['user']}>, Ops are ready to help :confused_dog:"
                )
                say(
                    f"Please type your issue with the following pattern: `/hiops [write your issue/inquiry]`"
                )
        elif match_thank_you:
            thank_you = match_thank_you.group(1)
            if thank_you in thank_you_response:
                response = thank_you_response[thank_you]
                say(response)
        else:
            say(f"Hi <@{event['user']}>, Ops are ready to help :confused_dog:")
            say(
                f"Please type your issue with this following pattern: `/hiops [write your issue/inquiry]`"
            )
        sheet_manager.log_ticket(
            chat_timestamp,
            timestamp_utc,
            user_id,
            full_name,
            email,
            phone_number,
            text,
        )
    except Exception as e:
        logging.error(f"Error handling message: {str(e)}")


@app.command("/hiops")
def handle_hiops_command(ack, body, client, say):
    ack()
    user_input = body.get("text", "No message provided.")
    user_id = body["user_id"]
    channel_id = "C0719R3NQ91"
    timestamp_utc = datetime.utcnow()
    timestamp_jakarta = convert_utc_to_jakarta(timestamp_utc)
    categories = [
        "Ajar",
        "Cuti",
        "Data related",
        "Observasi",
        "Piket",
        "Polling",
        "Recording Video",
        "Zoom",
        "Others",
    ]

    try:
        init_result = client.chat_postMessage(
            channel=channel_id, text="Initializing ticket..."
        )

        ticket = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Your ticket number: *live-ops.{init_result['ts']}*",
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Your Name:*\n{body['user_name']}",
                    },
                    {"type": "mrkdwn", "text": f"*Reported at:*\n{timestamp_jakarta}"},
                    {
                        "type": "mrkdwn",
                        "text": f"*Problem:*\n`{user_input}`",
                    },
                ],
            },
        ]

        response_for_user = client.chat_postMessage(channel=user_id, blocks=ticket)
        ticket_key_for_user = (
            f"{user_id},{response_for_user['ts']},{user_input},{timestamp_jakarta}"
        )
        members_result = client.conversations_members(channel=channel_id)
        members = members_result["members"] if members_result["ok"] else []
        user_options = [
            {
                "text": {"type": "plain_text", "text": f"<@{member}>"},
                "value": f"{member},{user_id},{response_for_user['ts']},{user_input},{timestamp_jakarta}",
            }
            for member in members
        ]
        category_options = [
            {
                "text": {"type": "plain_text", "text": category},
                "value": f"{category},{ticket_key_for_user}",
            }
            for category in categories
        ]

        if init_result["ok"]:
            ts = init_result["ts"]
            blocks = [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "Hi @channel :wave:"},
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"We just received a ticket from <@{user_id}> at `{timestamp_jakarta}`",
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Ticket Number:*\nlive-ops.{ts}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Problem:*\n`{user_input}`",
                        },
                    ],
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Please pick a person:",
                    },
                    "accessory": {
                        "type": "static_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select a person...",
                            "emoji": True,
                        },
                        "options": user_options,
                        "action_id": "user_select_action",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Please select the category of the issue:",
                    },
                    "accessory": {
                        "type": "static_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select category...",
                            "emoji": True,
                        },
                        "options": category_options,
                        "action_id": "category_select_action",
                    },
                },
                {"type": "divider"},
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "emoji": True,
                                "text": "Resolve",
                            },
                            "style": "primary",
                            "value": ticket_key_for_user,
                            "action_id": "resolve_button",
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "emoji": True,
                                "text": "Reject",
                            },
                            "style": "danger",
                            "value": ticket_key_for_user,
                            "action_id": "reject_button",
                        },
                    ],
                },
            ]

        private_metadata = {
            "category_options": category_options,
            "ticket_key_for_user": ticket_key_for_user,
        }

        result = client.chat_update(
            channel=channel_id,
            ts=ts,
            blocks=blocks,
            metadata={"private_metadata": json.dumps(private_metadata)},
        )
        sheet_manager.init_ticket_row(
            f"live-ops.{result['ts']}",
            user_id,
            body["user_name"],
            user_input,
            timestamp_utc,
        )
        if not result["ok"]:
            say("Failed to post message")
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")


@app.action("user_select_action")
def handle_user_selection(ack, body, client):
    ack()
    selected_user_data = body["actions"][0]["selected_option"]["value"].split(",")
    selected_user = selected_user_data[0]
    user_info = client.users_info(user=selected_user)
    selected_user_name = user_info["user"]["real_name"]
    user_who_requested = selected_user_data[1]
    response_ts = selected_user_data[2]
    user_input = selected_user_data[3]
    reported_at = selected_user_data[4]
    channel_id = body["channel"]["id"]
    thread_ts = body["container"]["message_ts"]
    timestamp_utc = datetime.utcnow()
    timestamp_jakarta = convert_utc_to_jakarta(timestamp_utc)
    private_metadata = json.loads(body["message"]["metadata"]["private_metadata"])
    category_options = private_metadata["category_options"]
    ticket_key_for_user = private_metadata["ticket_key_for_user"]
    response = client.chat_postMessage(
        channel=channel_id,
        thread_ts=thread_ts,
        text=f"<@{selected_user}> is going to resolve this issue, starting from `{timestamp_jakarta}`.",
    )
    sheet_manager.update_ticket(
        f"live-ops.{thread_ts}",
        {"handled_by": selected_user_name, "handled_at": timestamp_utc},
    )
    if response["ok"]:

        main_blocks = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "Hi @channel :wave:"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"We just received a ticket from <@{user_who_requested}> at `{reported_at}`",
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Ticket Number:*\nlive-ops.{thread_ts}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Problem:*\n`{user_input}`",
                    },
                    {"type": "mrkdwn", "text": f"*Picked up by:*\n<@{selected_user}>"},
                ],
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Please select the category of the issue:",
                },
                "accessory": {
                    "type": "static_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select category...",
                        "emoji": True,
                    },
                    "options": category_options,
                    "action_id": "category_select_action",
                },
            },
            {"type": "divider"},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "emoji": True,
                            "text": "Resolve",
                        },
                        "style": "primary",
                        "value": ticket_key_for_user,
                        "action_id": "resolve_button",
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "emoji": True,
                            "text": "Reject",
                        },
                        "style": "danger",
                        "value": ticket_key_for_user,
                        "action_id": "reject_button",
                    },
                ],
            },
        ]

        reflected_msg = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "Hi @channel :wave:"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"We just received an issue from <@{user_who_requested}> at `{reported_at}`",
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Ticket Number:*\nlive-ops.{thread_ts}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Problem:*\n`{user_input}`",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Current Progress:*\n:pray: On checking",
                    },
                ],
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Please pay attention, if this issue related to you :point_up_2:",
                },
            },
        ]

        client.chat_postMessage(
            channel=user_who_requested,
            thread_ts=response_ts,
            text=f"<@{user_who_requested}> your issue will be handled by <@{selected_user}>. We will check and text you asap. Please wait ya.",
        )
        reflected_post = client.chat_postMessage(
            channel=reflected_cn, blocks=reflected_msg
        )

        if reflected_post["ok"]:
            reflected_ts = reflected_post["ts"]
            ticket_manager.store_reflected_ts(thread_ts, reflected_ts)
            client.chat_postMessage(
                channel=reflected_cn,
                thread_ts=reflected_ts,
                text=f"This issue will be handled by <@{selected_user}>, starting from `{timestamp_jakarta}`",
            )
        else:
            logging.error(
                f"Failed to post reflected message: {reflected_post['error']}"
            )

    else:
        logging.error(f"Failed to post message: {response['error']}")

    if not response["ok"]:
        logging.error(f"Failed to post message: {response['error']}")


@app.action("category_select_action")
def handle_category_selection(ack, body, client):
    ack()
    selected_category = body["actions"][0]["selected_option"]["value"].split(",")
    selected_category_name = selected_category[0]
    thread_ts = body["container"]["message_ts"]

    if selected_category_name.lower() == "others":
        trigger_id = body["trigger_id"]
        modal_view = {
            "type": "modal",
            "callback_id": "custom_category_modal",
            "title": {"type": "plain_text", "text": "Custom Category"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "custom_category_block",
                    "label": {
                        "type": "plain_text",
                        "text": "Please specify your category",
                    },
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "custom_category_input",
                    },
                }
            ],
            "private_metadata": f"{thread_ts}",
            "submit": {"type": "plain_text", "text": "Submit"},
        }
        client.views_open(trigger_id=trigger_id, view=modal_view)
    else:
        sheet_manager.update_ticket(
            f"live-ops.{thread_ts}",
            {"category_issue": selected_category_name},
        )


@app.view("custom_category_modal")
def handle_custom_category_modal_submission(ack, body, client, view, logger):
    ack()
    user_id = body["user"]["id"]
    custom_category = view["state"]["values"]["custom_category_block"][
        "custom_category_input"
    ]["value"]
    thread_ts = view["private_metadata"]

    # Update the ticket with the custom category
    try:
        sheet_manager.update_ticket(
            f"live-ops.{thread_ts}",
            {"category_issue": custom_category},
        )
    except Exception as e:
        logger.error(f"Failed to update ticket with custom category: {str(e)}")
        client.chat_postMessage(
            channel=user_id,
            text="Failed to record the custom category. Please try again.",
        )


@app.action("resolve_button")
def handle_resolve_button(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    user_info = client.users_info(user=user_id)
    user_name = user_info["user"]["real_name"]
    channel_id = body["channel"]["id"]
    thread_ts = body["container"]["message_ts"]
    reflected_ts = ticket_manager.get_reflected_ts(thread_ts)
    elements = body["message"]["blocks"][7]["elements"]
    resolve_button_value = elements[0]["value"].split(",")
    user_who_requested_ticket_id = resolve_button_value[0]
    user_message_ts = resolve_button_value[1]
    user_input = resolve_button_value[2]
    ticket_reported_at = resolve_button_value[3]
    timestamp_utc = datetime.utcnow()
    timestamp_jakarta = convert_utc_to_jakarta(timestamp_utc)
    response = client.chat_postMessage(
        channel=channel_id,
        thread_ts=thread_ts,
        text=f"<@{user_id}> has resolved the issue at `{timestamp_jakarta}`.",
    )
    sheet_manager.update_ticket(
        f"live-ops.{thread_ts}",
        {"resolved_by": user_name, "resolved_at": timestamp_utc},
    )

    if response["ok"]:
        client.chat_update(
            channel=channel_id,
            ts=thread_ts,
            text=None,
            blocks=[
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "Hi @channel :wave:"},
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"We just received a message from <@{user_who_requested_ticket_id}> at `{ticket_reported_at}`",
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Ticket Number:*\nlive.ops.{thread_ts}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Problem:*\n`{user_input}`",
                        },
                    ],
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f":white_check_mark: <@{user_id}> resolved this issue",
                    },
                },
            ],
        )

        reflected_msg = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "Hi @channel :wave:"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"We just received an issue from <@{user_who_requested_ticket_id}> at `{ticket_reported_at}`",
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Ticket Number:*\nlive-ops.{thread_ts}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Problem:*\n`{user_input}`",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Current Progress:*\n:white_check_mark: Resolved",
                    },
                ],
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Please pay attention, if this issue related to you :point_up_2:",
                },
            },
        ]

        client.chat_update(channel=reflected_cn, ts=reflected_ts, blocks=reflected_msg)

        client.chat_postMessage(
            channel=reflected_cn,
            thread_ts=reflected_ts,
            text=f"This issue has been resolved at `{timestamp_jakarta}` by <@{user_id}>",
        )

        client.chat_postMessage(
            channel=user_who_requested_ticket_id,
            thread_ts=user_message_ts,
            text=f"<@{user_who_requested_ticket_id}> your issue has been resolved at `{timestamp_jakarta}`. Thank you :blob-bear-dance:",
        )

    else:
        logging.error(f"Failed to post message: {response['error']}")


@app.action("reject_button")
def handle_reject_button(ack, body, client):
    ack()
    trigger_id = body["trigger_id"]
    message_ts = body["container"]["message_ts"]
    channel_id = body["channel"]["id"]
    user_info = client.users_info(user=body["user"]["id"])
    user_name = user_info["user"]["real_name"]
    elements = body["message"]["blocks"][7]["elements"]
    reject_button_value = elements[0]["value"]
    timestamp_utc = datetime.utcnow()
    sheet_manager.update_ticket(
        f"live-ops.{message_ts}",
        {"rejected_by": user_name, "rejected_at": timestamp_utc},
    )
    modal = {
        "type": "modal",
        "callback_id": "modal_reject",
        "title": {"type": "plain_text", "text": "Reject Issue"},
        "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "reject_reason",
                "label": {"type": "plain_text", "text": "Reason for Rejection"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "reason_input",
                    "multiline": True,
                },
            }
        ],
        "private_metadata": f"{channel_id},{message_ts},{reject_button_value} ",
    }

    try:
        client.views_open(trigger_id=trigger_id, view=modal)
    except SlackApiError as e:
        logging.error(f"Error opening modal: {str(e)}")


@app.view("modal_reject")
def handle_modal_submission(ack, body, client, view, logger):
    ack()
    try:
        user_id = body["user"]["id"]
        private_metadata = view["private_metadata"].split(",")
        channel_id = private_metadata[0]
        message_ts = private_metadata[1]
        user_requested_id = private_metadata[2]
        user_message_ts = private_metadata[3]
        user_input = private_metadata[4]
        ticket_reported_at = private_metadata[5]
        reason = view["state"]["values"]["reject_reason"]["reason_input"]["value"]
        timestamp_utc = datetime.utcnow()
        timestamp_jakarta = convert_utc_to_jakarta(timestamp_utc)

        response = client.chat_postMessage(
            channel=channel_id,
            thread_ts=message_ts,
            text=f"<@{user_id}> has rejected the issue at `{timestamp_jakarta}` due to: `{reason}`.",
        )
        if response["ok"]:
            client.chat_update(
                channel=channel_id,
                ts=message_ts,
                text=None,
                blocks=[
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": "Hi @channel :wave:"},
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"We just received a message from <@{user_requested_id}> at `{ticket_reported_at}`",
                        },
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Ticket Number:*\nlive.ops.{message_ts}",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Problem:*\n`{user_input}`",
                            },
                        ],
                    },
                    {"type": "divider"},
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f":x: This issue was rejected by <@{user_id}>. Please ignore this",
                        },
                    },
                ],
            )

            client.chat_postMessage(
                channel=user_requested_id,
                thread_ts=user_message_ts,
                text=f"We are sorry :smiling_face_with_tear: your issue was rejected due to `{reason}`. Let's put another question.",
            )

        else:
            logger.error("No value information available for this channel.")
    except Exception as e:
        logger.error(f"Error handling modal submission: {str(e)}")


# Start your app
if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
