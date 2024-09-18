import os
import re
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
import logging
import threading
from datetime import datetime, timedelta
from slack_sdk.errors import SlackApiError
from database import SheetManager
import pytz

load_dotenv(".env.dev")

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
        self.user_inputs = {}
        self.ticket_status = {}

    def store_reflected_ts(self, thread_ts, reflected_ts):
        self.reflected_timestamps[thread_ts] = reflected_ts

    def get_reflected_ts(self, thread_ts):
        return self.reflected_timestamps.get(thread_ts)

    def clear_reflected_ts(self, thread_ts):
        if thread_ts in self.reflected_timestamps:
            del self.reflected_timestamps[thread_ts]

    def store_user_input(self, thread_ts, user_input):
        self.user_inputs[thread_ts] = user_input

    def get_user_input(self, thread_ts):
        return self.user_inputs.get(thread_ts)

    def clear_user_input(self, thread_ts):
        if thread_ts in self.user_inputs:
            del self.user_inputs[thread_ts]

    def update_ticket_status(self, thread_ts, status):
        self.ticket_status[thread_ts] = status

    def get_ticket_status(self, thread_ts):
        return self.ticket_status.get(
            thread_ts, "unassigned"
        )  # Default to 'unassigned'

    def clear_ticket_status(self, thread_ts):
        if thread_ts in self.ticket_status:
            del self.ticket_status[thread_ts]


ticket_manager = TicketManager()


@app.event("message")
def intial_msg(body, say, client):
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
                say(f"{response} <@{event['user']}>, Pepe is ready to help :frog:")
                say(
                    f"Please type your issue with the following pattern: `/hiops [write your issue/inquiry]`"
                )
        elif match_thank_you:
            thank_you = match_thank_you.group(1)
            if thank_you in thank_you_response:
                response = thank_you_response[thank_you]
                say(response)
        else:
            say(f"Hi <@{event['user']}>, Pepe is ready to help :frog:")
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


def truncate_value(value, max_length=37):
    return (
        value
        if len(value) <= max_length
        else value[:max_length] + "...(continued in thread)"
    )


@app.command("/opsdev")
def dev_ops(ack, body, client, say):
    ack()
    user_input = body.get("text", "No message provided.")
    user_id = body["user_id"]
    reporter_name = body["user_name"]
    channel_id = "C0719R3NQ91"
    timestamp_utc = datetime.utcnow()
    timestamp_jakarta = convert_utc_to_jakarta(timestamp_utc)

    try:
        init_result = client.chat_postMessage(
            channel=channel_id, text="Initializing ticket..."
        )

        ticket_manager.store_user_input(init_result["ts"], user_input)

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
                        "text": f"*Your Name:*\n{reporter_name}",
                    },
                    {"type": "mrkdwn", "text": f"*Reported at:*\n{timestamp_jakarta}"},
                    {
                        "type": "mrkdwn",
                        "text": f"*Problem:*\n`{truncate_value(user_input)}`",
                    },
                ],
            },
        ]

        response_for_user = client.chat_postMessage(channel=user_id, blocks=ticket)
        ticket_key_for_user = f"{user_id}@@{response_for_user['ts']}@@{truncate_value(user_input)}@@{timestamp_jakarta}"

        members_result = client.conversations_members(channel=channel_id)
        if members_result["ok"]:
            members = members_result["members"]
        else:
            members = []

        group_mentions = ["S05RYHJ41C6", "S02R59UL0RH"]
        members.extend(group_mentions)
        members.sort()

        user_options = [
            {
                "text": {
                    "type": "plain_text",
                    "text": (
                        f"<@{member}>"
                        if not member.startswith("S")
                        else f"<!subteam^{member}>"
                    ),
                },
                "value": f"{member}@@{user_id}@@{response_for_user['ts']}@@{truncate_value(user_input)}@@{timestamp_jakarta}",
            }
            for member in members
        ]

        if response_for_user["ok"]:
            ts = response_for_user["ts"]
            client.chat_postMessage(
                channel=user_id, thread_ts=ts, text=f"ini thread_ts buat user {ts}"
            )
            if len(user_input) > 37:
                client.chat_postMessage(
                    channel=user_id,
                    thread_ts=ts,
                    text=f"For the problem details: `{user_input}`",
                )

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
                            "text": f"*Problem:*\n`{truncate_value(user_input)}`",
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

        result = client.chat_update(channel=channel_id, ts=ts, blocks=blocks)
        sheet_manager.init_ticket_row(
            f"live-ops.{result['ts']}",
            user_id,
            body["user_name"],
            user_input,
            timestamp_utc,
        )
        if result["ok"]:
            # we post the ts, only for development purpose
            client.chat_postMessage(
                channel=channel_id,
                thread_ts=ts,
                text=f"thread ts: {result['ts']}",
            )
            if len(user_input) > 37:
                client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=ts,
                    text=f"For the problem details: `{user_input}`",
                )
        else:
            say("Failed to post message")

        reminder_time = timedelta(minutes=3)
        schedule_reminder(client, channel_id, ts, reminder_time, result["ts"])

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")


def schedule_reminder(client, channel_id, thread_ts, reminder_time, ticket_ts):
    def remind():
        if not is_ticket_assigned(ticket_ts):
            client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text="Reminder: This ticket has not been picked up yet. Please respond within 5 minutes.",
            )

    # Schedule the reminder after `reminder_time` minutes
    threading.Timer(reminder_time.total_seconds(), remind).start()


def is_ticket_assigned(ticket_ts):
    status = ticket_manager.get_ticket_status(ticket_ts)
    return status != "unassigned"


@app.action("user_select_action")
def select_user(ack, body, client):
    ack()
    selected_user_data = body["actions"][0]["selected_option"]["value"].split("@@")
    selected_user = selected_user_data[0]
    user_who_requested = selected_user_data[1]
    response_ts = selected_user_data[2]
    user_input = selected_user_data[3]
    reported_at = selected_user_data[4]
    channel_id = body["channel"]["id"]
    thread_ts = body["container"]["message_ts"]
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
    timestamp_utc = datetime.utcnow()
    timestamp_jakarta = convert_utc_to_jakarta(timestamp_utc)
    ticket_key_for_user = f"{user_who_requested}@@{response_ts}@@{truncate_value(user_input)}@@{reported_at}@@{selected_user}"

    category_options = [
        {
            "text": {"type": "plain_text", "text": category},
            "value": f"{category}@@{ticket_key_for_user}",
        }
        for category in categories
    ]

    ticket_manager.update_ticket_status(thread_ts, "assigned")

    if selected_user in ["S05RYHJ41C6", "S02R59UL0RH"]:
        user_info = client.users_info(user=body["user"]["id"])
        selected_user_name = user_info["user"]["real_name"]
        client.chat_postMessage(
            channel=user_who_requested,
            thread_ts=response_ts,
            text=f"Sorry <@{user_who_requested}>, your issue isn't within Live Ops's domain. But don't worry, <!subteam^{selected_user}> will take care of it soon.",
        )
        handover_response = client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=f"We've officially handed off this hot potato to <!subteam^{selected_user}>. Now, let's dive back into our awesome work!",
        )
        sheet_manager.update_ticket(
            f"live-ops.{thread_ts}",
            {"handed_over_by": selected_user_name, "handed_over_at": timestamp_utc},
        )
        if handover_response["ok"]:
            updated_blocks = [
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
                            "text": f"*Problem:*\n`{truncate_value(user_input)}`",
                        },
                    ],
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f":handshake: Handover to <!subteam^{selected_user}>",
                    },
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
                            "text": f"*Problem:*\n`{truncate_value(user_input)}`",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Current Progress:*\n:handshake: Handover to <!subteam^{selected_user}>",
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

            client.chat_update(
                channel=channel_id,
                ts=thread_ts,
                blocks=updated_blocks,
            )
            reflected_post = client.chat_postMessage(
                channel=reflected_cn, blocks=reflected_msg
            )
            if reflected_post["ok"]:
                ts = reflected_post["ts"]
                full_user_input = ticket_manager.get_user_input(thread_ts)
                client.chat_postMessage(
                    channel=reflected_cn,
                    thread_ts=ts,
                    text=f"Hi <!subteam^{selected_user}>,\nCould you lend a hand to <@{user_who_requested}> with the following problem: `{full_user_input}`? \nMuch appreciated!",
                )
    else:
        user_info = client.users_info(user=selected_user)
        selected_user_name = user_info["user"]["real_name"]
        client.chat_postMessage(
            channel=user_who_requested,
            thread_ts=response_ts,
            text=f"<@{user_who_requested}> your issue will be handled by <@{selected_user}>. We will check and text you asap. Please wait ya.",
        )

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
            updated_blocks = [
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
                            "text": f"*Problem:*\n`{truncate_value(user_input)}`",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Picked Up By:*\n<@{selected_user}>",
                        },
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
                            "text": f"*Problem:*\n`{truncate_value(user_input)}`",
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

            client.chat_update(
                channel=channel_id,
                ts=thread_ts,
                blocks=updated_blocks,
            )

            reflected_post = client.chat_postMessage(
                channel=reflected_cn, blocks=reflected_msg
            )

            if reflected_post["ok"]:
                reflected_ts = reflected_post["ts"]
                ticket_manager.store_reflected_ts(thread_ts, reflected_ts)
                full_user_input = ticket_manager.get_user_input(thread_ts)
                if len(full_user_input) > 37:
                    client.chat_postMessage(
                        channel=reflected_cn,
                        thread_ts=reflected_ts,
                        text=f"For the full details: `{full_user_input}`",
                    )
                client.chat_postMessage(
                    channel=reflected_cn,
                    thread_ts=reflected_ts,
                    text=f"thread ts: {reflected_ts}",
                )
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
def select_category(ack, body, client):
    ack()
    channel_id = body["channel"]["id"]
    selected_category = body["actions"][0]["selected_option"]["value"].split("@@")
    selected_category_name = selected_category[0]
    user_who_requested = selected_category[1]
    response_ts = selected_category[2]
    user_input = selected_category[3]
    reported_at = selected_category[4]
    selected_user = selected_category[5]
    thread_ts = body["container"]["message_ts"]
    reflected_ts = ticket_manager.get_reflected_ts(thread_ts)
    ticket_key_for_user = f"{user_who_requested}@@{response_ts}@@{truncate_value(user_input)}@@{reported_at}@@{selected_user}@@{selected_category_name}"

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
            "private_metadata": f"{thread_ts}@@{user_who_requested}@@{reported_at}@@{truncate_value(user_input)}@@{selected_user}@@{channel_id}@@{response_ts}",
            "submit": {"type": "plain_text", "text": "Submit"},
        }
        client.views_open(trigger_id=trigger_id, view=modal_view)
    else:
        updated_blocks = [
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
                        "text": f"*Problem:*\n`{truncate_value(user_input)}`",
                    },
                    {"type": "mrkdwn", "text": f"*Picked up by:*\n<@{selected_user}>"},
                    {
                        "type": "mrkdwn",
                        "text": f"*Category:*\n{selected_category_name}",
                    },
                ],
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
                        "text": f"*Problem:*\n`{truncate_value(user_input)}`",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Current Progress:*\nBeing resolved",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Issue Category:*\n{selected_category_name}",
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

        client.chat_update(channel=channel_id, ts=thread_ts, blocks=updated_blocks)

        client.chat_update(channel=reflected_cn, ts=reflected_ts, blocks=reflected_msg)

        sheet_manager.update_ticket(
            f"live-ops.{thread_ts}",
            {"category_issue": selected_category_name},
        )


@app.view("custom_category_modal")
def select_custom_category(ack, body, client, view, logger):
    ack()
    user_id = body["user"]["id"]
    custom_category = view["state"]["values"]["custom_category_block"][
        "custom_category_input"
    ]["value"]
    values = view["private_metadata"].split("@@")
    thread_ts = values[0]
    user_who_requested = values[1]
    reported_at = values[2]
    user_input = values[3]
    selected_user = values[4]
    channel_id = values[5]
    response_ts = values[6]
    reflected_ts = ticket_manager.get_reflected_ts(thread_ts)
    ticket_key_for_user = f"{user_who_requested}@@{response_ts}@@{truncate_value(user_input)}@@{reported_at}@@{selected_user}@@{custom_category}"

    try:
        updated_blocks = [
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
                        "text": f"*Problem:*\n`{truncate_value(user_input)}`",
                    },
                    {"type": "mrkdwn", "text": f"*Picked up by:*\n<@{selected_user}>"},
                    {
                        "type": "mrkdwn",
                        "text": f"*Category:*\n{custom_category}",
                    },
                ],
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
                        "text": f"*Problem:*\n`{truncate_value(user_input)}`",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Current Progress:*\nBeing resolved",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Issue Category:*\n{custom_category}",
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

        client.chat_update(channel=channel_id, ts=thread_ts, blocks=updated_blocks)

        client.chat_update(channel=reflected_cn, ts=reflected_ts, blocks=reflected_msg)

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
def resolve_button(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    user_info = client.users_info(user=user_id)
    user_name = user_info["user"]["real_name"]
    channel_id = body["channel"]["id"]
    thread_ts = body["container"]["message_ts"]
    reflected_ts = ticket_manager.get_reflected_ts(thread_ts)
    elements = body["message"]["blocks"][4]["elements"]
    resolve_button_value = elements[0]["value"].split("@@")
    user_who_requested_ticket_id = resolve_button_value[0]
    user_message_ts = resolve_button_value[1]
    user_input = resolve_button_value[2]
    ticket_reported_at = resolve_button_value[3]
    selected_user = resolve_button_value[4]
    selected_category = resolve_button_value[5]
    timestamp_utc = datetime.utcnow()
    timestamp_jakarta = convert_utc_to_jakarta(timestamp_utc)
    response = client.chat_update(
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
                        "text": f"*Problem:*\n`{truncate_value(user_input)}`",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Picked up by:*\n<@{selected_user}>",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Category:*\n{selected_category}",
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
    sheet_manager.update_ticket(
        f"live-ops.{thread_ts}",
        {"resolved_by": user_name, "resolved_at": timestamp_utc},
    )

    if response["ok"]:
        client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=f"<@{user_id}> has resolved the issue at `{timestamp_jakarta}`.",
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
                        "text": f"*Problem:*\n`{truncate_value(user_input)}`",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Current Progress:*\n:white_check_mark: Resolved",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Issue Category:*\n{selected_category}",
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
def reject_button(ack, body, client):
    ack()
    trigger_id = body["trigger_id"]
    message_ts = body["container"]["message_ts"]
    channel_id = body["channel"]["id"]
    user_info = client.users_info(user=body["user"]["id"])
    user_name = user_info["user"]["real_name"]
    elements = body["message"]["blocks"][6]["elements"]
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
        "private_metadata": f"{channel_id}@@{message_ts}@@{reject_button_value} ",
    }

    try:
        client.views_open(trigger_id=trigger_id, view=modal)
    except SlackApiError as e:
        logging.error(f"Error opening modal: {str(e)}")


@app.view("modal_reject")
def show_reject_modal(ack, body, client, view, logger):
    ack()
    try:
        user_id = body["user"]["id"]
        private_metadata = view["private_metadata"].split("@@")
        channel_id = private_metadata[0]
        message_ts = private_metadata[1]
        user_requested_id = private_metadata[2]
        user_message_ts = private_metadata[3]
        user_input = private_metadata[4]
        ticket_reported_at = private_metadata[5]
        reflected_ts = ticket_manager.get_reflected_ts(message_ts)
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
                                "text": f"*Problem:*\n`{truncate_value(user_input)}`",
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

            reflected_msg = [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "Hi @channel :wave:"},
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"We just received an issue from <@{user_requested_id}> at `{ticket_reported_at}`",
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Ticket Number:*\nlive-ops.{message_ts}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Problem:*\n`{truncate_value(user_input)}`",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Current Progress:*\n:x: Issue Rejected",
                        },
                    ],
                },
            ]

            client.chat_postMessage(
                channel=user_requested_id,
                thread_ts=user_message_ts,
                text=f"We are sorry :smiling_face_with_tear: your issue was rejected due to `{reason}` at {timestamp_jakarta}. Let's put another question.",
            )

            client.chat_update(
                channel=reflected_cn, ts=reflected_ts, blocks=reflected_msg
            )

            client.chat_postMessage(
                channel=reflected_cn,
                thread_ts=reflected_ts,
                text=f"We are sorry, this issue was rejected by <@{user_id}> at `{timestamp_jakarta}` due to `{reason}`.",
            )

        else:
            logger.error("No value information available for this channel.")
    except Exception as e:
        logger.error(f"Error handling modal submission: {str(e)}")


# Start your app
if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
