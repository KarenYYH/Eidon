import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse

from core.task_manager import task_manager

router = APIRouter()


@router.websocket("/{job_id}/ws")
async def job_websocket(websocket: WebSocket, job_id: str):
    await websocket.accept()
    job = task_manager.get_job(job_id)
    if not job:
        await websocket.close(code=4004)
        return

    queue: asyncio.Queue = asyncio.Queue(maxsize=20)
    task_manager.subscribe(job_id, queue)

    # Send current state immediately
    await websocket.send_json(job.model_dump(mode="json"))

    try:
        while True:
            try:
                data = await asyncio.wait_for(queue.get(), timeout=30)
                await websocket.send_json(data)
                # Close when terminal state
                if data.get("status") in ("completed", "failed", "cancelled"):
                    break
            except asyncio.TimeoutError:
                # Send ping to keep alive
                await websocket.send_json({"ping": True})
    except WebSocketDisconnect:
        pass
    finally:
        task_manager.unsubscribe(job_id, queue)


@router.get("/{job_id}/download")
async def download_output(job_id: str):
    job = task_manager.get_job(job_id)
    if not job or not job.output_file:
        raise HTTPException(404, "Output not ready")
    return FileResponse(job.output_file, filename=f"eidon_{job_id}.mp4", media_type="video/mp4")
