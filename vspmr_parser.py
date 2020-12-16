import subprocess
import re
import os
import requests
from bs4 import BeautifulSoup
import tempfile
from pymongo import MongoClient

client = MongoClient('localhost', 27017)
db = client.vspmr.day
event_db = client.vspmr.event
file_db = client.vspmr.file
init_db = client.vspmr.initiation
base_url = "http://www.vspmr.org"
os.chdir("lib")


def get_doc_text_with_err(file):
    proc = subprocess.Popen('./doctotext.sh ' + file, stdout=subprocess.PIPE, shell=True)
    (out, err) = proc.communicate()
    return {"out": out.decode("utf-8"), err: err}


def parse_day(event_url, file_url, content):
    parsed = [m.groupdict() for m in
              re.finditer("Электронный адрес:.+[IVX]+:(?P<type>.+)\/(?P<folder>.+)\/(?P<theme>.+)", content)]
    for parse in parsed:
        parse['event_url'] = event_url
        parse['file_url'] = file_url
        if parse['type'] == 'ИНИЦИАТИВА':
            cont = [m.groupdict() for m in
                    re.finditer("(?P<number>.+)\s+\((?P<conv>[IVX]+)\).+(?P<read>\d+)", parse['theme'])]
            if len(cont) == 1:
                parse['number'] = cont[0]['number']
                parse['conv'] = cont[0]['conv']
                parse['read'] = cont[0]['read']
                parse['number_form'] = parse['number'].replace(' ', '').replace('(', '').replace(')', '')

    if len(parsed) > 0:
        init_db.insert_many(parsed)


def parse_file_get_content(url, suffix):
    response = requests.get(base_url + url)
    temp = tempfile.NamedTemporaryFile(suffix=suffix)
    try:
        temp.write(response.content)
        return get_doc_text_with_err(temp.name)
    finally:
        temp.close()


def parse_event(url):
    date_string = ""
    response = requests.get(base_url + url)
    soup = BeautifulSoup(response.text, 'html.parser')
    cnt = soup.findAll("div", {"class": "big"})[0]
    date = cnt.findAll("div", {"class": "p"})
    if len(date) > 0:
        date_string = date[0].string

    for li in cnt.findAll("li"):
        if li.a:

            if file_db.count_documents({"url": li.a['href']}) == 0:

                content = parse_file_get_content(li.a['href'], '.' + li.string.split('.')[-1])

                file_db.insert_one({
                    "event_url": url,
                    "date": date_string,
                    "name": li.string,
                    "url": li.a['href'],
                    "content": content["out"] if "out" in content else None,
                    "error": content["err"] if "err" in content else None
                })

                if content["out"]:
                    parse_day(url, li.a['href'], content["out"])


def get_events(page):
    ret = {}
    response = requests.get(base_url + "/news/events/?page=" + str(page))
    soup = BeautifulSoup(response.text, 'html.parser')
    for calendar in soup.findAll("div", {"class": "calendar_b"}):
        link = calendar.parent.find("a")
        day = {
            "href": link['href'],
            "text": ''.join([m for m in link.stripped_strings]),
            "date": ' '.join([m for m in calendar.span.stripped_strings]),
            "begin": calendar.parent.p.b.string,
            "info": ' '.join([m for m in soup.findAll("div", {"class": "calendar_b"})[0].parent.p.stripped_strings])
        }

        if event_db.count_documents({"href": link['href']}) == 0:
            event_db.insert_one(day)
        else:
            ret['found_record'] = True

        parse_event(link['href'])

    pages = soup.findAll("div", {"class": "pages"})

    if len(pages) > 0:
        maxpage = pages[0].findAll("a", text='»')
    else:
        ret['maxurl'] = 1
        return ret
    if len(maxpage) == 1:
        ret['maxurl'] = maxpage[0]['href'].replace('?page=', '')

    return ret


def parser():
    page = 1
    maxpage = 110
    while page <= maxpage:
        print("page " + str(page) + " / " + str(maxpage))
        result = get_events(page)
        if 'found_record' in result:
            break
        if 'maxurl' in result:
            maxpage = int(result["maxurl"])
        page += 1


parser()
