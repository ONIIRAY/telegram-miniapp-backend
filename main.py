from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path
import shutil
import json
import uuid
import aiohttp
import copy
import random

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

COMFY_URL = "http://127.0.0.1:8188"

INPUT_DIR = Path(r"E:\CUMFY_TG\ComfyUI-Easy-Install\ComfyUI\input")
OUTPUT_DIR = Path(r"E:\CUMFY_TG\ComfyUI-Easy-Install\ComfyUI\output")

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

WORKFLOW_SINGLE = BASE_DIR / "workflow_single.json"
WORKFLOW_DOUBLE = BASE_DIR / "workflow_double.json"

with open(WORKFLOW_SINGLE, "r", encoding="utf-8") as f:
    BASE_WF_SINGLE = json.load(f)

with open(WORKFLOW_DOUBLE, "r", encoding="utf-8") as f:
    BASE_WF_DOUBLE = json.load(f)


@app.post("/process")
async def process(
    images: list[UploadFile] = File(...),
    prompt: str = Form(...)
):
    filenames = []

    for img in images:
        filename = f"{uuid.uuid4().hex}.png"
        file_path = INPUT_DIR / filename

        with open(file_path, "wb") as f:
            shutil.copyfileobj(img.file, f)

        filenames.append(filename)

    # Автовыбор workflow
    if len(filenames) == 1:
        wf = copy.deepcopy(BASE_WF_SINGLE)
        expected_batch = 6

        wf["151"]["inputs"]["image"] = filenames[0]
        wf["107"]["inputs"]["text"] = prompt

    elif len(filenames) == 2:
        wf = copy.deepcopy(BASE_WF_DOUBLE)
        expected_batch = 3

        wf["151"]["inputs"]["image"] = filenames[0]
        wf["121"]["inputs"]["image"] = filenames[1]
        wf["107"]["inputs"]["text"] = prompt

    else:
        return {
            "success": False,
            "error": "Only 1 or 2 images supported"
        }


    random_seed = random.randint(1, 999999999999999)
    wf["133"]["inputs"]["seed"] = random_seed

    print("SEED:", random_seed)

    async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{COMFY_URL}/prompt",
                json={
                    "prompt": wf,
                    "client_id": str(uuid.uuid4())
                }
            ) as resp:
                data = await resp.json()
                prompt_id = data["prompt_id"]

                print("PROMPT ID:", prompt_id)

    return {
            "success": True,
            "prompt_id": prompt_id,
            "expected_batch": expected_batch
        }


@app.get("/result/{prompt_id}")
async def get_result(prompt_id: str):
    history_url = f"{COMFY_URL}/history/{prompt_id}"

    async with aiohttp.ClientSession() as session:
        async with session.get(history_url) as resp:
            data = await resp.json()

    if prompt_id not in data:
        return {"status": "processing"}

    outputs = data[prompt_id]["outputs"]

    save_images = []

    for node_id, node_data in outputs.items():
        images = node_data.get("images", [])

        if images:
            save_images = images
            break

    if save_images:
        return {
            "status": "done",
            "images": [img["filename"] for img in save_images]
        }

    return {"status": "processing"}

@app.get("/file/{filename}")
async def get_file(filename: str):
    return FileResponse(OUTPUT_DIR / filename)
