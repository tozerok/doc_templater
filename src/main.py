import os
import shutil
import time
import urllib.parse
from pathlib import Path

import pandas as pd
from docxtpl import DocxTemplate
from fastapi import FastAPI, File, Request, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger
from pydantic import BaseModel

app = FastAPI()


class MappingInfo(BaseModel):
    """
        Описывает данные для заполнения файла по шаблону

        Attributes:
        mapping: dict
            Словарь, ключ - переменная шаблона, значение - значение столбца из файла наполнения
        path_to_template: str
            Путь к файлу шаблона
        path_to_data: str
            Путь к файлу с данными
    """
    mapping: dict
    path_to_template: str
    path_to_data: str


app.mount("/static", StaticFiles(directory="/app/static"))
templates = Jinja2Templates(directory="/app/templates")

workdir = Path("/app/workdir")
output_dir = Path("/app/output_dir")


@app.get("/", response_class=HTMLResponse)
async def loading(request: Request):
    """
        Страница загрузки
    Parameters
    ----------
    request: Request
        HTTP-запрос, полученный от клиента
    Returns
    -------
    starlette.templating._TemplateResponse
        Страница загрузки
    """
    return templates.TemplateResponse("loader.html", {"request": request})


@app.get("/templater", response_class=HTMLResponse)
async def mapper(request: Request,
                 path_to_template: str,
                 path_to_data: str
                 ):
    """
        Возвращает страницу с интерфейсом заполнения таблицы соответствия

    Parameters
    ----------
    request: Request
        HTTP-запрос, полученный от клиента
    path_to_template: str
        Путь к файлу с шаблоном
    path_to_data: str
        Путь к файлу с данными для заполнения

    Returns
    -------
    starlette.templating._TemplateResponse
        Страница интерфейса заполнения таблицы соответствия
    """
    template_variables = list(DocxTemplate(path_to_template).get_undeclared_template_variables())
    col_from_xlsx = list(pd.read_excel(path_to_data).columns)

    col_from_xlsx.sort()
    template_variables.sort()

    return templates.TemplateResponse("mapping.html", {"request": request,
                                                       "template_variables": template_variables,
                                                       "col_from_xlsx": col_from_xlsx
                                                       })


@app.post("/upload", response_class=RedirectResponse)
async def upload(template_file: UploadFile = File(...),
                 data_file: UploadFile = File(...)) -> RedirectResponse:
    """
        Запрос на загрузку файлов. После загрузки перенаправляет на страницу заполнения
     таблицы соответсвия

    Parameters
    ----------
    template_file: UploadFile
        Файл шаблоны
    data_file: UploadFile
        Файл с данными для заполнения

    Returns
    -------
    RedirectResponse
        Перенаправление на новую страницу
    """
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
    return RedirectResponse("/")


@app.post("/process")
async def process(data: MappingInfo) -> FileResponse:
    """
        Генерация файлов

    Parameters
    ----------
    data: MappingInfo
        Данные для генерации файлов

    Returns
    -------
    FileResponse
        zip-архив с генерированными файлами
    """
    mapping = data.mapping
    path_to_template = data.path_to_template
    path_to_data = data.path_to_data
    df = pd.read_excel(path_to_data)

    if not "file_name" in df.columns:
        df["file_name"] = [i for i in range(len(df))]

    ts = str(int(time.time()))
    output_path = Path(output_dir, ts)
    os.makedirs(output_path, exist_ok=True)
    for i in range(len(df)):
        line = df.iloc[i]
        doc = DocxTemplate(path_to_template)
        context = {doc_val: df.iloc[i][xlsx_val] for doc_val, xlsx_val in mapping.items()}
        doc.render(context)
        doc.save(f'{output_path}/{line["file_name"]}.docx')
    shutil.make_archive(ts, 'zip', output_path)
    return FileResponse(f"{ts}.zip", filename=f"{ts}.zip")
