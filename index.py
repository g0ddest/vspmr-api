from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from pymongo import MongoClient
from starlette.middleware.cors import CORSMiddleware
import uvicorn
import re

app = Starlette(debug=True)
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])
client = MongoClient('localhost', 27017)

event_db = client.vspmr.event
file_db = client.vspmr.file
init_db = client.vspmr.initiation
entry_db = client.vspmr.initiation_entry

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
        "committee_url": base_url + e["committee"],
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
