import wget
import pandas as pd
import os

selected_fields = ['ФИО', 'Школа', 'Класс']

def parse_general_students_info(sheet_id: str, skiprows=1):
    url = f'https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv'
    # os.remove('/tmp/test.csv')
    wget.download(url, '/tmp/test.csv', None)

    df = pd.read_csv('/tmp/test.csv', skiprows=skiprows)

    print(df.to_string()) 
    print(df.columns)
    print(df.head(10))
    print(df.head(10)[selected_fields].values[6])


parse_general_students_info('1Xw3kxUi2e_LM9Tmn448BqJRbmyq8L4_zzCh8nm88bW8')