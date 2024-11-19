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
        self.files = {}

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
        return self.ticket_status.get(thread_ts, "unassigned")

    def clear_ticket_status(self, thread_ts):
        if thread_ts in self.ticket_status:
            del self.ticket_status[thread_ts]

    def store_files(self, thread_ts, files):
        self.files[thread_ts] = files

    def get_files(self, thread_ts):
        files = self.files.get(thread_ts)
        return files


ticket_manager = TicketManager()


def convert_utc_to_jakarta(utc_dt):
    from pytz import timezone

    fmt = "%Y-%m-%d %H:%M:%S %Z%z"
    utc_dt = utc_dt.replace(tzinfo=timezone("UTC"))
    jakarta_time = utc_dt.astimezone(timezone("Asia/Jakarta"))
    return jakarta_time.strftime(fmt)


def schedule_reminder(client, channel_id, thread_ts, reminder_time, ticket_ts):
    def remind():
        if not is_ticket_assigned(ticket_ts):
            omar_id = "U020SH7JJF3"
            client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=f"Ribbit! 🐸 Pepe’s getting impatient, and this ticket's feeling lonely! Can you <@{omar_id}> hop in and rescue it within the next 2 minutes before Pepe starts croaking louder? 🐸⏳",
            )

    threading.Timer(reminder_time.total_seconds(), remind).start()


def is_ticket_assigned(ticket_ts):
    status = ticket_manager.get_ticket_status(ticket_ts)
    return status != "unassigned"


def truncate_value(value, max_length=25):
    return (
        value
        if len(value) <= max_length
        else value[:max_length] + "...(continued in thread)"
    )


def inserting_imgs_thread(client, channel_id, ts, files):
    blocks = []

    blocks.append(
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Here are the uploaded images from user:",
            },
        }
    )

    for file in files:
        img_url = file.get("url_private", file.get("thumb_360", file.get("thumb_64")))
        if img_url:
            img_block = {
                "type": "image",
                "image_url": img_url,
                "alt_text": "user_attachment",
            }
            blocks.append(img_block)

    if blocks:
        client.chat_postMessage(
            channel=channel_id,
            thread_ts=ts,
            blocks=blocks,
            text="Here are the uploaded images",
        )


def get_real_name(client, user_id):
    try:
        user_info = client.users_info(user=user_id)
        return user_info["user"]["real_name"]
    except Exception as e:
        return user_id


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


@app.command("/opsdev")
def slash_input(ack, body, client):
    ack()
    categories = ["Piket", "Others", "IT Helpdesk"]
    user_input = body.get("text", "No message provided.")
    category_options = [
        {
            "text": {"type": "plain_text", "text": category},
            "value": f"{category}",
        }
        for category in categories
    ]
    trigger_id = body["trigger_id"]
    channel_id = "C0719R3NQ91"

    modal = {
        "type": "modal",
        "callback_id": "slash_input",
        "title": {
            "type": "plain_text",
            "text": "Don’t Overthink It!",
        },
        "blocks": [
            {
                "type": "section",
                "block_id": "category_block",
                "text": {
                    "type": "mrkdwn",
                    "text": "Please select the category of the issue:",
                },
            },
            {
                "type": "actions",
                "block_id": "category_buttons",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": category["text"]["text"],
                            "emoji": True,
                        },
                        "value": category["value"],
                        "action_id": f"button_{category['value']}",
                        "style": (
                            "danger"
                            if category["text"]["text"] == "Others"
                            else "primary"
                        ),
                    }
                    for category in category_options
                ],
            },
        ],
        "private_metadata": f"{channel_id}@@{user_input}",
    }

    try:
        client.views_open(trigger_id=trigger_id, view=modal)
    except SlackApiError as e:
        logging.error(
            f"Error opening modal: {str(e)} | Response: {e.response['error']}"
        )


@app.action("button_Piket")
def handling_replacement(ack, body, client):
    ack()

    categories = [
        "I need help finding a replacement",
        "No Mentor",
        "I have had a replacement",
    ]

    category_options = [
        {
            "text": {"type": "plain_text", "text": category},
            "value": category,
        }
        for category in categories
    ]

    channel_id = "C0719R3NQ91"
    view_id = body["view"]["id"]

    modal = {
        "type": "modal",
        "callback_id": "slash_input",
        "title": {
            "type": "plain_text",
            "text": "Don’t Overthink It!",
        },
        "blocks": [
            {
                "type": "section",
                "block_id": "category_block",
                "text": {
                    "type": "mrkdwn",
                    "text": "Teacher Replacement Options",
                },
                "accessory": {
                    "type": "static_select",
                    "action_id": "handle_category_selection",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select a category",
                    },
                    "options": [
                        {
                            "text": {
                                "type": "plain_text",
                                "text": category_option["text"]["text"],
                            },
                            "value": category_option["value"],
                        }
                        for category_option in category_options
                    ],
                },
            },
        ],
        "private_metadata": f"{channel_id}@@Piket",
    }

    try:
        client.views_update(view_id=view_id, view=modal)
    except SlackApiError as e:
        logging.error(
            f"Error updating modal: {str(e)} | Response: {e.response['error']}"
        )


@app.action("handle_category_selection")
@app.action("button_Others")
@app.action("button_IT Helpdesk")
def handle_category_selection(ack, body, client):
    ack()
    [channel_id, user_input] = body["view"]["private_metadata"].split("@@")
    piket_category = (
        body.get("view", {})
        .get("state", {})
        .get("values", {})
        .get("category_block", {})
        .get("handle_category_selection", {})
        .get("selected_option", {})
        .get("value", {})
    )
    selected_category = body["actions"][0].get("value", user_input)
    trigger_id = body["trigger_id"]
    if selected_category == "Piket":
        modal_blocks = [
            {
                "type": "input",
                "block_id": "date_block",
                "label": {"type": "plain_text", "text": "Date"},
                "element": {
                    "type": "datepicker",
                    "action_id": "date_picker_action",
                    "placeholder": {"type": "plain_text", "text": "Select a date"},
                },
            },
            {
                "type": "input",
                "block_id": "teacher_request_block",
                "label": {"type": "plain_text", "text": "Teacher who requested"},
                "element": {
                    "action_id": "teacher_request_action",
                    "type": "users_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select Teacher Who Requested",
                    },
                },
            },
            {
                "type": "input",
                "block_id": "teacher_replace_block",
                "label": {"type": "plain_text", "text": "Teacher who replaces"},
                "element": {
                    "action_id": "teacher_replace_action",
                    "type": (
                        "users_select"
                        if piket_category == "I have had a replacement"
                        else "plain_text_input"
                    ),
                    **(
                        {
                            "initial_value": (
                                "I need help finding a replacement"
                                if piket_category == "I need help finding a replacement"
                                else (
                                    "No Mentor"
                                    if piket_category == "No Mentor"
                                    else None
                                )
                            )
                        }
                        if piket_category != "I have had a replacement"
                        else {}
                    ),
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select Teacher Who Replaces",
                    },
                },
            },
            {
                "type": "input",
                "block_id": "grade_block",
                "label": {"type": "plain_text", "text": "Grade"},
                "element": {
                    "type": "number_input",
                    "action_id": "grade_action",
                    "is_decimal_allowed": False,
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Generate Slots"},
                        "action_id": "generate_slot_list",
                    }
                ],
            },
            {
                "type": "input",
                "block_id": "time_class_block",
                "label": {"type": "plain_text", "text": "Class Time"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "time_class_action",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "e.g., 19:15",
                    },
                },
            },
            {
                "type": "input",
                "block_id": "reason_block",
                "label": {"type": "plain_text", "text": "Reason"},
                "element": {
                    "type": "plain_text_input",
                    "multiline": True,
                    "action_id": "reason_action",
                },
            },
            {
                "type": "input",
                "block_id": "direct_lead_block",
                "label": {"type": "plain_text", "text": "Direct Lead"},
                "element": {
                    "action_id": "direct_lead_action",
                    "type": "users_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select Your Direct Lead",
                    },
                },
            },
            {
                "type": "input",
                "block_id": "stem_lead_block",
                "label": {"type": "plain_text", "text": "STEM Lead"},
                "element": {
                    "action_id": "stem_lead_action",
                    "type": "users_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select Your STEM Lead",
                    },
                },
            },
        ]

    elif selected_category == "Others":
        modal_blocks = [
            {
                "type": "input",
                "block_id": "issue_name",
                "label": {"type": "plain_text", "text": "Your Issue"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "user_issue",
                    "multiline": True,
                    "initial_value": user_input,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Describe your issue...",
                    },
                },
            },
            {
                "type": "input",
                "optional": True,
                "block_id": "file_upload_block",
                "label": {"type": "plain_text", "text": "File Upload"},
                "element": {
                    "type": "file_input",
                    "action_id": "file_input_action",
                    "filetypes": ["jpg", "png"],
                    "max_files": 5,
                },
            },
        ]
    elif selected_category == "IT Helpdesk":
        issue_types = ["laptop issue", "network issue", "software issue", "others"]
        urgency_levels = ["low", "medium", "high"]

        issue_type_options = [
            {"text": {"type": "plain_text", "text": type}, "value": type}
            for type in issue_types
        ]

        urgency_level_options = [
            {"text": {"type": "plain_text", "text": level}, "value": level}
            for level in urgency_levels
        ]

        modal_blocks = [
            {
                "type": "input",
                "block_id": "full_name_block",
                "label": {"type": "plain_text", "text": "Full Name"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "full_name_action",
                    "placeholder": {"type": "plain_text", "text": "Your Full Name"},
                },
            },
            {
                "type": "input",
                "block_id": "issue_type_id",
                "label": {"type": "plain_text", "text": "Issue Type"},
                "elements": {
                    "type": "static_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Your Issue Type",
                    },
                    "action_id": "handle_issue_type",
                    "options": issue_type_options,
                },
            },
            {
                "type": "input",
                "block_id": "issue_description",
                "label": {"type": "plain_text", "text": "Description"},
                "element": {
                    "type": "plain_text_input",
                    "multiline": True,
                    "action_id": "issue_description_action",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Describe Your Issue",
                    },
                },
            },
            {
                "type": "input",
                "block_id": "urgency_id",
                "label": {"type": "plain_text", "text": "Urgency Level"},
                "element": {
                    "type": "static_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Determine Your Issue Level",
                    },
                    "action_id": "handle_urgency_level",
                    "options": urgency_level_options
                }
            },
        ]

    updated_modal = {
        "type": "modal",
        "callback_id": "slash_input",
        "title": {
            "type": "plain_text",
            "text": "Think Wisely!",
        },
        "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": modal_blocks,
        "private_metadata": f"{channel_id}@@{selected_category}",
    }

    try:
        client.views_update(view_id=body["view"]["id"], view=updated_modal)
    except SlackApiError as e:
        logging.error(
            f"Error updating modal: {str(e)} | Response: {e.response['error']}"
        )


@app.action("generate_slot_list")
def handle_generate_slot_list(ack, body, client):
    ack()
    state = body["view"]["state"]["values"]
    teacher_replace_block = state["teacher_replace_block"]["teacher_replace_action"]
    teacher_who_replaces_val = teacher_replace_block.get(
        "selected_user"
    ) or teacher_replace_block.get("value")
    selected_cat_on_piket = (
        teacher_who_replaces_val
        if teacher_who_replaces_val == "No Mentor"
        or teacher_who_replaces_val == "I need help finding a replacement"
        else "I have had a replacement"
    )
    grade = state["grade_block"]["grade_action"]["value"]
    slots = sheet_manager.get_slots_by_grade(grade)
    dropdown_options = [
        {"text": {"type": "plain_text", "text": slot}, "value": slot} for slot in slots
    ]

    client.views_update(
        view_id=body["view"]["id"],
        view={
            "type": "modal",
            "callback_id": "slash_input",
            "title": {"type": "plain_text", "text": "Piket Request"},
            "submit": {"type": "plain_text", "text": "Submit"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "date_block",
                    "label": {"type": "plain_text", "text": "Date"},
                    "element": {
                        "type": "datepicker",
                        "action_id": "date_picker_action",
                        "placeholder": {"type": "plain_text", "text": "Select a date"},
                    },
                },
                {
                    "type": "input",
                    "block_id": "teacher_request_block",
                    "label": {"type": "plain_text", "text": "Teacher who requested"},
                    "element": {
                        "action_id": "teacher_request_action",
                        "type": "users_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select Teacher Who Requested",
                        },
                    },
                },
                {
                    "type": "input",
                    "block_id": "teacher_replace_block",
                    "label": {"type": "plain_text", "text": "Teacher who replaces"},
                    "element": {
                        "action_id": "teacher_replace_action",
                        "type": (
                            "users_select"
                            if selected_cat_on_piket == "I have had a replacement"
                            else "plain_text_input"
                        ),
                        **(
                            {
                                "initial_value": (
                                    "I need help finding a replacement"
                                    if selected_cat_on_piket
                                    == "I need help finding a replacement"
                                    else (
                                        "No Mentor"
                                        if selected_cat_on_piket == "No Mentor"
                                        else None
                                    )
                                )
                            }
                            if selected_cat_on_piket != "I have had a replacement"
                            else {}
                        ),
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select Teacher Who Replaces",
                        },
                    },
                },
                {
                    "type": "input",
                    "block_id": "grade_block",
                    "label": {"type": "plain_text", "text": "Grade"},
                    "element": {
                        "type": "number_input",
                        "action_id": "grade_action",
                        "is_decimal_allowed": False,
                    },
                },
                {
                    "type": "input",
                    "block_id": "slot_name_block",
                    "label": {"type": "plain_text", "text": "Slot Name"},
                    "element": {
                        "type": "static_select",
                        "action_id": "slot_name_action",
                        "placeholder": {"type": "plain_text", "text": "Select a slot"},
                        "options": dropdown_options,
                    },
                },
                {
                    "type": "input",
                    "block_id": "time_class_block",
                    "label": {"type": "plain_text", "text": "Class Time"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "time_class_action",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "e.g., 19:15",
                        },
                    },
                },
                {
                    "type": "input",
                    "block_id": "reason_block",
                    "label": {"type": "plain_text", "text": "Reason"},
                    "element": {
                        "type": "plain_text_input",
                        "multiline": True,
                        "action_id": "reason_action",
                    },
                },
                {
                    "type": "input",
                    "block_id": "direct_lead_block",
                    "label": {"type": "plain_text", "text": "Direct Lead"},
                    "element": {
                        "action_id": "direct_lead_action",
                        "type": "users_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select Your Direct Lead",
                        },
                    },
                },
                {
                    "type": "input",
                    "block_id": "stem_lead_block",
                    "label": {"type": "plain_text", "text": "STEM Lead"},
                    "element": {
                        "action_id": "stem_lead_action",
                        "type": "users_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select Your STEM Lead",
                        },
                    },
                },
            ],
            "private_metadata": body["view"]["private_metadata"],
        },
    )


@app.view("slash_input")
def send_the_user_input(ack, body, client, say, view):
    ack()
    private_metadata = view["private_metadata"].split("@@")
    category = private_metadata[1]
    channel_id = private_metadata[0]
    view_state = body["view"]["state"]["values"]
    user_id = body["user"]["id"]
    reporter_name = body["user"]["username"]
    timestamp_utc = datetime.utcnow()
    timestamp_jakarta = convert_utc_to_jakarta(timestamp_utc)
    init_result = client.chat_postMessage(
        channel=channel_id, text="Initializing ticket..."
    )
    initial_ts = init_result["ts"]

    if category == "Piket":
        date = view["state"]["values"]["date_block"]["date_picker_action"][
            "selected_date"
        ]
        teacher_requested = view["state"]["values"]["teacher_request_block"][
            "teacher_request_action"
        ]["selected_user"]
        teacher_replace_block = view["state"]["values"]["teacher_replace_block"][
            "teacher_replace_action"
        ]
        teacher_replace = teacher_replace_block.get(
            "selected_user"
        ) or teacher_replace_block.get("value")

        grade = view["state"]["values"]["grade_block"]["grade_action"]["value"]
        slot_name = view["state"]["values"]["slot_name_block"]["slot_name_action"][
            "selected_option"
        ]["value"]
        time_class = view["state"]["values"]["time_class_block"]["time_class_action"][
            "value"
        ]
        reason = view["state"]["values"]["reason_block"]["reason_action"]["value"]
        direct_lead = view["state"]["values"]["direct_lead_block"][
            "direct_lead_action"
        ]["selected_user"]
        stem_lead = view["state"]["values"]["stem_lead_block"]["stem_lead_action"][
            "selected_user"
        ]

        teacher_requested_name = get_real_name(client, teacher_requested)
        teacher_replaces_name = get_real_name(client, teacher_replace)
        direct_lead_name = get_real_name(client, direct_lead)
        stem_lead_name = get_real_name(client, stem_lead)

        piket_channel_id = channel_id

        piket_blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Hi <@{user_id}> :blob-wave:\nYour piket request have been received with this following number: `piket.{initial_ts}`",
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Your Name:*\n{reporter_name}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Requested at:*\n{timestamp_jakarta}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Ticket Category:*\n`{category}`",
                    },
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Please wait ya, we will give the update in this thread.",
                },
            },
        ]

        response_for_user = client.chat_postMessage(
            channel=user_id, blocks=piket_blocks
        )

        piket_data = f"{date}@@{teacher_requested}@@{teacher_replace}@@{grade}@@{slot_name}@@{time_class}@@{reason}@@{direct_lead}@@{stem_lead}"
        ticket_key_for_user = f"{user_id}@@{response_for_user['ts']}@@{timestamp_jakarta}@@{piket_data}@@{category}"
        ticket_key_for_request_teacher = f"{user_id}@@{response_for_user['ts']}@@{timestamp_jakarta}@@{date}@@{teacher_requested}@@{grade}@@{slot_name}@@{time_class}@@{reason}@@{direct_lead}@@{stem_lead}"
        teacher_replace_state = (
            f"<@{teacher_replace}>"
            if teacher_replace != "No Mentor"
            and teacher_replace != "I need help finding a replacement"
            else f"`{teacher_replace}`"
        )

        piket_message = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Hi @tim_ajar\nWe've got a request from <@{teacher_requested}> with detail as below:",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Class Date:*\n`{date}`"},
                    {"type": "mrkdwn", "text": f"*Time of Class:*\n`{time_class}`"},
                    {
                        "type": "mrkdwn",
                        "text": f"*Teacher Requested:*\n<@{teacher_requested}>",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Teacher Replaces:*\n{teacher_replace_state}",
                    },
                    {"type": "mrkdwn", "text": f"*Slot Name:*\n`{grade}-{slot_name}`"},
                    {"type": "mrkdwn", "text": f"*Reason:*\n```{reason}```"},
                    {"type": "mrkdwn", "text": f"*Direct Lead:*\n<@{direct_lead}>"},
                    {"type": "mrkdwn", "text": f"*STEM Lead:*\n<@{stem_lead}>"},
                ],
            },
            {"type": "divider"},
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Piket Ticket Number:* piket.{initial_ts}",
                    }
                ],
            },
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

        if teacher_replace == "I need help finding a replacement":
            if len(piket_message) > 4:
                piket_message[4]["elements"].clear()
                piket_message[4]["elements"] = [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "emoji": True,
                            "text": "Edit",
                        },
                        "value": ticket_key_for_request_teacher,
                        "action_id": "edit_piket_msg",
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
                ]

        result = client.chat_update(
            channel=piket_channel_id, ts=initial_ts, blocks=piket_message
        )
        sheet_manager.init_piket_row(
            f"piket.{result['ts']}",
            teacher_requested_name,
            teacher_replaces_name,
            grade,
            slot_name,
            date,
            time_class,
            reason,
            direct_lead_name,
            stem_lead_name,
            timestamp_utc,
        )

    elif category == "Others":
        issue_description = view_state["issue_name"]["user_issue"]["value"]
        files = (
            view_state.get("file_upload_block", {})
            .get("file_input_action", {})
            .get("files", [])
        )
        try:
            ticket_manager.store_user_input(initial_ts, issue_description)
            if files:
                ticket_manager.store_files(initial_ts, files)

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
                        {
                            "type": "mrkdwn",
                            "text": f"*Reported at:*\n{timestamp_jakarta}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Problem:*\n`{truncate_value(issue_description)}`",
                        },
                    ],
                },
            ]

            response_for_user = client.chat_postMessage(channel=user_id, blocks=ticket)
            ticket_key_for_user = f"{user_id}@@{response_for_user['ts']}@@{truncate_value(issue_description)}@@{timestamp_jakarta}@@{category}"

            members_result = client.conversations_members(channel=channel_id)
            if members_result["ok"]:
                members = members_result["members"]
            else:
                members = []

            group_mentions = ["S05RYHJ41C6", "S02R59UL0RH", "U05LPMNQBBK"]
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
                    "value": f"{member}@@{user_id}@@{response_for_user['ts']}@@{truncate_value(issue_description)}@@{timestamp_jakarta}@@{category}",
                }
                for member in members
            ]

            if response_for_user["ok"]:
                ts = response_for_user["ts"]
                if len(issue_description) > 25:
                    client.chat_postMessage(
                        channel=user_id,
                        thread_ts=ts,
                        text=f"For the problem details: `{issue_description}`",
                    )

            if init_result["ok"]:
                ts = initial_ts
                blocks = [
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": "Hi Team :wave:"},
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
                                "text": f"*Problem:*\n`{truncate_value(issue_description)}`",
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

            result = client.chat_update(
                channel=channel_id,
                ts=ts,
                blocks=blocks,
            )

            sheet_manager.init_ticket_row(
                f"live-ops.{result['ts']}",
                user_id,
                reporter_name,
                issue_description,
                timestamp_utc,
            )
            if result["ok"]:
                if files:
                    inserting_imgs_thread(client, channel_id, ts, files)
                if len(issue_description) > 37:
                    client.chat_postMessage(
                        channel=channel_id,
                        thread_ts=ts,
                        text=f"For the problem details: `{issue_description}`",
                    )
            else:
                say("Failed to post message")

            reminder_time = timedelta(minutes=3)
            schedule_reminder(client, channel_id, ts, reminder_time, result["ts"])
        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")


@app.action("edit_piket_msg")
def edit_piket_msg(ack, body, client):
    ack()
    [
        reporter_id,
        report_ts,
        timestamp,
        class_date,
        teacher_requested,
        grade,
        slot_name,
        time_class,
        reason,
        direct_lead,
        stem_lead,
    ] = body["message"]["blocks"][4]["elements"][0]["value"].split("@@")
    previous_values = {
        "date": class_date,
        "teacher_requested": teacher_requested,
        "grade": grade,
        "slot_name": slot_name,
        "time_class": time_class,
        "reason": reason,
        "direct_lead": direct_lead,
        "stem_lead": stem_lead,
    }
    thread_ts = body["container"]["message_ts"]
    channel_id = body["channel"]["id"]
    trigger_id = body["trigger_id"]

    modal_blocks = [
        {
            "type": "input",
            "block_id": "date_block",
            "label": {"type": "plain_text", "text": "Date"},
            "element": {
                "type": "datepicker",
                "action_id": "date_picker_action",
                "initial_date": previous_values.get("date", None),
                "placeholder": {"type": "plain_text", "text": "Select a date"},
            },
        },
        {
            "type": "input",
            "block_id": "teacher_request_block",
            "label": {"type": "plain_text", "text": "Teacher who requested"},
            "element": {
                "action_id": "teacher_request_action",
                "type": "users_select",
                "initial_user": previous_values.get("teacher_requested", None),
                "placeholder": {
                    "type": "plain_text",
                    "text": "Select Teacher Who Requested",
                },
            },
        },
        {
            "type": "input",
            "block_id": "teacher_replace_block",
            "label": {"type": "plain_text", "text": "Teacher who replaces"},
            "element": {
                "action_id": "teacher_replace_action",
                "type": "users_select",
                "placeholder": {
                    "type": "plain_text",
                    "text": "Select Teacher Who Replaces",
                },
            },
        },
        {
            "type": "input",
            "block_id": "grade_block",
            "label": {"type": "plain_text", "text": "Grade"},
            "element": {
                "type": "number_input",
                "action_id": "grade_action",
                "initial_value": str(previous_values.get("grade", "")),
                "is_decimal_allowed": False,
            },
        },
        {
            "type": "input",
            "block_id": "slot_name_block",
            "label": {"type": "plain_text", "text": "Slot Name"},
            "element": {
                "type": "plain_text_input",
                "action_id": "slot_name_action",
                "initial_value": previous_values.get("slot_name", ""),
                "placeholder": {
                    "type": "plain_text",
                    "text": "please input grade first and click generate button",
                },
            },
        },
        {
            "type": "input",
            "block_id": "time_class_block",
            "label": {"type": "plain_text", "text": "Time of Class"},
            "element": {
                "type": "plain_text_input",
                "action_id": "time_class_action",
                "initial_value": previous_values.get("time_class", ""),
                "placeholder": {"type": "plain_text", "text": "contoh: 19:15"},
            },
        },
        {
            "type": "input",
            "block_id": "reason_block",
            "label": {"type": "plain_text", "text": "Reason"},
            "element": {
                "type": "plain_text_input",
                "multiline": True,
                "action_id": "reason_action",
                "initial_value": previous_values.get("reason", ""),
            },
        },
        {
            "type": "input",
            "block_id": "direct_lead_block",
            "label": {"type": "plain_text", "text": "Direct Lead"},
            "element": {
                "action_id": "direct_lead_action",
                "type": "users_select",
                "initial_user": previous_values.get("direct_lead", None),
                "placeholder": {
                    "type": "plain_text",
                    "text": "Select Your Direct Lead",
                },
            },
        },
        {
            "type": "input",
            "block_id": "stem_lead_block",
            "label": {"type": "plain_text", "text": "STEM Lead"},
            "element": {
                "action_id": "stem_lead_action",
                "type": "users_select",
                "initial_user": previous_values.get("stem_lead", None),
                "placeholder": {
                    "type": "plain_text",
                    "text": "Select Your STEM Lead",
                },
            },
        },
    ]

    modal = {
        "type": "modal",
        "callback_id": "modal_edit_msg",
        "title": {
            "type": "plain_text",
            "text": "Piket!",
        },
        "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": modal_blocks,
        "private_metadata": f"{reporter_id}@@{report_ts}@@{timestamp}@@{thread_ts}@@{channel_id}",
    }

    try:
        client.views_open(trigger_id=trigger_id, view=modal)
    except SlackApiError as e:
        logging.error(f"Error opening modal: {str(e)}")


@app.view("modal_edit_msg")
def show_editted_piket_msg(ack, body, client, view, logger):
    ack()
    try:
        user_id = body["user"]["id"]
        user_info = client.users_info(user=user_id)
        user_name = user_info["user"]["real_name"]
        [reporter_id, report_ts, timestamp, thread_ts, channel_id] = view[
            "private_metadata"
        ].split("@@")
        date = view["state"]["values"]["date_block"]["date_picker_action"][
            "selected_date"
        ]
        teacher_requested = view["state"]["values"]["teacher_request_block"][
            "teacher_request_action"
        ]["selected_user"]
        teacher_replace = view["state"]["values"]["teacher_replace_block"][
            "teacher_replace_action"
        ]["selected_user"]
        grade = view["state"]["values"]["grade_block"]["grade_action"]["value"]
        slot_name = view["state"]["values"]["slot_name_block"]["slot_name_action"][
            "value"
        ]
        time_class = view["state"]["values"]["time_class_block"]["time_class_action"][
            "value"
        ]
        reason = view["state"]["values"]["reason_block"]["reason_action"]["value"]
        direct_lead = view["state"]["values"]["direct_lead_block"][
            "direct_lead_action"
        ]["selected_user"]
        stem_lead = view["state"]["values"]["stem_lead_block"]["stem_lead_action"][
            "selected_user"
        ]
        timestamp_utc = datetime.utcnow()
        timestamp_jakarta = convert_utc_to_jakarta(timestamp_utc)

        piket_message = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Hi @tim_ajar\nWe've got a request from <@{teacher_requested}> with detail as below:",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Class Date:*\n`{date}`"},
                    {
                        "type": "mrkdwn",
                        "text": f"*Time of Class:*\n`{time_class}`",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Teacher Requested:*\n<@{teacher_requested}>",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Teacher Replaces:*\n<@{teacher_replace}>",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Slot Name:*\n`{grade}-{slot_name}`",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Reason:*\n```{reason}```",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Direct Lead:*\n<@{direct_lead}>",
                    },
                    {"type": "mrkdwn", "text": f"*STEM Lead:*\n<@{stem_lead}>"},
                ],
            },
            {"type": "divider"},
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Piket Ticket Number:* piket.{report_ts}",
                    }
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":white_check_mark: <@{user_id}> approved the request",
                },
            },
        ]

        response = client.chat_update(
            channel=channel_id, ts=thread_ts, blocks=piket_message
        )
        if response["ok"]:
            client.chat_postMessage(
                channel=reporter_id,
                thread_ts=report_ts,
                text=f"Your request approved. Your class on `{date}` at `{time_class}`, the teacher replacement is <@{teacher_replace}>",
            )

            client.chat_postMessage(channel=reflected_cn, blocks=piket_message)

            client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=f"This request has been approved at `{timestamp_jakarta}` by <@{user_id}>",
            )

            sheet_manager.update_piket(
                f"piket.{thread_ts}",
                {
                    "status": "Approved",
                    "approved_by": user_name,
                    "teacher_replaces": get_real_name(client, teacher_replace),
                    "approved_at": timestamp_utc,
                    "teacher_requested": get_real_name(client, teacher_requested),
                    "grade": str(grade),
                    "slot_name": slot_name,
                    "class_date": str(date),
                    "class_time": str(time_class),
                    "reason": reason,
                    "direct_lead": get_real_name(client, direct_lead),
                    "stem_lead": get_real_name(client, stem_lead),
                    "edited_at": timestamp_utc,
                },
            )

    except Exception as e:
        logger.error(f"Error handling modal submission: {str(e)}")


@app.action("user_select_action")
def select_user(ack, body, client):
    ack()
    person_who_assigns = body["user"]["id"]
    person_who_assigns_name = get_real_name(client, person_who_assigns)
    [
        selected_user,
        user_who_requested,
        response_ts,
        user_input,
        reported_at,
        ticket_category,
    ] = body["actions"][0]["selected_option"]["value"].split("@@")
    channel_id = body["channel"]["id"]
    thread_ts = body["container"]["message_ts"]
    categories = [
        "Ajar",
        "Cuti",
        "Data related",
        "Observasi",
        "Polling",
        "Recording Video",
        "Zoom",
        "Others",
    ]
    timestamp_utc = datetime.utcnow()
    timestamp_jakarta = convert_utc_to_jakarta(timestamp_utc)
    ticket_key_for_user = f"{user_who_requested}@@{response_ts}@@{truncate_value(user_input)}@@{reported_at}@@{selected_user}@@{ticket_category}"
    category_options = [
        {
            "text": {"type": "plain_text", "text": category},
            "value": f"{category}@@{ticket_key_for_user}",
        }
        for category in categories
    ]

    files = ticket_manager.get_files(thread_ts)
    print(f"check the files {files} and ts {thread_ts} on select_user")
    ticket_manager.update_ticket_status(thread_ts, "assigned")

    if selected_user in ["S05RYHJ41C6", "S02R59UL0RH", "U05LPMNQBBK"]:
        user_info = client.users_info(user=body["user"]["id"])
        selected_user_name = user_info["user"]["real_name"]
        other_div_mention = (
            f"<@{selected_user}>"
            if selected_user == "U05LPMNQBBK"
            else f"<!subteam^{selected_user}>"
        )
        client.chat_postMessage(
            channel=user_who_requested,
            thread_ts=response_ts,
            text=f"Sorry <@{user_who_requested}>, your issue isn't within Live Ops's domain. But don't worry, {other_div_mention} will take care of it soon.",
        )
        handover_response = client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=f"We've officially handed off this hot potato to {other_div_mention}. Now, let's dive back into our awesome work!",
        )
        sheet_manager.update_ticket(
            f"live-ops.{thread_ts}",
            {
                "handed_over_by": selected_user_name,
                "handed_over_at": timestamp_utc,
                "assigned_by": person_who_assigns_name,
            },
        )
        if handover_response["ok"]:
            updated_blocks = [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "Hi Team :wave:"},
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
                        "text": f":handshake: Handover to {other_div_mention}",
                    },
                },
            ]

            reflected_msg = [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "Hi Team :wave:"},
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
                            "text": f"*Current Progress:*\n:handshake: Handover to {other_div_mention}",
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
                if files:
                    inserting_imgs_thread(client, reflected_cn, ts, files)

                full_user_input = ticket_manager.get_user_input(thread_ts)
                client.chat_postMessage(
                    channel=reflected_cn,
                    thread_ts=ts,
                    text=f"Hi {other_div_mention},\nCould you lend a hand to <@{user_who_requested}> with the following problem: `{full_user_input}`? \nMuch appreciated!",
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
            text=f"<@{selected_user}> is on the case and will tackle this issue starting at `{timestamp_jakarta}`. (Assigned by: <@{person_who_assigns}>)",
        )

        sheet_manager.update_ticket(
            f"live-ops.{thread_ts}",
            {
                "handled_by": selected_user_name,
                "handled_at": timestamp_utc,
                "assigned_by": person_who_assigns_name,
            },
        )

        if response["ok"]:
            updated_blocks = [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "Hi Team :wave:"},
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
                    "text": {"type": "mrkdwn", "text": "Hi Team :wave:"},
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
                if files:
                    inserting_imgs_thread(client, reflected_cn, reflected_ts, files)
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
    [
        selected_category_name,
        user_who_requested,
        response_ts,
        user_input,
        reported_at,
        selected_user,
        ticket_category,
    ] = body["actions"][0]["selected_option"]["value"].split("@@")
    thread_ts = body["container"]["message_ts"]
    reflected_ts = ticket_manager.get_reflected_ts(thread_ts)
    ticket_key_for_user = f"{user_who_requested}@@{response_ts}@@{truncate_value(user_input)}@@{reported_at}@@{selected_user}@@{selected_category_name}@@{ticket_category}"

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
            "private_metadata": f"{thread_ts}@@{user_who_requested}@@{reported_at}@@{truncate_value(user_input)}@@{selected_user}@@{channel_id}@@{response_ts}@@{ticket_category}",
            "submit": {"type": "plain_text", "text": "Submit"},
        }
        client.views_open(trigger_id=trigger_id, view=modal_view)
    else:
        updated_blocks = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "Hi Team :wave:"},
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
                "text": {"type": "mrkdwn", "text": "Hi Team :wave:"},
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
    [
        thread_ts,
        user_who_requested,
        reported_at,
        user_input,
        selected_user,
        channel_id,
        response_ts,
        ticket_category,
    ] = view["private_metadata"].split("@@")
    reflected_ts = ticket_manager.get_reflected_ts(thread_ts)
    ticket_key_for_user = f"{user_who_requested}@@{response_ts}@@{truncate_value(user_input)}@@{reported_at}@@{selected_user}@@{custom_category}@@{ticket_category}"

    try:
        updated_blocks = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "Hi Team :wave:"},
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
                "text": {"type": "mrkdwn", "text": "Hi Team :wave:"},
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
def resolve_button(ack, body, client, logger):
    ack()
    try:
        user_id = body["user"]["id"]
        user_info = client.users_info(user=user_id)
        user_name = user_info["user"]["real_name"]
        channel_id = body["channel"]["id"]
        thread_ts = body["container"]["message_ts"]
        reflected_ts = ticket_manager.get_reflected_ts(thread_ts)
        elements = body["message"]["blocks"][4]["elements"]
        resolve_button_value = elements[0]["value"].split("@@")
        category_ticket = resolve_button_value[-1]
        timestamp_utc = datetime.utcnow()
        timestamp_jakarta = convert_utc_to_jakarta(timestamp_utc)
        reflected_cn = "C05Q52ZTQ3X"

        if category_ticket == "Piket":
            [
                reporter_piket,
                response_ts,
                timestamp,
                date,
                teacher_requested,
                teacher_replace,
                grade,
                slot_name,
                time_class,
                reason,
                direct_lead,
                stem_lead,
            ] = resolve_button_value[:-1]
            ticket_manager.update_ticket_status(thread_ts, "assigned")
            teacher_replace_state = (
                f"<@{teacher_replace}>"
                if teacher_replace != "No Mentor"
                and teacher_replace != "I need help finding a replacement"
                else f"`{teacher_replace}`"
            )
            piket_message = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"Hi @tim_ajar\nWe've got a request from <@{teacher_requested}> with detail as below:",
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Class Date:*\n`{date}`"},
                        {
                            "type": "mrkdwn",
                            "text": f"*Time of Class:*\n`{time_class}`",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Teacher Requested:*\n<@{teacher_requested}>",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Teacher Replaces:*\n{teacher_replace_state}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Slot Name:*\n`{grade}-{slot_name}`",
                        },
                        {"type": "mrkdwn", "text": f"*Reason:*\n```{reason}```"},
                        {
                            "type": "mrkdwn",
                            "text": f"*Direct Lead:*\n<@{direct_lead}>",
                        },
                        {"type": "mrkdwn", "text": f"*STEM Lead:*\n<@{stem_lead}>"},
                    ],
                },
                {"type": "divider"},
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Piket Ticket Number:* piket.{thread_ts}",
                        }
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f":white_check_mark: <@{user_id}> approved the request",
                    },
                },
            ]
            response = client.chat_update(
                channel=channel_id, ts=thread_ts, text=None, blocks=piket_message
            )
            if response["ok"]:
                client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=thread_ts,
                    text=f"This request has been approved at `{timestamp_jakarta}` by <@{user_id}>",
                )

                client.chat_postMessage(
                    channel=reflected_cn,
                    blocks=piket_message,
                )

                client.chat_postMessage(
                    channel=reporter_piket,
                    thread_ts=response_ts,
                    text=f"<@{reporter_piket}> your piket request has been approved at `{timestamp_jakarta}`. Thank you :blob-bear-dance:",
                )

            sheet_manager.update_piket(
                f"piket.{thread_ts}",
                {
                    "status": "Approved",
                    "approved_by": user_name,
                    "approved_at": timestamp_utc,
                },
            )
        elif category_ticket == "Others":
            user_who_requested_ticket_id = resolve_button_value[0]
            user_message_ts = resolve_button_value[1]
            user_input = resolve_button_value[2]
            ticket_reported_at = resolve_button_value[3]
            selected_user = resolve_button_value[4]
            selected_category = resolve_button_value[5]
            category_ticket = resolve_button_value[6]
            response = client.chat_update(
                channel=channel_id,
                ts=thread_ts,
                text=None,
                blocks=[
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": "Hi Team :wave:"},
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
                        "text": {"type": "mrkdwn", "text": "Hi Team :wave:"},
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

                client.chat_update(
                    channel=reflected_cn, ts=reflected_ts, blocks=reflected_msg
                )

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
    except Exception as e:
        logger.error(f"Error handling modal submission: {str(e)}")


@app.action("reject_button")
def reject_button(ack, body, client):
    ack()
    trigger_id = body["trigger_id"]
    message_ts = body["container"]["message_ts"]
    channel_id = body["channel"]["id"]
    user_info = client.users_info(user=body["user"]["id"])
    user_name = user_info["user"]["real_name"]
    conditional_index = [6, 0] if len(body["message"]["blocks"]) > 5 else [4, 1]
    elements = body["message"]["blocks"][conditional_index[0]]["elements"]
    reject_button_value = elements[conditional_index[1]]["value"]
    ticket_category = "Piket" if conditional_index[0] == 4 else "Others"
    timestamp_utc = datetime.utcnow()
    sheet_manager.update_ticket(
        f"live-ops.{message_ts}",
        {"rejected_by": user_name, "rejected_at": timestamp_utc},
    )
    sheet_manager.update_piket(
        f"piket.{message_ts}",
        {"status": "Rejected", "rejected_by": user_name, "rejected_at": timestamp_utc},
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
            },
        ],
        "private_metadata": f"{channel_id}@@{message_ts}@@{reject_button_value}@@{ticket_category}",
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
        reflected_cn = "C05Q52ZTQ3X"
        [channel_id, message_ts, *reject_button_value] = view["private_metadata"].split(
            "@@"
        )
        reflected_ts = ticket_manager.get_reflected_ts(message_ts)
        reason = view["state"]["values"]["reject_reason"]["reason_input"]["value"]
        timestamp_utc = datetime.utcnow()
        timestamp_jakarta = convert_utc_to_jakarta(timestamp_utc)
        ticket_category = reject_button_value[-1]
        ticket_manager.update_ticket_status(message_ts, "assigned")

        if ticket_category == "Others":
            [
                user_requested_id,
                user_message_ts,
                user_input,
                ticket_reported_at,
            ] = reject_button_value[0:4]
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
                            "text": {"type": "mrkdwn", "text": "Hi Team :wave:"},
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
                        "text": {"type": "mrkdwn", "text": "Hi Team :wave:"},
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
                    text=f"We are sorry :smiling_face_with_tear: your issue was rejected due to `{reason}` at `{timestamp_jakarta}`. Let's put another question.",
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
        elif ticket_category == "Piket":
            [
                reporter_piket,
                response_ts,
                timestamp,
                date,
                teacher_requested,
                teacher_replace,
                grade,
                slot_name,
                time_class,
                reason_on_piket_replacement,
                direct_lead,
                stem_lead,
            ] = reject_button_value[:-2]
            general_rejection_text = f"<@{user_id}> has rejected the request at `{timestamp_jakarta}` due to: `{reason}`."
            response = client.chat_postMessage(
                channel=channel_id,
                thread_ts=message_ts,
                text=general_rejection_text,
            )
            teacher_replace_state = (
                f"<@{teacher_replace}>"
                if teacher_replace != "No Mentor"
                and teacher_replace != "I need help finding a replacement"
                else f"`{teacher_replace}`"
            )
            if response["ok"]:
                piket_message = [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"Hi @tim_ajar\nWe've got a request from <@{teacher_requested}> with detail as below:",
                        },
                    },
                    {
                        "type": "section",
                        "fields": [
                            {"type": "mrkdwn", "text": f"*Class Date:*\n`{date}`"},
                            {
                                "type": "mrkdwn",
                                "text": f"*Time of Class:*\n`{time_class}`",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Teacher Requested:*\n<@{teacher_requested}>",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Teacher Replaces:*\n{teacher_replace_state}",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Slot Name:*\n`{grade}-{slot_name}`",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Reason:*\n```{reason_on_piket_replacement}```",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Direct Lead:*\n<@{direct_lead}>",
                            },
                            {"type": "mrkdwn", "text": f"*STEM Lead:*\n<@{stem_lead}>"},
                        ],
                    },
                    {"type": "divider"},
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Piket Ticket Number:* piket.{message_ts}",
                            }
                        ],
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f":x: This request was rejected by <@{user_id}>. Please ignore this",
                        },
                    },
                ]
                client.chat_update(
                    channel=channel_id, ts=message_ts, text=None, blocks=piket_message
                )

                client.chat_postMessage(
                    channel=reporter_piket,
                    thread_ts=response_ts,
                    text=f"Uh-oh! :smiling_face_with_tear: Your request got the boot due to `{reason}` at `{timestamp_jakarta}`. But hey, no worries! You can always throw another piket request our way soon!",
                )

                ref_post = client.chat_postMessage(
                    channel=reflected_cn, blocks=piket_message
                )

                if ref_post["ok"]:
                    ref_ts = ref_post["ts"]
                    client.chat_postMessage(
                        channel=reflected_cn,
                        thread_ts=ref_ts,
                        text=general_rejection_text,
                    )

            else:
                logger.error("No value information available for this channel.")
    except Exception as e:
        logger.error(f"Error handling modal submission: {str(e)}")


# Start your app
if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
