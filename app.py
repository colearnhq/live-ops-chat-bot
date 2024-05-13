import os
import re
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
import logging
from datetime import datetime
from slack_sdk.errors import SlackApiError
from database import SheetManager

load_dotenv(".env")

app = App(token=os.environ.get("SLACK_BOT_TOKEN"))
sheet_manager = SheetManager(
    "creds_file.json", "1dPXiGBN2dDyyQ9TnO6Hi8cQtmbkFBU4O7sI5ztbXT90"
)

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
    "malam": "Selamat Malam"
}

thank_you_response = {
    "makasih": "Iyaa, sama sama :pray:",
    "thank you": "yap, my pleasure :pray:",
    "thx": "yuhu, you're welcome",
    "maaci": "hihi iaa, maaciw juga :wink:",
    "suwun": "enggeh, sami sami :pray:",
    "nuhun": "muhun, sami sami :pray:"
}

greeting_pattern = re.compile(
    r".*(morning|hello|hi|assalamu'alaikum|evening|hey|assalamualaikum|afternoon|shalom|hai|hej|pagi|siang|malam).*",
    re.IGNORECASE,
)

thank_you_pattern = re.compile(
    r".*(makasih|thank|thx|maaci|suwun|nuhun).*",
    re.IGNORECASE
)

@app.event("message")
def handle_message_events(body, say, client):
    event = body.get("event", {})
    user_id = event.get("user")
    chat_timestamp = event["ts"]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        user_info = client.users_info(user=user_id)
        text = event.get("text", "").strip().lower()
        email = user_info["user"].get("name", "unknown") + "@colearn.id"
        full_name = user_info["user"]["profile"].get("real_name", "unknown")
        phone_number = user_info["user"]["profile"].get("phone", "unknown")
        match_greeting = greeting_pattern.search(text)
        match_thank_you = thank_you_pattern.search(text)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if match_greeting:
            greeting = match_greeting.group(1)
            if greeting in greetings_response:
                response = greetings_response[greeting]
                say(
                    f"{response} <@{event['user']}>, Ops are ready to help :confused_dog:"
                )
                say(
                    f"Please type your issue with the following pattern: `/hiops [isi pertanyaan/masalahmu]`"
                )
        elif match_thank_you:
            thank_you = match_thank_you.group(1)
            if thank_you in thank_you_response:
                response = thank_you_response[thank_you]
                say(response)
        else:
            say(f"Hi <@{event['user']}>, Ops are ready to help :confused_dog:")
            say(
                f"Please type your issue with this following pattern: `/hiops [isi pertanyaan/masalahmu]`"
            )
        sheet_manager.log_ticket(
            chat_timestamp, timestamp, user_id, full_name, email, phone_number, text
        )
    except Exception as e:
        logging.error(f"Error handling message: {str(e)}")


@app.command("/hiops")
def handle_hiops_command(ack, body, client, say):
    ack()
    user_input = body.get("text", "No message provided.")
    user_id = body["user_id"]
    channel_id = "C0719R3NQ91"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    categories = ['Data', 'Ajar', 'Guru Piket', 'Recording Video']
    categories.sort()

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
                        {"type": "mrkdwn", "text": f"*Reported at:*\n{timestamp}"},
                        {
                            "type": "mrkdwn",
                            "text": f"*Problem:*\n{user_input}",
                        },
                    ],
                },
            ]
        

        response_for_user = client.chat_postMessage(channel=user_id, blocks=ticket)
        ticket_key_for_user = f"{user_id},{response_for_user["ts"]},{user_input},{timestamp}"
        members_result = client.conversations_members(channel=channel_id)
        members = members_result["members"] if members_result["ok"] else []
        user_options = [
            {"text": {"type": "plain_text", "text": f"<@{member}>"}, "value": f"{member},{user_id},{response_for_user["ts"]}"}
            for member in members
        ]
        category_options = [
            {"text": {"type": "plain_text", "text": category}, "value": f"{category},{ticket_key_for_user}"}
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
                            "text": f"We just received a ticket from <@{user_id}> at `{timestamp}`",
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
                                "text": f"*Problem:*\n{user_input}",
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

        
        result = client.chat_update(channel=channel_id, ts=ts, blocks=blocks)
        sheet_manager.init_ticket_row(
            f"live-ops.{result['ts']}",
            user_id,
            body["user_name"],
            user_input,
            timestamp,
        )
        if not result["ok"]:
            say("Failed to post message")
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")


@app.action("user_select_action")
def handle_user_selection(ack, body, client):
    ack()
    selected_user_data = body["actions"][0]["selected_option"]["value"].split(',')
    selected_user = selected_user_data[0]
    user_who_requested = selected_user_data[1]
    response_ts = selected_user_data[2]
    channel_id = body["channel"]["id"]
    thread_ts = body["container"]["message_ts"]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    response = client.chat_postMessage(
        channel=channel_id,
        thread_ts=thread_ts,
        text=f"<@{selected_user}> is going to resolve this issue, starting from `{timestamp}`.",
    )
    sheet_manager.update_ticket(
        f"live-ops.{thread_ts}",
        {"handled_by": selected_user, "handled_at": timestamp},
    )
    if response["ok"]:
        client.chat_postMessage(
            channel=user_who_requested,
            thread_ts=response_ts,
            text=f"<@{user_who_requested}> your issue will be handled by <@{selected_user}>. We will check and text you asap. Please wait ya.",
        )
    else:
        logging.error(f"Failed to post message: {response['error']}")

    if not response["ok"]:
        logging.error(f"Failed to post message: {response['error']}")

@app.action("category_select_action")
def handle_category_selection(ack, body, client):
    ack()
    selected_category = body['actions'][0]['selected_option']['value'].split(',')
    print("ini kateogry", selected_category)
    selected_category_name = selected_category[0]
    thread_ts = body["container"]["message_ts"]
    sheet_manager.update_ticket(
        f"live-ops.{thread_ts}",
        {"category_issue": selected_category_name},
    )


@app.action("resolve_button")
def handle_resolve_button(ack, body, client):
    ack()
    user_id = body["user"]["id"]
    channel_id = body["channel"]["id"]
    thread_ts = body["container"]["message_ts"]
    elements = body["message"]["blocks"][7]["elements"]
    resolve_button_value = elements[0]["value"].split(",")
    user_who_requested_ticket_id = resolve_button_value[0]
    user_message_ts = resolve_button_value[1]
    user_input = resolve_button_value[2]
    ticket_reported_at = resolve_button_value[3]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    response = client.chat_postMessage(
        channel=channel_id,
        thread_ts=thread_ts,
        text=f"<@{user_id}> has resolved the issue at `{timestamp}`.",
    )
    sheet_manager.update_ticket(
        f"live-ops.{thread_ts}",
        {"resolved_by": body["user"]["name"], "resolved_at": timestamp},
    )
    if response["ok"]:
        client.chat_postMessage(
            channel=user_who_requested_ticket_id,
            thread_ts=user_message_ts,
            text=f"<@{user_who_requested_ticket_id}> your issue has been resolved at `{timestamp}`. Thank you :blob-bear-dance:",
        )
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
                            "text": f"*Problem:*\n{user_input}",
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
    else:
        logging.error(f"Failed to post message: {response['error']}")


@app.action("reject_button")
def handle_reject_button(ack, body, client):
    ack()
    trigger_id = body["trigger_id"]
    message_ts = body["container"]["message_ts"]
    channel_id = body["channel"]["id"]
    elements = body["message"]["blocks"][7]["elements"]
    reject_button_value = elements[0]["value"].split(",")
    user_who_requested_ticket_id = reject_button_value[0]
    user_message_ts = reject_button_value[1]
    user_input = reject_button_value[2]
    ticket_reported_at = reject_button_value[3]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheet_manager.update_ticket(
                f"live-ops.{message_ts}",
                {"rejected_by": body["user"]["name"], "rejected_at": timestamp},
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
        "private_metadata": f"{channel_id},{message_ts},{user_who_requested_ticket_id},{user_message_ts},{user_input},{ticket_reported_at} ",
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
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        response = client.chat_postMessage(
                channel=channel_id,
                thread_ts=message_ts,
                text=f"<@{user_id}> has rejected the issue at `{timestamp}` due to: `{reason}`.",
            )
        if response["ok"]:
                client.chat_postMessage(
                    channel=user_requested_id,
                    thread_ts=user_message_ts,
                    text=f"We are sorry :smiling_face_with_tear: your issue was rejected due to `{reason}`. Let's put another question.",
                )
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
                                    "text": f"*Problem:*\n{user_input}",
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
        else:
            logger.error("No value information available for this channel.")
    except Exception as e:
        logger.error(f"Error handling modal submission: {str(e)}")


# Start your app
if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
