import gspread
import logging
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime


class SheetManager:
    def __init__(self, creds_file, sheet_key):
        try:
            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive.file",
                "https://www.googleapis.com/auth/drive",
            ]
            creds = ServiceAccountCredentials.from_json_keyfile_name(creds_file, scope)
            client = gspread.authorize(creds)
            self.chat_sheet = client.open_by_key(sheet_key).worksheet("chit_chat")
            self.ticket_sheet = client.open_by_key(sheet_key).worksheet("ticket")
        except Exception as e:
            logging.error(f"Failed to initialize SheetManager: {str(e)}")

    def log_ticket(
        self, chat_timestamp, timestamp, user_id, user_name, email, phone_number, text
    ):
        try:
            data = [
                chat_timestamp,
                timestamp,
                user_id,
                user_name,
                email,
                phone_number,
                text,
            ]
            self.chat_sheet.append_row(data)
        except Exception as e:
            logging.error(f"Failed to log chat: {str(e)}")

    def init_ticket_row(self, ticket_id, user_id, user_name, user_input, timestamp):
        try:
            data = [
                timestamp,
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
                    self.ticket_sheet.update_cell(row, col, value)
        except Exception as e:
            logging.error(f"Failed to update ticket: {str(e)}")

    def find_ticket_row(self, ticket_id):
        ticket_id_col = 2  # Assuming 'ticket_ids' is in the second column
        col_values = self.ticket_sheet.col_values(ticket_id_col)
        for i, val in enumerate(col_values):
            if val == ticket_id:
                return i + 1  # +1 because Sheets is 1-indexed
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
        }
