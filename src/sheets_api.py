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
