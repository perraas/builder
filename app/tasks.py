from celery import Celery
import docker
import logging
from sqlalchemy.orm import Session
from .models import SessionLocal, Process
import os

app = Celery('tasks')
app.config_from_object('celeryconfig')

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.task(name="app.tasks.build_and_start_container")
def build_and_start_container(image_name: str, container_name: str, script_type: str):
    try:
        client = docker.from_env()

        # Define the volume mount
        host_output_dir = "/home/toor/scrape-new/storage/util/output"
        container_output_dir = "/output"
        volumes = {host_output_dir: {"bind": container_output_dir, "mode": "rw"}}

        # Select script based on script_type
        if script_type == "bash":
            script_name = "script.sh"
        elif script_type == "python":
            script_name = "script.py"
        else:
            return f"Unsupported script type: {script_type}"

        # Ensure the script file exists
        script_path = f"./scripts/{script_name}"
        if not os.path.exists(script_path):
            return f"Script file {script_path} does not exist."

        # Use a Dockerfile template to create a Dockerfile
        with open("Dockerfile.template", "r") as template_file:
            dockerfile_content = template_file.read()
        dockerfile_content = dockerfile_content.replace("$SCRIPT_NAME", script_name)
        with open("Dockerfile", "w") as dockerfile_file:
            dockerfile_file.write(dockerfile_content)

        # Build the image
        logger.debug(f"Building image {image_name}")
        image, logs = client.images.build(path='.', tag=image_name)
        
        # Log the build logs
        for log in logs:
            logger.debug(log)

        logger.debug(f"Image built: {image.id}")

        # Create and start the container with volume mounts
        logger.debug(f"Creating container {container_name}")
        container = client.containers.create(
            image=image.id, 
            name=container_name, 
            volumes=volumes
        )
        container.start()
        logger.debug("Container started")

        # Wait for the container to finish and get the logs
        container.wait()
        logs = container.logs().decode("utf-8")

        # Store the logs in the database
        db = next(get_db())
        process = db.query(Process).filter(Process.container_name == container_name).first()
        if process:
            process.result = logs
            db.commit()
            db.refresh(process)

        return f"Container {container_name} started successfully with image {image_name}. Logs: {logs}"
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return str(e)

@app.task(name="app.tasks.stop_container")
def stop_container(container_name: str):
    try:
        client = docker.from_env()
        container = client.containers.get(container_name)
        container.stop()
        return f"Container {container_name} stopped successfully."
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return str(e)

@app.task(name="app.tasks.remove_container")
def remove_container(container_name: str):
    try:
        client = docker.from_env()
        container = client.containers.get(container_name)
        container.remove()
        return f"Container {container_name} removed successfully."
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return str(e)

@app.task(name="app.tasks.reset_container")
def reset_container(image_name: str, container_name: str, script_type: str):
    try:
        stop_container(container_name)
        remove_container(container_name)
        build_and_start_container(image_name, container_name, script_type)
        return f"Container {container_name} reset successfully with environment {image_name}."
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return str(e)
