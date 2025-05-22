import os
from slack_bolt import Ack, Respond
from slack_sdk import WebClient
from datetime import datetime
import logging
import uuid
from slack_sdk.errors import SlackApiError


def register_dataops_commands(app, sheet_manager, channel_config):
    @app.command("/dataopsdev")
    def submit_a_project(ack, body, client):
        ack()
        trigger_id = body["trigger_id"]
        modal_blocks = [
            {
                "type": "input",
                "block_id": "project_title_block",
                "label": {"type": "plain_text", "text": "Judul Pengajuan*"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "project_title_action",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Contoh: Analisis Data Q3 2024",
                    },
                },
                "hint": {"type": "plain_text", "text": "Maksimal 50 karakter."},
            },
            {
                "type": "input",
                "block_id": "direct_lead_block",
                "label": {"type": "plain_text", "text": "Direct Lead*"},
                "element": {
                    "type": "users_select",
                    "action_id": "direct_lead_action",
                    "placeholder": {"type": "plain_text", "text": "Pilih atasan Anda"},
                },
                "hint": {
                    "type": "plain_text",
                    "text": "Orang yang perlu menyetujui/mengetahui.",
                },
            },
            {
                "type": "input",
                "block_id": "start_date_block",
                "label": {"type": "plain_text", "text": "Estimasi Mulai*"},
                "element": {
                    "type": "datepicker",
                    "action_id": "start_date_action",
                    "placeholder": {"type": "plain_text", "text": "Pilih tanggal"},
                },
            },
            {
                "type": "input",
                "block_id": "end_date_block",
                "label": {"type": "plain_text", "text": "Estimasi Selesai*"},
                "element": {
                    "type": "datepicker",
                    "action_id": "end_date_action",
                    "placeholder": {"type": "plain_text", "text": "Pilih tanggal"},
                },
            },
            {
                "type": "input",
                "block_id": "description_block",
                "label": {"type": "plain_text", "text": "Deskripsi Lengkap*"},
                "element": {
                    "type": "plain_text_input",
                    "multiline": True,
                    "action_id": "description_action",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Jelaskan latar belakang, tujuan, dan kebutuhan spesifik.",
                    },
                },
            },
            {
                "type": "input",
                "block_id": "expected_output_block",
                "label": {"type": "plain_text", "text": "Ekspektasi Output*"},
                "element": {
                    "type": "plain_text_input",
                    "multiline": True,
                    "action_id": "expected_output_action",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Contoh: Dashboard Tableau, CSV clean data, dll.",
                    },
                },
            },
            {
                "type": "input",
                "block_id": "attachment_url_block",
                "label": {"type": "plain_text", "text": "Link Spreadsheet/Attachment"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "attachment_url_action",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "https://docs.google.com/...",
                    },
                },
                "hint": {
                    "type": "plain_text",
                    "text": "Opsional, tapi sangat disarankan.",
                },
                "optional": True,
            },
        ]

        modal = {
            "type": "modal",
            "callback_id": "dataops_submission",
            "title": {
                "type": "plain_text",
                "text": "Submit Your Project!",
            },
            "submit": {"type": "plain_text", "text": "Submit"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": modal_blocks,
        }

        try:
            client.views_open(trigger_id=trigger_id, view=modal)
        except SlackApiError as e:
            logging.error(
                f"Error updating modal: {str(e)} | Response: {e.response['error']}"
            )

    @app.view("dataops_submission")
    def handle_dataops_submission(
        ack: Ack, body: dict, client: WebClient, view: dict, logger: logging.Logger
    ):
        ack()
        user_id = body["user"]["id"]
        submission_time = datetime.now().isoformat()

        try:
            values = view["state"]["values"]
            project_data = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "timestamp": submission_time,
                "title": values["project_title_block"]["project_title_action"]["value"],
                "direct_lead": values["direct_lead_block"]["direct_lead_action"][
                    "selected_user"
                ],
                "start_date": values["start_date_block"]["start_date_action"][
                    "selected_date"
                ],
                "end_date": values["end_date_block"]["end_date_action"][
                    "selected_date"
                ],
                "description": values["description_block"]["description_action"][
                    "value"
                ],
                "expected_output": values["expected_output_block"][
                    "expected_output_action"
                ]["value"],
                "attachment_url": values["attachment_url_block"][
                    "attachment_url_action"
                ].get("value"),
                "status": "awaiting_approval",
            }

            sheet_manager.append_row("DataOps_Submissions", list(project_data.values()))

            send_approval_request(client, project_data, user_id)

            client.chat_postMessage(
                channel=user_id,
                text=f"✅ Permohonan DataOps Anda *'{project_data['title']}'* telah diajukan. Menunggu persetujuan.",
            )

        except Exception as e:
            logger.error(f"DataOps submission failed: {e}")
            client.chat_postMessage(
                channel=user_id,
                text="❌ Gagal memproses pengajuan DataOps. Silakan coba lagi atau hubungi support.",
            )

    def send_approval_request(client: WebClient, project_data: dict, submitter_id: str):
        """Send approval message with Accept/Reject buttons to approver"""
        approver_id = "D01HLN378QZ"

        try:
            response = client.chat_postMessage(
                channel=approver_id,
                text=f"🚀 Permohonan DataOps Baru membutuhkan persetujuan Anda",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Permohonan DataOps Baru*\n*Judul:* {project_data['title']}\n*Diajukan oleh:* <@{submitter_id}>\n*Direct Lead:* <@{project_data['direct_lead']}>",
                        },
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Deskripsi:*\n{project_data['description']}\n\n*Ekspektasi Output:*\n{project_data['expected_output']}",
                        },
                    },
                    {
                        "type": "actions",
                        "block_id": f"approval_buttons_{project_data['id']}",
                        "elements": [
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "Approve ✅"},
                                "style": "primary",
                                "action_id": "dataops_approve",
                                "value": project_data["id"],
                            },
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "Reject ❌"},
                                "style": "danger",
                                "action_id": "dataops_reject",
                                "value": project_data["id"],
                            },
                        ],
                    },
                ],
            )

            sheet_manager.update_cell(
                "DataOps_Submissions",
                project_data["id"],
                "approval_message_ts",
                response["ts"],
            )

        except SlackApiError as e:
            logger.error(f"Failed to send approval request: {e.response['error']}")

    @app.action("dataops_approve")
    def handle_approval(ack, body, client, respond):
        ack()
        project_id = body["actions"][0]["value"]

        sheet_manager.update_cell(
            "DataOps_Submissions", project_id, "status", "approved"
        )

        project_data = sheet_manager.get_row("DataOps_Submissions", project_id)

        client.chat_postMessage(
            channel="C05Q52ZTQ3X",
            text=f"📢 Project DataOps Baru Disetujui!",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{project_data['title']}*\nDiajukan oleh: <@{project_data['user_id']}>\nDirect Lead: <@{project_data['direct_lead']}>\n\n*Deskripsi:*\n{project_data['description']}\n\n*Lampiran:* {project_data['attachment_url'] or '-'}",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Timeline:* {project_data['start_date']} hingga {project_data['end_date']}\n*Ekspektasi Output:* {project_data['expected_output']}",
                    },
                },
                {
                    "type": "actions",
                    "block_id": f"ticket_actions_{project_id}",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "🔄 Pending"},
                            "action_id": "ticket_pending",
                            "value": project_id,
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "✅ Resolve"},
                            "style": "primary",
                            "action_id": "ticket_resolve",
                            "value": project_id,
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "💬 Start Chat"},
                            "action_id": "ticket_chat",
                            "value": project_id,
                        },
                    ],
                },
            ],
        )

        client.chat_postMessage(
            channel="D03MT33NKDX",
            text=f"CC: Project DataOps '{project_data['title']}' telah disetujui dan dikirim ke tim.",
        )

        client.chat_postMessage(
            channel=project_data["direct_lead"],
            text=f"ℹ️ Staff Anda <@{project_data['user_id']}> telah mendapatkan persetujuan untuk project DataOps: *{project_data['title']}*",
        )

        client.chat_postMessage(
            channel=project_data["user_id"],
            text=f"🎉 Permohonan DataOps Anda *'{project_data['title']}'* telah disetujui! Tim akan segera menghubungi Anda.",
        )

        respond(
            replace_original=True,
            text=f"✅ Anda telah menyetujui project '{project_data['title']}'",
            blocks=[],
        )

    @app.action("dataops_reject")
    def handle_rejection(ack, body, client):
        ack()
        project_id = body["actions"][0]["value"]

        # Open rejection reason modal
        client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "rejection_reason_modal",
                "private_metadata": project_id,
                "title": {"type": "plain_text", "text": "Alasan Penolakan"},
                "submit": {"type": "plain_text", "text": "Submit"},
                "blocks": [
                    {
                        "type": "input",
                        "block_id": "rejection_reason_block",
                        "label": {
                            "type": "plain_text",
                            "text": "Berikan alasan penolakan",
                        },
                        "element": {
                            "type": "plain_text_input",
                            "multiline": True,
                            "action_id": "rejection_reason_action",
                        },
                    }
                ],
            },
        )

    @app.view("rejection_reason_modal")
    def handle_rejection_reason(ack, body, client, view):
        ack()
        project_id = view["private_metadata"]
        reason = view["state"]["values"]["rejection_reason_block"][
            "rejection_reason_action"
        ]["value"]

        sheet_manager.update_cell(
            "DataOps_Submissions", project_id, "status", "rejected"
        )
        sheet_manager.update_cell(
            "DataOps_Submissions", project_id, "rejection_reason", reason
        )

        project_data = sheet_manager.get_row("DataOps_Submissions", project_id)

        client.chat_postMessage(
            channel=project_data["user_id"],
            text=f"❌ Maaf, permohonan DataOps Anda *'{project_data['title']}'* ditolak.\n*Alasan:* {reason}",
        )

        client.chat_update(
            channel=body["container"]["channel_id"],
            ts=body["container"]["message_ts"],
            text=f"❌ Anda telah menolak project '{project_data['title']}'",
            blocks=[],
        )

    @app.action("ticket_pending")
    def handle_pending(ack, body, client, respond):
        ack()
        project_id = body["actions"][0]["value"]
        sheet_manager.update_cell(
            "DataOps_Submissions", project_id, "status", "pending"
        )
        respond(text=f"Ticket status updated to PENDING")

    @app.action("ticket_resolve")
    def handle_resolve(ack, body, client, respond):
        ack()
        project_id = body["actions"][0]["value"]
        sheet_manager.update_cell(
            "DataOps_Submissions", project_id, "status", "resolved"
        )
        respond(text=f"Ticket status updated to RESOLVED")

    @app.action("ticket_chat")
    def handle_start_chat(ack, body, client):
        ack()
        project_id = body["actions"][0]["value"]
        project_data = sheet_manager.get_row("DataOps_Submissions", project_id)

        client.conversations_open(
            users=f"{body['user']['id']},{project_data['user_id']}",
            text=f"Diskusi mengenai project DataOps: {project_data['title']}",
        )
