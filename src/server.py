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

# Pinned rather than left to defaults: the SDK sends the legacy v2.5 model unless told
# otherwise, and Tripo moves the server default between releases.
MODEL_VERSION = "v3.1-20260211"
# The texture model that can remove lighting baked into an input image (delight).
TEXTURE_VERSION = "v3.5-20260815"

mcp = FastMCP(
    name="Tripo MCP",
    instructions=(
        "Generates 3D models with Tripo AI and saves them as files on disk. "
        "Start a task with create_3d_model_from_text or create_3d_model_from_image, poll "
        "get_task_status until it succeeds, then call download_task_model to save the model. "
        "To rig a character, call check_riggable first, then rig_model. "
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


def _started(task_id: str, task, settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    result = {
        "task_id": task_id,
        "status": str(task.status),
        "progress": task.progress,
        "message": "Task created. 3D model generation usually takes 1-5 minutes.",
        "next_step": "Call get_task_status with this task_id until the status is SUCCESS, "
        "then call download_task_model.",
    }
    if settings:
        result["settings"] = settings
    return result


def _generation_settings(
    model_version: str, face_limit: Optional[int], texture_quality: str,
    geometry_quality: str, pbr: bool, auto_size: bool, delight: bool, quad: bool,
    smart_low_poly: bool, model_seed: Optional[int], texture_seed: Optional[int],
) -> Dict[str, Any]:
    """The options both generation tools share, as SDK keyword arguments."""
    settings: Dict[str, Any] = {
        "model_version": model_version, "face_limit": face_limit,
        "texture_quality": texture_quality, "geometry_quality": geometry_quality,
        "pbr": pbr, "auto_size": auto_size, "quad": quad, "smart_low_poly": smart_low_poly,
        "model_seed": model_seed, "texture_seed": texture_seed,
    }
    if delight:
        settings.update(texture_version=TEXTURE_VERSION, delight=True)
    return settings


@mcp.tool()
async def create_3d_model_from_text(
    describe_the_look_of_object: str,
    negative_prompt: Optional[str] = None,
    model_version: str = MODEL_VERSION,
    face_limit: Optional[int] = None,
    texture_quality: str = "standard",
    geometry_quality: str = "standard",
    pbr: bool = True,
    auto_size: bool = True,
    delight: bool = True,
    quad: bool = False,
    smart_low_poly: bool = False,
    model_seed: Optional[int] = None,
    texture_seed: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Start a Tripo task that generates a 3D model from a text description.

    Prefer create_3d_model_from_image with an approved concept image for anything whose
    look matters; text alone suits simple filler props. The call returns at once with a
    task_id. Poll get_task_status with it until the status is SUCCESS, then save the
    model with download_task_model.

    Args:
        describe_the_look_of_object: The object's shape, material, style and size
            (up to 1024 characters).
        negative_prompt: What to avoid (up to 255 characters).
        model_version: Tripo geometry model. "v3.1-20260211" (default, best quality,
            up to 2M faces with geometry_quality "detailed") or "P2-20260801" (low-poly,
            native quads).
        face_limit: Maximum number of faces; Tripo suggests 50k-100k for game assets.
        texture_quality: "fast", "standard", "detailed" or "extreme" (8K).
        geometry_quality: "standard" or "detailed" (v3.1 only).
        pbr: Also make metallic, roughness and normal maps.
        auto_size: Scale the model to its real-world size in metres.
        delight: Remove lighting baked into the textures (uses texture model v3.5).
        quad: Quad topology (the result is FBX).
        smart_low_poly: Hand-made-style low-poly topology (500-20k faces); may fail on
            complex subjects.
        model_seed: Fix the geometry seed to reproduce or vary a result.
        texture_seed: Fix the texture seed.

    Returns:
        The task ID, its initial status and the settings sent.
    """
    settings = _generation_settings(
        model_version, face_limit, texture_quality, geometry_quality, pbr, auto_size,
        delight, quad, smart_low_poly, model_seed, texture_seed)
    async with _client() as client:
        task_id = await client.text_to_model(
            prompt=describe_the_look_of_object, negative_prompt=negative_prompt, **settings
        )
        return _started(task_id, await client.get_task(task_id), settings)


@mcp.tool()
async def create_3d_model_from_image(
    image: str,
    model_version: str = MODEL_VERSION,
    face_limit: Optional[int] = None,
    texture_quality: str = "standard",
    geometry_quality: str = "standard",
    pbr: bool = True,
    auto_size: bool = True,
    delight: bool = True,
    quad: bool = False,
    smart_low_poly: bool = False,
    model_seed: Optional[int] = None,
    texture_seed: Optional[int] = None,
    orientation: str = "default",
    enable_image_autofix: bool = False,
) -> Dict[str, Any]:
    """
    Start a Tripo task that generates a 3D model from an image.

    Best input: one whole subject, orthographic front view, flat shadowless lighting,
    plain light background, at least 1024 px. The call returns at once with a task_id.
    Poll get_task_status with it until the status is SUCCESS, then save the model with
    download_task_model.

    Args:
        image: Local path or URL of the image.
        model_version: Tripo geometry model. "v3.1-20260211" (default, best quality,
            up to 2M faces with geometry_quality "detailed") or "P2-20260801" (low-poly,
            native quads).
        face_limit: Maximum number of faces; Tripo suggests 50k-100k for game assets.
        texture_quality: "fast", "standard", "detailed" or "extreme" (8K).
        geometry_quality: "standard" or "detailed" (v3.1 only).
        pbr: Also make metallic, roughness and normal maps.
        auto_size: Scale the model to its real-world size in metres.
        delight: Remove lighting baked into the image from the textures (uses texture
            model v3.5).
        quad: Quad topology (the result is FBX).
        smart_low_poly: Hand-made-style low-poly topology (500-20k faces); may fail on
            complex subjects.
        model_seed: Fix the geometry seed to reproduce or vary a result.
        texture_seed: Fix the texture seed.
        orientation: "default", or "align_image" to turn the model to match the image.
        enable_image_autofix: Let Tripo clean up a low-quality image first.

    Returns:
        The task ID, its initial status and the settings sent.
    """
    settings = _generation_settings(
        model_version, face_limit, texture_quality, geometry_quality, pbr, auto_size,
        delight, quad, smart_low_poly, model_seed, texture_seed)
    async with _client() as client:
        task_id = await client.image_to_model(
            image=image, orientation=orientation, enable_image_autofix=enable_image_autofix,
            **settings
        )
        return _started(task_id, await client.get_task(task_id), settings)


@mcp.tool()
async def check_riggable(model_task_id: str) -> Dict[str, Any]:
    """
    Check whether a generated model can be rigged, before paying for rig_model.

    The check is free and waits for its answer (usually seconds). Only call rig_model
    when riggable is true, with the rig_type reported here.

    Args:
        model_task_id: The task ID of a successful create_3d_model_* task.

    Returns:
        Whether the model can be rigged and the rig type Tripo detected (for example
        "biped").
    """
    async with _client() as client:
        task_id = await client.rig_check(model_task_id)
        task = await client.wait_for_task(task_id, timeout=300)
    if task.status != TaskStatus.SUCCESS or not task.output:
        raise ValueError(f"Rig check {task_id} ended with status {task.status}.")
    rig_type = task.output.rig_type
    return {
        "model_task_id": model_task_id,
        "riggable": bool(task.output.riggable),
        "rig_type": getattr(rig_type, "value", rig_type),
    }


@mcp.tool()
async def rig_model(
    model_task_id: str, spec: str = "unreal", rig_type: str = "biped", out_format: str = "glb"
) -> Dict[str, Any]:
    """
    Start a Tripo task that adds a skeleton and skin weights to a generated model.

    Works best on characters generated in a T-pose or A-pose. Call check_riggable first
    (free) and rig only a riggable model. The call returns at once with a new task_id;
    poll get_task_status with it, then save the rigged model with download_task_model.

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
    if task.credits_consumed is not None:
        result["credits_consumed"] = task.credits_consumed
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
