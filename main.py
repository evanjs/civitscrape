import requests
import dotenv
from os import environ

base_url = "https://civitai.com"

payload = {}
headers = {}
names = [
    '__Host-next-auth.csrf-token',
    '__Secure-civitai-token',
    '__Secure-next-auth.callback-url',
    '__Secure-next-auth.session-token',
    'cf_clearance',
    'f_period=Day'
    'mantine-color-scheme'
]


def get_model(model_id: int) -> str:
    url = f'{base_url}/models/{model_id}'
    response = requests.request("GET", url, headers=headers, data=payload)
    return response.text


def load_env():
    dotenv.load_dotenv()
    for name in names:
        value = environ.get(name)
        headers[name] = value
        print(f'Header for {name} set to {value}')


def main():
    load_env()
    thing = get_model(7914)
    print(thing)


if '__main__' in __name__:
    main()
