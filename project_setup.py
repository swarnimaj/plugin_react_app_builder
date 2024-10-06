import os
import zipfile
import tarfile
import asyncio
from logger import logger

script_path = os.path.dirname(os.path.abspath(__file__))
projects_directory = "projects"

def get_project_directory(project_name):
    # First, check if it's an absolute path
    if os.path.isabs(project_name):
        return project_name if os.path.isdir(project_name) else None
    
    # Check in the default projects directory
    default_path = os.path.join(script_path, projects_directory, project_name)
    if os.path.isdir(default_path):
        return default_path
    
    # Check if it's a relative path from the current working directory
    cwd_path = os.path.join(os.getcwd(), project_name)
    if os.path.isdir(cwd_path):
        return cwd_path
    
    # If not found, return None
    return None

async def create_project(project_name):
    destination_folder = os.path.join(script_path, projects_directory, project_name)
    logger.info(f"Destination folder of new project {destination_folder}")
    if not os.path.exists(destination_folder):
        logger.info(f"Creating folder {destination_folder}")
        os.makedirs(destination_folder, exist_ok=True)
    
    await deflate_file("project.tar.gz", destination_folder)

async def deflate_file(file_path, destination_folder):
    """
    Extracts the contents of a .zip or .tar.gz file into the destination folder.

    Args:
        file_path (str): Path to the zip/tar.gz file.
        destination_folder (str): Path to the folder where the contents should be extracted.
    """
    # Ensure the destination folder exists
    os.makedirs(destination_folder, exist_ok=True)

    # Check the file extension to determine the type of compressed file
    if file_path.endswith('.zip'):
        # Handle zip files
        await asyncio.to_thread(extract_zip, file_path, destination_folder)
        logger.info(f"Extracted {file_path} to {destination_folder}")

    elif file_path.endswith('.tar.gz') or file_path.endswith('.tgz'):
        # Handle tar.gz files
        await asyncio.to_thread(extract_tar, file_path, destination_folder)
        logger.info(f"Extracted {file_path} to {destination_folder}")

    else:
        logger.error("Unsupported file format. Only .zip and .tar.gz are supported.")

def extract_zip(file_path, destination_folder):
    with zipfile.ZipFile(file_path, 'r') as zip_ref:
        zip_ref.extractall(destination_folder)

def extract_tar(file_path, destination_folder):
    with tarfile.open(file_path, 'r:gz') as tar_ref:
        tar_ref.extractall(destination_folder)
        

