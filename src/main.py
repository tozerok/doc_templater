import shutil
import time
from pathlib import Path
import urllib.parse
from loguru import logger
import pandas as pd

from docxtpl import DocxTemplate
from fastapi import FastAPI, File, Form, UploadFile, Request, status
from typing_extensions import Annotated
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
import os
from pydantic import BaseModel

app = FastAPI()


class MappingInfo(BaseModel):
    mapping: dict
    path_to_template: str
    path_to_data: str


app.mount("/static", StaticFiles(directory="/app/static"))
templates = Jinja2Templates(directory="/app/templates")

workdir = Path("/app/workdir")


@app.get("/", response_class=HTMLResponse)
async def loading(request: Request):
    return templates.TemplateResponse("loader.html", {"request": request})


@app.get("/templater", response_class=HTMLResponse)
async def mapper(request: Request,
                 path_to_template: str,
                 path_to_data: str
                 ):
    template_variables = list(DocxTemplate(path_to_template).get_undeclared_template_variables())
    template_variables.sort()
    logger.warning(template_variables)
    col_from_xlsx = pd.read_excel(path_to_data).columns

    return templates.TemplateResponse("mapping.html", {"request": request,
                                                       "template_variables": template_variables,
                                                       "col_from_xlsx": col_from_xlsx
                                                       })


@app.post("/upload", response_class=RedirectResponse)
async def upload(request: Request,
                 template_file: UploadFile = File(...),
                 data_file: UploadFile = File(...)):
    try:
        ts = str(int(time.time()))
        os.makedirs(Path(workdir, ts))
        path_to_template = Path(workdir, ts, template_file.filename)
        path_to_data = Path(workdir, ts, data_file.filename)
        with open(path_to_template, "wb") as buffer:
            shutil.copyfileobj(template_file.file, buffer)

        with open(path_to_data, "wb") as buffer:
            shutil.copyfileobj(data_file.file, buffer)

        return RedirectResponse(f"""/templater/?{urllib.parse.urlencode({
            "path_to_template": path_to_template,
            "path_to_data": path_to_data
        })}""",
                                status_code=status.HTTP_303_SEE_OTHER)

    except Exception as e:
        logger.exception("Uploading error", e, exc_info=True)
    return RedirectResponse("/templater")


@app.post("/process")
async def process(request: Request,
                  data: MappingInfo
                  ):
    mapping = data.mapping
    path_to_template = data.path_to_template
    path_to_data = data.path_to_data
    df = pd.read_excel(path_to_data)

    if not "file_name" in df.columns:
        df["file_name"] = [i for i in range(len(df))]

    ts = str(int(time.time()))
    output_dir = Path(workdir, ts)
    os.makedirs(output_dir, exist_ok=True)
    for i in range(len(df)):
        line = df.iloc[i]
        doc = DocxTemplate(path_to_template)
        context = {doc_val: df.iloc[i][xlsx_val] for doc_val, xlsx_val in mapping.items()}
        doc.render(context)
        doc.save( f'{output_dir}/{line["file_name"]}.docx')
    shutil.make_archive(ts, 'zip', output_dir)
    return FileResponse(f"{ts}.zip", filename=f"{ts}.zip")

if __name__ == "__main__":
    doc = DocxTemplate('../test.docx')
    doc.get_undeclared_template_variables()

    doc.render({"card_number": 21142354})
    doc.save('res.docx')
