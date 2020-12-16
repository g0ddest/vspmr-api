import io

import markdown2
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.templating import Jinja2Templates
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from pymongo import MongoClient, DESCENDING
from pymongo.collation import Collation
from starlette.middleware.cors import CORSMiddleware
import uvicorn
import re
import datetime
import time
from PIL import Image, ImageDraw, ImageFont

client = MongoClient('localhost', 27017)

event_db = client.vspmr.event
file_db = client.vspmr.file
init_db = client.vspmr.initiation
entry_db = client.vspmr.initiation_entry
entries_per_page = 20

templates = Jinja2Templates(directory='templates')

last_conv = "VII"


async def homepage(request):
    conv = last_conv
    if "conv" in request.path_params:
        conv = request.path_params["conv"]

    page = int(request.query_params["page"]) if "page" in request.query_params else 0
    entries = [e for e in entry_db.find({"conv": conv}, limit=entries_per_page)
        .sort([('number', DESCENDING)])
        .collation(Collation('ru', numericOrdering=True))
        .skip(page * entries_per_page)]

    return templates.TemplateResponse('index.html',
                                      {'request': request, 'id': 1, 'entries': [entry for entry in entries],
                                       'show_pages': len(entries) > entries_per_page,
                                       'next': page + 1, 'prev': page - 1,
                                       'conv': conv})


async def item(request):
    entry_id = request.path_params["entry"]

    conv = last_conv

    if "conv" in request.path_params:
        conv = request.path_params["conv"]

    if "additional" in request.path_params:
        entry_id = "{0}/{1}".format(entry_id, request.path_params["additional"])

    e = entry_db.find({
        "number": entry_id,
        "conv": conv
    }).limit(1)

    try:
        e = e[0]
    except:
        return Response(status_code=404)

    inits = init_db.find({
        "number": re.sub("\(.+\)", "", e["number"]).strip(),
        "conv": conv
    })

    e['reads'] = []
    if e["date"] is not None and e["date"] != "":
        e['date_formatted'] = datetime.datetime.strptime(e["date"], '%d.%m.%Y').strftime('%Y-%m-%d')
    e['texthtml'] = markdown2.markdown(e['text'])

    for init in inits:
        file = file_db.find({"url": init["file_url"]}).limit(1)[0]
        event = event_db.find({"href": init["event_url"]}).limit(1)[0]
        e["reads"].append({
            "read": init['read'],
            "event_url": base_url + init["event_url"],
            "date": file["date"],
            "time": event["begin"],
            "timestamp": time.mktime(
                datetime.datetime.strptime(file["date"] + " " + event["begin"], "%d.%m.%Y %H.%M").timetuple())
        })

    e["reads"] = sorted(e["reads"], key=lambda item: item['timestamp'])
    e["reads"] = reversed(e["reads"])

    return templates.TemplateResponse('item.html',
                                      {'request': request, 'entry': e})


def save_pil_image_to_bytes(img):
    out = io.BytesIO()
    img.save(out, format='PNG')
    out.seek(0)
    return out


async def preview(request):
    entry_id = request.path_params["entry"]

    if "additional" in request.path_params:
        entry_id = "{0}/{1}".format(entry_id, request.path_params["additional"])

    e = entry_db.find({
        "number": entry_id,
        "conv": last_conv
    }).limit(1)

    try:
        e = e[0]
    except:
        return Response(status_code=404)

    img = Image.new('RGB', (2048, 1170), color='white')

    font = ImageFont.truetype("static/fonts/Golos_Text Medium/Golos_Text Medium.ttf", 120)
    fontHeader = ImageFont.truetype("static/fonts/Golos_Text Bold/Golos_Text Bold.ttf", 180)
    draw = ImageDraw.Draw(img)
    draw.text((200, 700), "Верховный Совет", (0, 0, 0), font=fontHeader)
    draw.text((200, 900), "Законопроект  {0}".format(e['number']), (0, 0, 0), font=font)

    return StreamingResponse(save_pil_image_to_bytes(img), media_type="image/png")


app = Starlette(debug=True, routes=[
    Route('/', endpoint=homepage),
    Route('/conv-{conv}', endpoint=homepage),
    Route('/entry/{entry}', endpoint=item),
    Route('/entry/conv-{conv}/{entry}', endpoint=item),
    Route('/preview/{entry}.png', endpoint=preview),
    Route('/entry/{entry}/{additional}', endpoint=item),
    Route('/preview/{entry}/{additional}.png', endpoint=preview),
    Mount('/static', StaticFiles(directory='static'), name='static')
])
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])

base_url = "http://www.vspmr.org"


@app.route('/list')
async def init_list(request):
    entries = entry_db.find({
        "conv": request.query_params["conv"]
    })

    response = []

    for e in entries:
        r = {
            "number": e["number"],
            "conv": e["conv"],
            "name": e["name"],
            "url": base_url + e["url"],
            "date": e["date"],
            "read_numbers": []
        }
        inits = init_db.find({
            "number": re.sub("\(.+\)", "", e["number"]).strip(),
            "conv": e["conv"]
        })

        for i in inits:
            if "read" in i and i["read"] not in r["read_numbers"]:
                r["read_numbers"].append(i["read"])

        response.append(r)

    return JSONResponse(response)


@app.route('/init')
async def init_info(request):
    e = entry_db.find({
        "number": request.query_params["number"],
        "conv": request.query_params["conv"]
    }).limit(1)

    try:
        e = e[0]
    except:
        return Response(status_code=404)

    entry = {
        "number": e["number"],
        "conv": e["conv"],
        "name": e["name"],
        "url": base_url + e["url"],
        "date": e["date"],
        "text": e["text"],
        "files": e["files"],
        "committee": e["committee"] if "committee" in e else None,
        "committee_url": (base_url + e["committee"]) if "committee" in e else None,
        "author": e["author"],
        "note": e["note"],
        "reads": []
    }

    inits = init_db.find({
        "number": re.sub("\(.+\)", "", request.query_params["number"]).strip(),
        "conv": request.query_params["conv"]
    })

    for init in inits:
        file = file_db.find({"url": init["file_url"]}).limit(1)[0]
        event = event_db.find({"href": init["event_url"]}).limit(1)[0]
        entry["reads"].append({
            "read": init['read'],
            "event_url": base_url + init["event_url"],
            "date": file["date"],
            "time": event["begin"]
        })

    return JSONResponse(entry)


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=9000)
