from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, root_validator
from sqlalchemy.orm import Session
from .tasks import build_and_start_container, stop_container, remove_container, reset_container
from .models import Base, SessionLocal, Process, engine
import docker
import logging
app = FastAPI()


# Initialize logger
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class ContainerConfig(BaseModel):
    image_name: str
    container_name: str
    script_type: str

@app.post("/build-and-start/")
async def build_and_start(config: ContainerConfig, db: Session = Depends(get_db)):
    task = build_and_start_container.delay(config.image_name, config.container_name, config.script_type)
    process = Process(container_name=config.container_name, script_type=config.script_type)
    db.add(process)
    db.commit()
    db.refresh(process)
    return {"task_id": task.id, "process_id": process.id, "status": "Building and starting container"}

@app.get("/status/{task_id}")
async def get_status(task_id: str):
    from celery.result import AsyncResult
    result = AsyncResult(task_id)
    if result.state == 'PENDING':
        return {"status": "Pending"}
    elif result.state == 'SUCCESS':
        return {"status": "Success", "result": result.result}
    elif result.state == 'FAILURE':
        return {"status": "Failed", "result": str(result.result)}
    return {"status": result.state}

@app.get("/process/by_id/{process_id}/result")
async def get_process_result(process_id: int, db: Session = Depends(get_db)):
    process = db.query(Process).filter(Process.id == process_id).first()
    if process:
        return {"result": process.result}
    raise HTTPException(status_code=404, detail="Process not found")

@app.post("/stop/")
async def stop(config: ContainerConfig):
    task = stop_container.delay(config.container_name)
    return {"task_id": task.id, "status": "Stopping container"}

@app.post("/remove/")
async def remove(config: ContainerConfig):
    task = remove_container.delay(config.container_name)
    return {"task_id": task.id, "status": "Removing container"}

@app.post("/reset/")
async def reset(config: ContainerConfig):
    task = reset_container.delay(config.image_name, config.container_name, config.script_type)
    return {"task_id": task.id, "status": "Resetting container"}

@app.get("/containers/")
def list_containers():
    try:
        client = docker.from_env()
        containers = client.containers.list(all=True)  # Include all containers
        container_list = [
            {
                "id": container.id,
                "name": container.name,
                "image": container.image.tags,
                "status": container.status,
            }
            for container in containers
        ]
        logger.debug(f"Listed containers: {container_list}")
        return {"containers": container_list}
    except Exception as e:
        logger.error(f"Error listing containers: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
