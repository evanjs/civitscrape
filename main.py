import argparse
import os
import shutil
import tempfile
from xml.etree import ElementTree
import pathlib
import requests
import dotenv
from os import environ

from bs4 import BeautifulSoup
from lxml import etree
from tqdm import tqdm

base_url = "https://civitai.com"

# payload = {}
headers = {}
cookies = {}
names = [
    '__Host-next-auth.csrf-token',
    '__Secure-civitai-token',
    '__Secure-next-auth.callback-url',
    '__Secure-next-auth.session-token',
    'cf_clearance',
    'f_period',
    'mantine-color-scheme'
]


class Model:
    model_type: str = ''
    model_id: int = 0,
    model_name: str = '',
    webpage: str | BeautifulSoup = ''
    primary_download_url: str = '',
    primary_download_id: int | None

    def __str__(self) -> str:
        return f'{self.model_name} [{self.model_id}] — {self.model_type}'


def get_download_filename(response: requests.Response) -> str:
    content_disposition = response.headers.get('Content-Disposition').split("filename=")[1]
    return content_disposition


def update_auth(response: requests.Response):
    cookies.update(response.cookies)
    token = response.headers.get('__Secure-civitai-token')
    # headers['__Secure-civitai-token'] = token


class Civit:
    tree: ElementTree = ElementTree.fromstring('<html></html>')
    download_xpath = '//*[@id="__next"]/div/div/main/div/div[2]/div[1]/div/div[1]/div[1]/div[1]/a'
    fallback_sd_directory = pathlib.Path('G:/Downloads/stable-diffusion')
    base_sd_directory: pathlib.Path = fallback_sd_directory
    header_xpath = '//h1/text()'
    model_type_xpath = '//*[@id="mantine-r35-dropdown"]/div[1]/div[4]/div[5]/label//text()'
    model_primary_download_selector = '.mantine-Stack-root .mantine-UnstyledButton-root.mantine-Button-root'
    model: Model = Model()

    def __init__(self):
        self.load_env()

    def init_tree(self, soup: BeautifulSoup):
        self.tree: ElementTree = etree.HTML(str(soup))

    def update_title(self):
        self.model.model_name = self.tree.xpath(self.header_xpath)[0]

    def update_model(self, model_id: int):
        url = f'{base_url}/models/{model_id}'
        response = requests.get(url, cookies=cookies)
        update_auth(response)
        soup = BeautifulSoup(response.text, 'html.parser')
        self.model.webpage = soup
        self.init_tree(self.model.webpage)

    def update_primary_download(self):
        self.model.primary_download_url = f"{base_url}{self.model.webpage.select_one(self.model_primary_download_selector).get('href')}"
        self.model.primary_download_id = self.model.primary_download_url.split('/')[-1]

    def update_model_type(self):
        model_type_box = list(self.model.webpage.select_one('div.mantine-Stack-root div tbody > tr, td').children)
        model_type = model_type_box[1].text.strip()
        self.model.model_type = model_type

    def download_model_file(self) -> requests.Response:
        url = f'{base_url}/api/download/models/{self.model.primary_download_id}'
        response = requests.get(url, stream=True, cookies=cookies)
        update_auth(response)
        return response

    def load_env(self):
        dotenv.load_dotenv()
        sd_dir_var = environ.get('base_sd_directory')
        if sd_dir_var is not None:
            print(f'Found SD directory: {sd_dir_var}')
            self.base_sd_directory = pathlib.Path(sd_dir_var)
        else:
            print(f'Failed to find base SD directory variable "base_sd_directory". Using fallback: {sd_dir_var}')
        dotenv.load_dotenv(dotenv_path='.cookies.env')
        for name in names:
            value = environ.get(name)
            cookies[name] = value
            # headers[name] = value
            # print(f'Header for {name} set to {value}')

    def init_dir(self):
        if not self.fallback_sd_directory.exists():
            self.fallback_sd_directory.mkdir(parents=True)

    # def get_download_name(self):
    #     pass

    def get_model_download_directory(self, model: Model):
        next_path: pathlib.Path | None = None
        match model.model_type:
            case 'LORA':
                next_path = pathlib.Path('models/Lora')
            case 'Textual Inversion':
                next_path = pathlib.Path('embeddings')
            case 'Checkpoint':
                next_path = pathlib.Path('Stable-diffusion')
            case 'Hypernetwork':
                next_path = pathlib.Path('models/hypernetworks')
            case 'Aesthetic Gradient':
                next_path = pathlib.Path('models/aesthetic_embeddings')
        pass
        if next_path is not None:
            # print(f'Found path {next_path}')
            final_path = self.base_sd_directory.joinpath(next_path)
            # print(f'Using directory {final_path} for download')
        else:
            # print(f'Failed to find path {next_path} under {self.base_sd_directory}. Falling back to base directory')
            final_path = self.base_sd_directory

        return final_path

    def download_model(self):
        model = self.model
        download_path = self.get_model_download_directory(model)
        response = self.download_model_file()
        update_auth(response)

        filename = pathlib.Path(get_download_filename(response))
        final_download_path = download_path.joinpath(filename.__str__().replace('"', ''))
        fname = final_download_path.absolute().__str__()
        if final_download_path.exists():
            print(f'{fname} already exists! Exiting without downloading ...')
            exit(0)
        else:
            print(f'Touched file destination {fname}')
            final_download_path.touch()
        mess = f"Final path {fname} does not exist!"
        assert(final_download_path.exists(), mess)
        leng = int(response.headers.get('content-length', 0))
        units = 1024
        print(f"Attempting to download {model.model_type} model {model.model_name} ({model.model_id})")
        # tp = tempfile.TemporaryFile()
        with open(fname, 'wb') as file, tqdm(
                desc=fname,
                total=leng,
                unit='iB',
                unit_scale=True,
                unit_divisor=units
        ) as bar:
            for data in response.iter_content(chunk_size=units):
                size = file.write(data)
                bar.update(size)
        pass
        # print(f'Successfully downloaded model {model.primary_download_id} to temporary file {temp_filename}')
        print(f'Successfully downloaded {model.model_type} model {model.model_name} ({model.primary_download_id}) to {final_download_path}')
        # print(f'Attempting to move temporary file {tempfile} to {final_download_path} ...')
        # shutil.move(file, final_download_path)

    def update_model_details(self, model_id):
        self.model.model_id = model_id
        self.update_model(model_id)
        self.update_title()
        self.update_model_type()
        self.update_primary_download()


# Get main model page from ID (HTML)
#   Get type of model
#   Get id of model
#   Get name of model

def main():
    parser = argparse.ArgumentParser(prog = 'CivitAI Scraper')
    parser.add_argument('file_id', type=int)
    res = parser.parse_args()
    file_id = res.file_id
    assert(file_id is not None, 'File ID is required!')
    c = Civit()
    c.update_model_details(file_id)
    model = c.model
    c.download_model()
    print(model)


if '__main__' in __name__:
    main()
