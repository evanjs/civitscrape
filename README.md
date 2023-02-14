# CivitAI Scraper

This is a utility designed to make downloading multiple resources from CivitAI less painful and easier to manage

Currently, this utility only downloads the latest/primary/topmost resource from a given model page

## Basic Usage

### File ID(s)

```shell
./main.py -i 1234 3456 4567 7689
```

This will download the latest model, which would normally be downloaded via the "Download Latest" button near the top of
the page.
___

### File containing file IDs

#### `ids.txt`

```txt
1234
8564
1924
4585
```

```shell
./main.py -f ids.txt
```

This will iterate the lines found in `ids.txt` and download the latest model from each of the specified resources
___

## Limitations

* This utility downloads the specified model(s) in a synchronous manner (one at a time)
* Only the latest model is downloaded

___

## Requirements

* To ensure this utility works with NSFW content, cookies must be saved to `.cookies.env`
    * `__Secure-civitai-token` should be the only cookie required to authenticate
        * e.g. `__Secure-civitai-token=<TOKEN_GOES_HERE>`
* The base directory for A1111 must be listed in `.env`
    * e.g. `sd_base_directory=G:\SD\automatic1111\stable-diffusion-webui`

___

## Notes

* The model type will be determined at runtime, and models will be downloaded to their respective folders
    * e.g. LORA -> `<sd_base_directory>/stable-diffusion-webui/models/Lora`