# Tripo MCP Server

Tripo MCP lets AI assistants generate 3D models with [Tripo AI](https://www.tripo3d.ai) through the [Model Context Protocol (MCP)](https://modelcontextprotocol.io). Generated models are saved to disk as GLB files, so any tool can take them from there: Blender (for example through Blender's own MCP) when a model needs more work, or a game engine such as Unreal directly when it does not.

> **Note:** This project is in alpha.

## Tools

| Tool | What it does |
| --- | --- |
| `create_3d_model_from_text` | Starts a Tripo task from a text description and returns its `task_id`. |
| `create_3d_model_from_image` | Starts a Tripo task from a local image path or URL. |
| `get_task_status` | Reports a task's status, progress and credits used; poll it until `SUCCESS`. |
| `check_riggable` | Free check whether a generated model can be rigged, and as what (for example `biped`). |
| `rig_model` | Rigs a generated model (default: Unreal Mannequin skeleton naming); returns a new `task_id`. |
| `download_task_model` | Saves a finished task's model (usually `.glb`) and preview image to a folder. |

A typical run: start a task, poll `get_task_status` (generation usually takes 1-5 minutes), then call `download_task_model`. For a character, call `check_riggable` before `rig_model`.

### Generation defaults

The generation tools pin Tripo's models instead of taking whatever the API or SDK defaults to (the tripo3d SDK otherwise sends the legacy `v2.5-20250123` model):

- geometry model `v3.1-20260211` (pass `model_version="P2-20260801"` for low-poly with native quads),
- texture model `v3.5-20260815` with `delight` on, which removes lighting baked into the input image,
- PBR maps and `auto_size` (real-world size in metres) on.

Both tools also take `face_limit`, `texture_quality`, `geometry_quality`, `quad`, `smart_low_poly` and the `model_seed`/`texture_seed` seeds; the image tool adds `orientation` and `enable_image_autofix`, the text tool `negative_prompt`. Each call returns the settings it sent.

## Setup

### Prerequisites

- Python 3.10+
- A Tripo API key (it starts with `tsk_`), from your Tripo account

### API key

The server reads the key from the `TRIPO_API_KEY` environment variable; it is never passed as a tool argument or stored in the MCP configuration. On Windows, add it as a user environment variable (Start → "Edit environment variables for your account"), then restart your MCP client so it inherits the variable.

### Output folder

`download_task_model` saves into the `output_dir` you pass, or into the folder named by the optional `TRIPO_OUTPUT_DIR` environment variable. Keep it outside a game engine's watched content folder if the engine would otherwise prompt to import new files.

### Install and register

```bash
git clone https://github.com/lifelike-and-believable/tripo-mcp.git
cd tripo-mcp
python -m venv .venv
.venv/Scripts/python -m pip install -e .
```

Register the server with your MCP client, for example Claude Code:

```bash
claude mcp add --scope user tripo -e "TRIPO_OUTPUT_DIR=C:\path\to\generated" -- "C:\path\to\tripo-mcp\.venv\Scripts\tripo-mcp.exe"
```

Or in a JSON MCP configuration:

```json
{
  "mcpServers": {
    "tripo": {
      "command": "C:\\path\\to\\tripo-mcp\\.venv\\Scripts\\tripo-mcp.exe",
      "env": { "TRIPO_OUTPUT_DIR": "C:\\path\\to\\generated" }
    }
  }
}
```

## Acknowledgements

- **[Tripo AI](https://www.tripo3d.ai)**
- **[blender-mcp](https://github.com/ahujasid/blender-mcp)** by [Siddharth Ahuja](https://github.com/ahujasid), which inspired the original version of this server
