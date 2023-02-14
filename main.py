import argparse
import os.path
from xml.etree import ElementTree
import pathlib

import regex_spm
import requests
import dotenv
from os import environ

from bs4 import BeautifulSoup
from lxml import etree
from tqdm import tqdm

base_url = "https://civitai.com"

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
    model_id: int = 0
    model_name: str = ''
    webpage: str | BeautifulSoup = ''
    primary_download_url: str = ''
    primary_download_id: int | None
    file_id_override: int | None = None

    def __str__(self) -> str:
        return f'{self.model_name} [{self.model_id}] — {self.model_type}'


def get_download_filename(response: requests.Response) -> str:
    content_disposition = response.headers.get('Content-Disposition').split("filename=")[1]
    return content_disposition


def update_auth(response: requests.Response):
    cookies.update(response.cookies)


class Civit:
    tree: ElementTree = ElementTree.fromstring('<html></html>')
    download_xpath = '//*[@id="__next"]/div/div/main/div/div[2]/div[1]/div/div[1]/div[1]/div[1]/a'
    sd_fallback_directory: pathlib.Path
    sd_base_directory: pathlib.Path
    header_xpath = '//h1/text()'
    model_type_xpath = '//*[@id="mantine-r35-dropdown"]/div[1]/div[4]/div[5]/label//text()'
    model_primary_download_selector = '.mantine-Stack-root .mantine-UnstyledButton-root.mantine-Button-root'
    model: Model = Model()

    def __init__(self):
        self.load_env()
        self.sd_base_directory = \
            self.sd_base_directory if self.sd_base_directory is not None else self.sd_fallback_directory

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

    # TODO: Better handle NSFW pages if not logged in
    #  If not logged in, NSFW pages will not have any scrapable content
    #  This should be made more obvious to the user,
    #  and the scraping should exit early as soon as this can be determined
    def update_primary_download(self):
        if self.model.file_id_override is not None:
            self.model.primary_download_id = self.model.file_id_override
            self.model.primary_download_url = f'https://civitai/api/download/models/{self.model.file_id_override}'
        else:
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
        sd_base_dir_var = environ.get('sd_base_directory')
        if sd_base_dir_var is not None:
            print(f'Found SD directory: {sd_base_dir_var}')
            self.sd_base_directory = pathlib.Path(sd_base_dir_var)
        else:
            print(f'Failed to find base SD directory variable "sd_base_directory". Using fallback: {sd_base_dir_var}')

        sd_fallback_dir_var = environ.get('sd_fallback_directory')
        if sd_fallback_dir_var is not None:
            print(f'Found SD fallback directory: {sd_fallback_dir_var}')
            self.sd_fallback_directory = pathlib.Path(sd_fallback_dir_var)
        else:
            print(f'Failed to find SD fallback directory variable "sd_fallback_dir". Using downloads directory...')
            self.sd_fallback_directory = pathlib.Path(os.path.join(pathlib.Path.home(), "Downloads"))

        dotenv.load_dotenv(dotenv_path='.cookies.env')
        for name in names:
            value = environ.get(name)
            cookies[name] = value

    def init_dir(self):
        if not self.sd_fallback_directory.exists():
            self.sd_fallback_directory.mkdir(parents=True)

    def get_model_download_directory(self, model: Model):
        next_path: pathlib.Path | None = None
        print(f'Attempting to parse model type {model.model_type}')
        r_match = regex_spm.fullmatch_in(model.model_type)
        match r_match:
            case r"LORA":
                next_path = pathlib.Path('models/Lora')
            case r"Textual Inversion":
                next_path = pathlib.Path('embeddings')
            case r"\s*Checkpoint.*":
                next_path = pathlib.Path('models/Stable-diffusion')
            case r'Hypernetwork':
                next_path = pathlib.Path('models/hypernetworks')
            case r"Aesthetic Gradient":
                next_path = pathlib.Path('models/aesthetic_embeddings')
            case _:
                print(f"Unhandled model type: {model.model_type}. I don't know where to download this...")
                pass
        pass
        if next_path is not None:
            print(f'Found path "{next_path}"')
            final_path = self.sd_base_directory.joinpath(next_path)
            print(f'Using directory "{final_path}" for download')
        else:
            print(f'Failed to find path "{next_path}" under "{self.sd_base_directory}". Falling back to base directory')
            final_path = self.sd_base_directory

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
            model.already_exists = True
            print(f'{fname} already exists! Not downloading... ...')
            return
        else:
            print(f'Touched file destination {fname}')
            final_download_path.touch()
        mess = f"Final path {fname} does not exist!"
        assert final_download_path.exists(), mess
        leng = int(response.headers.get('content-length', 0))
        units = 1024
        print(f"Attempting to download {model.model_type} model {model.model_name} ({model.model_id})")

        # TODO: investigate temporary download approach
        #  This would involve downloading to a temporary file, then later moving the completed file to a final path
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

        # TODO: investigate using basic logging rather than prints
        # print(f'Successfully downloaded model {model.primary_download_id} to temporary file {temp_filename}')
        print(
            f'Successfully downloaded "{model.model_type}" model "{model.model_name}" ({model.primary_download_id}) to "{final_download_path}"')
        # print(f'Attempting to move temporary file "{tempfile}" to "{final_download_path}" ...')
        # shutil.move(file, final_download_path)

    def update_model_details(self, model_id):
        self.model.model_id = model_id
        self.update_model(model_id)
        self.update_title()
        self.update_model_type()
        self.update_primary_download()

    def clear_details(self):
        self.model.__init__()
        self.tree = None


ids = []


def read_ids(file_name):
    with open(file_name, 'rb') as f:
        lines = [int(l.strip()) for l in f.readlines()]
        ids.extend(lines)
    pass


# TODO: handle pages with multiple downloadable files.
#  Do we ask the user? Do we support multi-selection for the response?
def download_multiple():
    c = Civit()
    print('Processing multiple downloads...')
    done_first = False
    for i in ids:
        print(f"Getting model {i} ...")
        if not done_first and c.model.model_id is not None:
            c.clear_details()
        mess = f"{i} is not a valid number!"
        assert i is not None, mess
        c.update_model_details(i)
        c.download_model()
        done_first = True
    pass


def download_single(file_id, file_id_override):
    c = Civit()
    c.model.file_id_override = file_id_override
    c.update_model_details(file_id)
    c.download_model()
    pass


def main():
    parser = argparse.ArgumentParser(prog='CivitAI Scraper')
    parser.add_argument("-i", "--id", type=int, nargs='*')
    parser.add_argument("-f", "--file")
    parser.add_argument("-o", "--override")
    res = parser.parse_args()
    override = res.override
    file_ids: list = res.id or []
    file_name = res.file
    print(f'File IDs: {file_ids}')
    print(f'File Name: {file_name}')
    print(f'length of file_ids: {len(file_ids)}')
    print(f'file_name is not None: {file_name is not None}')
    assert not (len(file_ids) == 0 and (file_name is None)), 'Please provide one or more file IDs or a file ID name!'
    if override is not None:
        print(f'Override: {override}')
        ids.extend(file_ids)
        print(f'ids: {ids}')
        download_single(ids[0], file_id_override=override)
    if file_ids is not None:
        ids.extend(file_ids)
        print(f'ids: {ids}')
        download_multiple()
        exit(0)
    elif file_name is not None:
        read_ids(file_name)
        print(f'ids: {ids}')
        download_multiple()


if '__main__' in __name__:
    main()
