import html2text
import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient

client = MongoClient('localhost', 27017)
db = client.vspmr
entry_db = client.vspmr.initiation_entry

base_url = "http://www.vspmr.org"
last_conv = {
    'url': 'vii-soziv',
    'name': 'VII'
}


def get_page_text(text):
    soup = BeautifulSoup(text, 'html.parser')

    found = soup.find("div", {"class": "column_2"}).find("div", {"class": "block"}).findAll("div", {"class", "p"},
                                                                                            recursive=False)

    file_is_first = len(found) > 1 and found[0].a is not None
    file_idx = 0 if file_is_first else 1
    text_idx = 1 if file_is_first else 0

    if len(found) == 1:
        return {
            "text": html2text.html2text(str(found[text_idx]).strip("\n")),
            "file": None
        }
    else:
        return {
            "text": html2text.html2text(str(found[text_idx]).strip("\n")),
            "file": {
                "name": ' '.join([m for m in found[file_idx].stripped_strings]),
                "url": found[file_idx].find("a").get("href")
            }
        }


def get_note_text(url):
    return get_page_text(requests.get(base_url + url).text)


def get_initiation_info(url):
    response = requests.get(base_url + url)
    soup = BeautifulSoup(response.text, 'html.parser')

    page_text = get_page_text(response.text)

    info = {
        "text": page_text["text"],
        "files": []
    }

    if page_text["file"]:
        info["files"].append(page_text["file"])

    # meta
    for meta_row in soup.find("div", {"class": "column_2"}).find("div", {"class": "col-1"}).findAll("div",
                                                                                                    {"class": "p"}):
        meta_text = ' '.join([m for m in meta_row.stripped_strings])
        if len(meta_row.findAll("a")) == 1 and meta_row.a["href"].startswith("/structure"):
            info["committee"] = ' '.join([m for m in meta_row.a.stripped_strings])
            info["committee_url"] = meta_row.a["href"]
        if meta_text.lower().startswith("автор"):
            info["author"] = ' '.join([m for m in meta_row.b.stripped_strings])
        if len(meta_row.findAll("a")) == 1 and meta_row.a.get("href").startswith("?"):
            note_text = get_note_text(url + "?&note=" + meta_row.a["href"].split("=")[1])
            info["note"] = note_text["text"]
            if note_text["file"]:
                info["files"].append(note_text["file"])

    # files
    for file in soup.find("div", {"class": "column_2"}).find("div", {"class": "col-2"}).findAll("a"):
        info["files"].append({
            "name": ' '.join([m for m in file.stripped_strings]),
            "url": file.get("href")
        })

    return info


def get_initiations(page):
    ret = {}
    response = requests.get(base_url + "/legislation/bills/" + last_conv["url"] + "/?page=" + str(page))
    soup = BeautifulSoup(response.text, 'html.parser')

    for row in soup.find("div", {"class": "p"}).findAll("tr"):
        elems = row.findAll("td")
        if len(elems) == 3:
            initiation = {
                "number": ' '.join([m for m in elems[0].stripped_strings]),
                "conv": last_conv["name"],
                "name": ' '.join([m for m in elems[1].a.stripped_strings]),
                "url": elems[1].a["href"],
                "date": ' '.join([m for m in elems[2].stripped_strings])
            }

            if entry_db.count_documents({"url": elems[1].a["href"]}) == 0:
                entry_db.insert_one({**initiation, **get_initiation_info(elems[1].a["href"])})
            else:
                ret['found_record'] = True

    pages = soup.findAll("div", {"class": "pages"})

    if len(pages) > 0:
        maxpage = pages[0].findAll("a", text='»')
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
        print("page " + str(page) + " / " + str(maxpage))
        result = get_initiations(page)
        if 'found_record' in result:
            break
        if 'maxurl' in result:
            maxpage = int(result["maxurl"])
        page += 1


parse()