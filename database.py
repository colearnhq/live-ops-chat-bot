import gspread
import logging
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz


class SheetManager:
    def __init__(self, creds_dict, sheet_key):
        try:
            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive.file",
                "https://www.googleapis.com/auth/drive",
            ]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            self.chat_sheet = client.open_by_key(sheet_key).worksheet("chit_chat")
            self.ticket_sheet = client.open_by_key(sheet_key).worksheet("ticket")
            self.piket_sheet = client.open_by_key(sheet_key).worksheet("piket")
        except Exception as e:
            logging.error(f"Failed to initialize SheetManager: {str(e)}")

    def convert_to_local_time(self, timestamp_utc):
        utc = pytz.utc
        local_tz = pytz.timezone("Asia/Jakarta")
        timestamp_utc = utc.localize(timestamp_utc)
        timestamp_local = timestamp_utc.astimezone(local_tz)
        return timestamp_local.strftime("%Y-%m-%d %H:%M:%S")

    def log_ticket(
        self,
        chat_timestamp,
        timestamp_utc,
        user_id,
        user_name,
        email,
        phone_number,
        text,
    ):
        try:
            timestamp_local = self.convert_to_local_time(timestamp_utc)
            data = [
                chat_timestamp,
                timestamp_local,
                user_id,
                user_name,
                email,
                phone_number,
                text,
            ]
            self.chat_sheet.append_row(data)
        except Exception as e:
            logging.error(f"Failed to log chat: {str(e)}")

    def init_piket_row(
        self,
        piket_id,
        teacher_requested,
        teacher_replaces,
        grade,
        slot_name,
        class_date,
        class_time,
        reason,
        direct_lead,
        stem_lead,
        timestamp_utc,
    ):
        try:
            timestamp_local = self.convert_to_local_time(timestamp_utc)
            data = [
                piket_id,
                timestamp_local,
                teacher_requested,
                teacher_replaces,
                grade,
                slot_name,
                class_date,
                class_time,
                reason,
                direct_lead,
                stem_lead,
            ]
            self.piket_sheet.append_row(data)
        except Exception as e:
            logging.error(f"Failed to initialize ticket row: {str(e)}")

    def init_ticket_row(self, ticket_id, user_id, user_name, user_input, timestamp_utc):
        try:
            timestamp_local = self.convert_to_local_time(timestamp_utc)
            data = [
                timestamp_local,
                ticket_id,
                user_id,
                user_name,
                user_input,
                "",
                "",
                "",
                "",
                "",
                "",
            ]
            self.ticket_sheet.append_row(data)
        except Exception as e:
            logging.error(f"Failed to initialize ticket row: {str(e)}")

    def update_ticket(self, ticket_id, updates):
        try:
            row = self.find_ticket_row(ticket_id)
            if row:
                for key, value in updates.items():
                    col = self.column_mappings[key]
                    if "at" in key and isinstance(value, datetime):
                        value = self.convert_to_local_time(value)
                    self.ticket_sheet.update_cell(row, col, value)
        except Exception as e:
            logging.error(f"Failed to update ticket: {str(e)}")

    def find_ticket_row(self, ticket_id):
        ticket_id_col = 2
        col_values = self.ticket_sheet.col_values(ticket_id_col)
        for i, val in enumerate(col_values):
            if val == ticket_id:
                return i + 1
        return None

    @property
    def column_mappings(self):
        return {
            "timestamp": 1,
            "ticket_ids": 2,
            "user_ids": 3,
            "user_names": 4,
            "user_issue": 5,
            "category_issue": 6,
            "handled_by": 7,
            "handled_at": 8,
            "resolved_by": 9,
            "resolved_at": 10,
            "rejected_by": 11,
            "rejected_at": 12,
            "handed_over_by": 13,
            "handed_over_at": 14,
            "assigned_by": 15,
        }

    def update_piket(self, piket_id, updates):
        try:
            row = self.find_piket_row(piket_id)
            if row:
                for key, value in updates.items():
                    col = self.piket_col_mapping[key]
                    if "at" in key and isinstance(value, datetime):
                        value = self.convert_to_local_time(value)
                    self.ticket_sheet.update_cell(row, col, value)
        except Exception as e:
            logging.error(f"Failed to update ticket: {str(e)}")

    def find_piket_row(self, piket_id):
        piket_id = 1
        col_values = self.ticket_sheet.col_values(piket_id)
        for i, val in enumerate(col_values):
            if val == piket_id:
                return i + 1
        return None

    @property
    def piket_col_mapping(self):
        return {
            "piket_id": 1,
            "timestamp": 2,
            "teacher_requested": 3,
            "teacher_replaces": 4,
            "grade": 5,
            "slot_name": 6,
            "class_date": 7,
            "class_time": 8,
            "reason": 9,
            "direct_lead": 10,
            "stem_lead": 11,
            "status": 12,
            "approved_by": 13,
            "approved_at": 14,
            "rejected_by": 15,
            "rejected_at": 16,
        }
