"""
MIT License

Copyright (c) 2025 Siddharth Ahuja
Copyright (c) 2025 for additions

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

This file is based on work by Siddharth Ahuja, with additional contributions
for Tripo MCP functionality.
"""

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP
from tripo3d import TaskStatus, TripoClient

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("TripoMCPServer")

FAILED_STATUSES = (
    TaskStatus.FAILED,
    TaskStatus.CANCELLED,
    TaskStatus.BANNED,
    TaskStatus.EXPIRED,
)

mcp = FastMCP(
    name="Tripo MCP",
    instructions=(
        "Generates 3D models with Tripo AI and saves them as files on disk. "
        "Start a task with create_3d_model_from_text or create_3d_model_from_image, poll "
        "get_task_status until it succeeds, then call download_task_model to save the model. "
        "The saved GLB file can be imported into any tool, for example Blender for further "
        "work or a game engine directly. The API key comes from the TRIPO_API_KEY "
        "environment variable."
    ),
)


def _client() -> TripoClient:
    # TripoClient reads TRIPO_API_KEY itself; this only gives a clearer error.
    if not os.environ.get("TRIPO_API_KEY"):
        raise ValueError(
            "TRIPO_API_KEY is not set. Set it as an environment variable for the process "
            "that starts this server (for example a Windows user environment variable), "
            "then restart the MCP client."
        )
    return TripoClient()


def _started(task_id: str, task) -> Dict[str, Any]:
    return {
        "task_id": task_id,
        "status": str(task.status),
        "progress": task.progress,
        "message": "Task created. 3D model generation usually takes 1-5 minutes.",
        "next_step": "Call get_task_status with this task_id until the status is SUCCESS, "
        "then call download_task_model.",
    }


@mcp.tool()
async def create_3d_model_from_text(
    describe_the_look_of_object: str, face_limit: Optional[int] = None
) -> Dict[str, Any]:
    """
    Start a Tripo task that generates a 3D model from a text description.

    The call returns at once with a task_id. Poll get_task_status with it until the
    status is SUCCESS, then save the model with download_task_model.

    Args:
        describe_the_look_of_object: A detailed description of the object to generate.
        face_limit: Optional maximum number of faces in the model.

    Returns:
        The task ID and its initial status.
    """
    async with _client() as client:
        task_id = await client.text_to_model(
            prompt=describe_the_look_of_object, face_limit=face_limit
        )
        return _started(task_id, await client.get_task(task_id))


@mcp.tool()
async def create_3d_model_from_image(
    image: str, face_limit: Optional[int] = None
) -> Dict[str, Any]:
    """
    Start a Tripo task that generates a 3D model from an image.

    The call returns at once with a task_id. Poll get_task_status with it until the
    status is SUCCESS, then save the model with download_task_model.

    Args:
        image: Local path or URL of the image.
        face_limit: Optional maximum number of faces in the model.

    Returns:
        The task ID and its initial status.
    """
    async with _client() as client:
        task_id = await client.image_to_model(image=image, face_limit=face_limit)
        return _started(task_id, await client.get_task(task_id))


@mcp.tool()
async def rig_model(
    model_task_id: str, spec: str = "unreal", rig_type: str = "biped", out_format: str = "glb"
) -> Dict[str, Any]:
    """
    Start a Tripo task that adds a skeleton and skin weights to a generated model.

    Works best on characters generated in a T-pose or A-pose. The call returns at once
    with a new task_id; poll get_task_status with it, then save the rigged model with
    download_task_model.

    Args:
        model_task_id: The task ID of a successful create_3d_model_* task.
        spec: Skeleton convention: "unreal" (Unreal Mannequin bone names), "mixamo",
            "unity", "vrm", "actorcore" or "tripo".
        rig_type: "biped", "quadruped", "hexapod", "octopod", "avian", "serpentine",
            "aquatic" or "others".
        out_format: "glb" or "fbx".

    Returns:
        The rigging task ID and its initial status.
    """
    async with _client() as client:
        task_id = await client.rig_model(
            original_model_task_id=model_task_id,
            # The unreal, unity and vrm specs need a v2.5+ rig model.
            model_version="v3.0-20260909",
            out_format=out_format,
            rig_type=rig_type,
            spec=spec,
        )
        return _started(task_id, await client.get_task(task_id))


@mcp.tool()
async def get_task_status(task_id: str) -> Dict[str, Any]:
    """
    Get the status of a Tripo generation task.

    Call this repeatedly until the status is SUCCESS (then call download_task_model)
    or one of FAILED, CANCELLED, BANNED or EXPIRED.

    Args:
        task_id: The task ID returned by create_3d_model_from_text or
            create_3d_model_from_image.

    Returns:
        The task status and progress, and the result URLs once it has succeeded.
    """
    async with _client() as client:
        task = await client.get_task(task_id)

    result = {"task_id": task_id, "status": str(task.status), "progress": task.progress}
    if task.status == TaskStatus.SUCCESS and task.output:
        result.update(
            {
                "model_url": task.output.pbr_model or task.output.model,
                "rendered_image_url": task.output.rendered_image,
                "next_step": "Call download_task_model with this task_id to save the model.",
            }
        )
    elif task.status == TaskStatus.SUCCESS:
        result["message"] = "Task succeeded but returned no model."
    elif task.status in FAILED_STATUSES:
        result["message"] = f"Task ended with status {task.status}."
    else:
        result["next_step"] = "Still running; call get_task_status again shortly."
    return result


@mcp.tool()
async def download_task_model(
    task_id: str, output_dir: str = "", file_name: str = ""
) -> Dict[str, Any]:
    """
    Save the model of a successful Tripo task to disk.

    Args:
        task_id: The ID of a task whose status is SUCCESS.
        output_dir: Absolute folder to save into. Defaults to the TRIPO_OUTPUT_DIR
            environment variable. Created if it does not exist.
        file_name: File name without extension. Defaults to the task ID. Letters,
            digits, '-' and '_' only.

    Returns:
        The absolute path of the saved model file (usually .glb) and, if Tripo made one,
        of a rendered preview image saved next to it.
    """
    folder = output_dir or os.environ.get("TRIPO_OUTPUT_DIR", "")
    if not folder:
        raise ValueError("Pass output_dir or set the TRIPO_OUTPUT_DIR environment variable.")
    folder_path = Path(folder)
    if not folder_path.is_absolute():
        raise ValueError(f"output_dir must be an absolute path, got {folder!r}.")
    name = file_name or task_id
    if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
        raise ValueError(f"file_name may only contain letters, digits, '-' and '_', got {name!r}.")

    async with _client() as client:
        task = await client.get_task(task_id)
        if task.status != TaskStatus.SUCCESS or not task.output:
            raise ValueError(f"Task {task_id} is not finished (status {task.status}).")
        model_url = task.output.pbr_model or task.output.model
        if not model_url:
            raise ValueError(f"Task {task_id} succeeded but has no model to download.")

        folder_path.mkdir(parents=True, exist_ok=True)
        extension = Path(model_url.split("?")[0]).suffix or ".glb"
        model_path = folder_path / f"{name}{extension}"
        await client.download_file(model_url, model_path)
        result = {"task_id": task_id, "model_path": str(model_path)}

        if task.output.rendered_image:
            preview_ext = Path(task.output.rendered_image.split("?")[0]).suffix or ".jpg"
            preview_path = folder_path / f"{name}_preview{preview_ext}"
            await client.download_file(task.output.rendered_image, preview_path)
            result["preview_path"] = str(preview_path)

    logger.info("Saved model of task %s to %s", task_id, model_path)
    return result


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
