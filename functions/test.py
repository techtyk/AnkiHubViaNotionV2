from .my_helpers import extract_database_id
url = "https://www.notion.so/18012e5fa8e18079bf0dd16b345a32d6?v=18012e5fa8e1810dbaa2000c054aa957"
database_id = extract_database_id(url)
print(database_id)