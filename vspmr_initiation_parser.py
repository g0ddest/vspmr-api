import logging
import os
import time

import html2text
import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

session = requests.Session()

mongoHost = os.environ["DB_HOST"] if "DB_HOST" in os.environ else "localhost"
mongoPort = int(os.environ["DB_PORT"]) if "DB_PORT" in os.environ else 27017
client = MongoClient(mongoHost, mongoPort)
db = client.vspmr
entry_db = client.vspmr.initiation_entry

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36'}

base_url = os.environ["VS_HOST"] if "VS_HOST" in os.environ else "https://vspmr.org"
last_conv = {
    'url': 'viii-soziv',
    'name': 'VIII'
}


def get_page_text(text):
    soup = BeautifulSoup(text, 'html.parser')

    entry_content = soup.find("div", {"class": "entry-content"})
    # Text is now in div.p after block_50
    block_50 = entry_content.find("div", {"class": "block_50"})
    found = block_50.find_next_sibling("div", {"class": "p"}) if block_50 else entry_content.find("div", {"class": "p"}, recursive=False)

    # File link is in col-2 inside block_50
    file_info = None
    if block_50:
        col_2 = block_50.find("div", {"class": "col-2"})
        if col_2:
            file_link = col_2.find("div", {"class": "p"})
            if file_link:
                url = file_link.find("a")
                if url and url.get("href") and url.get("href").startswith("/file"):
                    file_info = {
                        "name": ' '.join([m for m in url.stripped_strings]),
                        "url": url.get("href")
                    }

    return {
        "text": html2text.html2text(str(found).strip("\n")) if found else "",
        "file": file_info
    }


def get_note_text(url):
    return get_page_text(fetch(url))

def fetch(url):
    i = 1
    while True:
        logging.info("try = " + str(i))
        note = session.get(base_url + url, headers=headers)
        text = note.text
        time.sleep(12)
        if text != "ANTIDDOS":
            break
        logging.warning("faced ddos protection, waiting 10 seconds")
        i = i + 1
        if i > 10:
            logging.error("too many attempts, stopping")
            raise Exception("too many attempts")
    return text


def get_initiation_info(url):
    time.sleep(1)
    logging.info("getting initiation info: " + url)
    response = fetch(url)
    soup = BeautifulSoup(response, 'html.parser')

    page_text = get_page_text(response)

    info = {
        "text": page_text["text"],
        "files": []
    }

    if page_text["file"]:
        info["files"].append(page_text["file"])

    # meta
    block_50 = soup.find("div", {"class": "block_50"})
    if block_50:
        col_1 = block_50.find("div", {"class": "col-1"})
        if col_1:
            for meta_row in col_1.find_all("div", {"class": "p"}):
                meta_text = ' '.join([m for m in meta_row.stripped_strings])
                if len(meta_row.find_all("a")) == 1 and meta_row.a["href"].startswith("/structure"):
                    info["committee"] = ' '.join([m for m in meta_row.a.stripped_strings])
                    info["committee_url"] = meta_row.a["href"]
                if meta_text.lower().startswith("автор"):
                    info["author"] = ' '.join([m for m in meta_row.b.stripped_strings])
                if len(meta_row.find_all("a")) == 1 and meta_row.a.get("href").startswith("?"):
                    logging.info("getting note for: " + url)
                    note_text = get_note_text(url + "?&note=" + meta_row.a["href"].split("=")[1])
                    info["note"] = note_text["text"]
                    if note_text["file"]:
                        info["files"].append(note_text["file"])

        # files
        col_2 = block_50.find("div", {"class": "col-2"})
        if col_2:
            for file in col_2.find_all("a"):
                info["files"].append({
                    "name": ' '.join([m for m in file.stripped_strings]),
                    "url": file.get("href")
                })

    return info


def get_initiations(page):
    ret = {}
    response = fetch("/legislation/bills/" + last_conv["url"] + "/?page=" + str(page))
    soup = BeautifulSoup(response, 'html.parser')

    for row in soup.find("div", {"class": "p"}).find_all("tr"):
        elems = row.find_all("td")
        if len(elems) == 2:
            initiation = {
                "number": ' '.join([m for m in elems[0].stripped_strings]),
                "conv": last_conv["name"],
                "name": ' '.join([m for m in elems[1].a.stripped_strings]),
                "url": elems[1].a["href"],
                # "date": ' '.join([m for m in elems[2].stripped_strings])
                "date": ""
            }

            if entry_db.count_documents({
                "url": elems[1].a["href"],
                "number": initiation["number"],
                "conv": initiation["conv"]}) == 0:
                entry_db.insert_one({**initiation, **get_initiation_info(elems[1].a["href"])})
            else:
                ret['found_record'] = True

    pages = soup.find_all("div", {"class": "nav-links"})

    if len(pages) > 0:
        maxpage = pages[0].find_all("a", string='»')
    else:
        ret['maxurl'] = 1
        return ret
    if len(maxpage) == 1:
        ret['maxurl'] = maxpage[0]['href'].replace('?page=', '')

    return ret

def parse():
    page = 1
    maxpage = 7
    while page <= maxpage:
        logging.info("page " + str(page) + " / " + str(maxpage))
        result = get_initiations(page)
        if 'found_record' in result:
            break
        if 'maxurl' in result:
            maxpage = int(result["maxurl"])
        page += 1


parse()