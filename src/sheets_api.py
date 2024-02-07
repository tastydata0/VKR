import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
import pandas as pd


def get_spreadsheet_data(spreadsheet_id, range_name):
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
    ]

    # Откройте файл JSON, который вы загрузили из учетной записи службы, и вставьте его сюда.
    service_account_json_credentials = json.load(open("token.json", "r"))

    credentials = service_account.Credentials.from_service_account_info(
        service_account_json_credentials, scopes=scopes
    )
    sheets_service = build("sheets", "v4", credentials=credentials)

    result = (
        sheets_service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=range_name)
        .execute()
    )

    values = result.get("values", [])

    if not values:
        print("No data found.")
        return None
    else:
        return values


def write_dataframe_to_sheet(spreadsheet_id, range_name, dataframe):
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
    ]

    # Откройте файл JSON, который вы загрузили из учетной записи службы, и вставьте его сюда.
    service_account_json_credentials = json.load(open("token.json", "r"))

    credentials = service_account.Credentials.from_service_account_info(
        service_account_json_credentials, scopes=scopes
    )
    sheets_service = build("sheets", "v4", credentials=credentials)

    data = [list(dataframe.columns)] + dataframe.values.tolist()
    body = {"values": data}

    result = (
        sheets_service.spreadsheets()
        .values()
        .update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            body=body,
            valueInputOption="RAW",
        )
        .execute()
    )

    print(f"{result.get('updatedCells')} cells updated.")


def convert_to_dataframe(data):
    if data is None:
        return None

    df = pd.DataFrame(data[1:], columns=data[0])
    return df


if __name__ == "__main__":
    # Используйте идентификатор таблицы и диапазон, чтобы получить данные.
    spreadsheet_id = "1bc3M_BHuYkFsdjMuVGaRwbUs77MuctwNbImILCrBnUI"
    range_name = "programs!A1:Z100"  # Замените на ваш реальный диапазон

    spreadsheet_data = get_spreadsheet_data(spreadsheet_id, range_name)
    df = convert_to_dataframe(spreadsheet_data)

    print("DataFrame:")
    print(df)

    # Пример использования:
    range_name = "testing!A1"  # Укажите нужный диапазон
    dataframe_to_write = pd.DataFrame(
        {"Column1": [1, 2, 3], "Column2": ["A", "B", "C"]}
    )

    write_dataframe_to_sheet(spreadsheet_id, range_name, df)

from typing import List
import uuid
import wget
import pandas as pd
import os
import dotenv
import os

dotenv.load_dotenv(".env")
sheet_id = os.getenv("SHEETS_ID")
programs_info_gid = os.getenv("SHEETS_PROGRAMS_INFO_GID")


def parse_sheet_to_dataframe(sheet_id: str, sheet_gid: str, skiprows=1):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={sheet_gid}"
    temp_file_name = f"/tmp/{uuid.uuid4()}.csv"
    wget.download(url, temp_file_name, None)

    df = pd.read_csv(temp_file_name, skiprows=skiprows)

    os.remove(temp_file_name)

    return df


def load_programs() -> List[dict]:
    programs = parse_sheet_to_dataframe(sheet_id, programs_info_gid, 0)
    return list(programs.to_dict(orient="index").values())
