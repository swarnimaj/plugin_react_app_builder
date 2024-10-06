from typing import Union
import json
import os
import re
import asyncio
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from project_setup import *
from logger import logger
import playwright
from playwright.async_api import async_playwright

app = FastAPI()

origins = [
    "https://exp-chat.nikhil.com.np",
    "http://localhost",
    "http://localhost:8080",
    "https://exp-lobechat.nikhil.com.np",
    "http://localhost:3010"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define Pydantic models for request body
class FileContent(BaseModel):
    content: str

class SearchReplace(BaseModel):
    search: str
    replace: str
    multiple: bool

class RegexEdit(BaseModel):
    regex: str
    content: str
    multiple: bool

class NpmPackage(BaseModel):
    package_name: str
    version: Union[str, None] = None

class ProjectDetails(BaseModel):
    project_name: str
    filepath: Union[str, None] = None

# For project creation (to avoid query parameter)
class ProjectName(BaseModel):
    project_name: str

@app.get("/manifest")
async def read_manifest():
    file_name = "lobechat-manifest.json"
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, file_name)
    
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail=f"File '{file_name}' not found.")
    
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            content = json.load(file)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"JSON decode error: {str(e)}")
    except Exception as e:
        logger.error(f"Error reading manifest: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
    return content
    
@app.post("/create_react_project")
async def create_react_project(details: ProjectName):
    try:
        await create_project(details.project_name)
        return {"success": True, "message": f"Project '{details.project_name}' created successfully"}
    except Exception as e:
        logger.error(f"Error creating project: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")

@app.post("/create_or_replace_file")
async def create_file(details: ProjectDetails, file_content: FileContent):
    project_dir = get_project_directory(details.project_name)
    logger.info(f"Project path: {project_dir}")

    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail=f"Project '{details.project_name}' not found.")

    file_path = os.path.join(project_dir, details.filepath)

    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(file_content.content)
        return {"success": True, "message": f"File '{details.filepath}' created/replaced successfully."}
    except Exception as e:
        logger.error(f"Error creating/replacing file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/delete_file")
async def delete_file(details: ProjectDetails):
    project_dir = get_project_directory(details.project_name)

    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail=f"Project '{details.project_name}' not found.")

    file_path = os.path.join(project_dir, details.filepath)

    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            return {"success": True, "message": f"File '{details.filepath}' deleted successfully."}
        except Exception as e:
            logger.error(f"Error deleting file: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    else:
        raise HTTPException(status_code=404, detail=f"File '{details.filepath}' not found.")

@app.post("/get_file")
async def get_file(details: ProjectDetails):
    project_dir = get_project_directory(details.project_name)

    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail=f"Project '{details.project_name}' not found.")

    file_path = os.path.join(project_dir, details.filepath)

    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                content = file.read()
            return {"success": True, "content": content}
        except Exception as e:
            logger.error(f"Error reading file: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    else:
        raise HTTPException(status_code=404, detail=f"File '{details.filepath}' not found.")

@app.post("/list_files")
async def list_files(details: ProjectDetails):
    project_dir = get_project_directory(details.project_name)
    logger.info(f"Project path {project_dir}")
    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail=f"Project '{details.project_name}' not found.")
    
    directory_path = os.path.join(project_dir, details.filepath) if details.filepath else project_dir
    logger.info(f"Directory path {directory_path}")
    
    abs_directory_path = os.path.abspath(directory_path)
    if not abs_directory_path.startswith(os.path.abspath(project_dir)):
        raise HTTPException(status_code=403, detail="Access outside the project directory is forbidden.")
    
    logger.info(f"Directory path: {abs_directory_path}")
    
    if not os.path.isdir(abs_directory_path):
        raise HTTPException(status_code=404, detail=f"Directory '{details.filepath}' not found.")
    
    file_list = []
    try:
        for root, dirs, files in os.walk(abs_directory_path):
            if 'node_modules' in dirs:
                dirs.remove('node_modules')
            
            relative_root = os.path.relpath(root, project_dir)
            if relative_root.startswith('src/components/ui'):
                continue
            
            for file in files:
                relative_path = os.path.relpath(os.path.join(root, file), project_dir)
                file_list.append(relative_path)
                
        if not file_list:
            return {"success": True, "message": f"No files found in the directory '{details.filepath}'."}
        
        return {"success": True, "files": file_list}
    except Exception as e:
        logger.error(f"Error listing files: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/edit_file_regex")
async def edit_file_regex(details: ProjectDetails, regex_edit: RegexEdit):
    project_dir = get_project_directory(details.project_name)

    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail=f"Project '{details.project_name}' not found.")

    file_path = os.path.join(project_dir, details.filepath)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File '{details.filepath}' not found.")

    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()

        pattern = re.compile(regex_edit.regex)
        
        if regex_edit.multiple:
            new_content = re.sub(pattern, regex_edit.content, content)
        else:
            new_content = re.sub(pattern, regex_edit.content, content, count=1)

        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(new_content)

        return {"success": True, "message": f"File '{details.filepath}' updated successfully."}
    except re.error as e:
        raise HTTPException(status_code=400, detail=f"Invalid regex: {str(e)}")
    except Exception as e:
        logger.error(f"Error editing file with regex: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search_replace_file")
async def search_replace_file(project_name: str, filepath: str, search_replace: SearchReplace):
    project_dir = get_project_directory(project_name)

    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found.")

    file_path = os.path.join(project_dir, filepath)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File '{filepath}' not found.")

    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        if search_replace.multiple:
            new_content = content.replace(search_replace.search, search_replace.replace)
        else:
            new_content = content.replace(search_replace.search, search_replace.replace, 1)

        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(new_content)

        return {"success": True, "message": f"File '{filepath}' updated successfully."}
    except Exception as e:
        logger.error(f"Error searching and replacing in file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/install_npm_package")
async def install_npm_package(project_name: str, npm_package: NpmPackage):
    project_dir = get_project_directory(project_name)

    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found.")
    
    command = f"npm install {npm_package.package_name}" if npm_package.version is None else f"npm install {npm_package.package_name}@{npm_package.version}"
    
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            cwd=project_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            return {"success": True, "message": f"Package '{npm_package.package_name}' installed successfully."}
        else:
            error_message = "STDOUT:\n" + stdout.decode() + "\nSTDERR::\n" + stderr.decode()
            raise HTTPException(status_code=500, detail=f"Error installing package: {error_message}")
    except Exception as e:
        logger.error(f"Error installing npm package: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/remove_npm_package")
async def remove_npm_package(project_name: str, package_name: str):
    project_dir = get_project_directory(project_name)

    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found.")
    
    try:
        process = await asyncio.create_subprocess_shell(
            f"npm uninstall {package_name}",
            cwd=project_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            return {"success": True, "message": f"Package '{package_name}' removed successfully."}
        else:
            error_message = "STDOUT:\n" + stdout.decode() + "\nSTDERR::\n" + stderr.decode()
            raise HTTPException(status_code=500, detail=f"Error removing package: {error_message}")
    except Exception as e:
        logger.error(f"Error removing npm package: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search_npm_package")
async def search_npm_package(project_name, package_name: str):
    project_dir = get_project_directory(project_name)
    
    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found.")
    
    try:
        process = await asyncio.create_subprocess_shell(
            f"npm search {package_name} --json",
            cwd=project_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            search_results = json.loads(stdout.decode())
            return {"success": True, "results": search_results}
        else:
            error_message = stderr.decode() if stderr else stdout.decode()
            raise HTTPException(status_code=500, detail=f"Error searching for package: {error_message}")
    except Exception as e:
        logger.error(f"Error searching npm package: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/build")
async def build(project_name: str):
    project_dir = get_project_directory(project_name)

    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found.")

    try:
        process = await asyncio.create_subprocess_shell(
            "npm run build",
            cwd=project_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            return {"success": True, "output": stdout.decode()}
        else:
            error_message = "STDOUT:\n" + stdout.decode() + "\nSTDERR::\n" + stderr.decode()
            raise HTTPException(status_code=process.returncode, detail=f"Error during build: {error_message}")
    except Exception as e:
        logger.error(f"Error building project: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/lint")
async def lint(project_name: str):
    project_dir = get_project_directory(project_name)

    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found.")

    try:
        process = await asyncio.create_subprocess_shell(
            "npm run lint",
            cwd=project_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            return {"success": True, "output": stdout.decode()}
        else:
            error_message = "STDOUT:\n" + stdout.decode() + "\nSTDERR::\n" + stderr.decode()
            return {"success": False, "output": stderr.decode()}
    except Exception as e:
        logger.error(f"Error linting project: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/screenshot")
async def screenshot(url: str = "/", background_tasks: BackgroundTasks = BackgroundTasks()):
    async def take_screenshot(url: str):
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url)
                screenshot_path = os.path.join("screenshots", f"screenshot_{int(time.time())}.png")
                os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
                await page.screenshot(path=screenshot_path)
                await browser.close()
                logger.info(f"Screenshot taken and saved to '{screenshot_path}'.")
                return screenshot_path
        except playwright.errors.TimeoutError:
            logger.error(f"Timeout error while taking screenshot of {url}")
            raise HTTPException(status_code=504, detail="Timeout while loading the page")
        except Exception as e:
            logger.error(f"Error taking screenshot: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error taking screenshot: {str(e)}")

    background_tasks.add_task(take_screenshot, url)
    return {"success": True, "message": "Screenshot task added to background tasks."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

