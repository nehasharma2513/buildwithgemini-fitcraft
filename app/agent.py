# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
from zoneinfo import ZoneInfo

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.memory import VertexAiMemoryBankService
from google.genai import types
from google.cloud import firestore

MODEL = "gemini-3.8-flash"
PROJECT_ID = "qwiklabs-gcp-03-fff23bb90df6"
LOCATION = "us-east1"
AGENT_ENGINE_ID = "6802079207212974080"
AGENT_ENGINE_RESOURCE = f"projects/331565616056/locations/{LOCATION}/reasoningEngines/{AGENT_ENGINE_ID}"



def _get_firestore_client() -> firestore.Client:
    return firestore.Client(project=PROJECT_ID)


def list_home_exercises(muscle_group: str = "", equipment: str = "") -> list[dict]:
    """Retrieve exercises from the at-home exercises catalog in Firestore.

    Args:
        muscle_group: Optional filter by target muscle group (e.g. 'Core', 'Chest', 'Back', 'Quads').
        equipment: Optional filter by required equipment (e.g. 'Bodyweight', 'Towel', 'Resistance Band').

    Returns:
        A list of matching exercise records.
    """
    db = _get_firestore_client()
    docs = db.collection("home_exercises").stream()
    results = []
    m_filter = muscle_group.lower().strip()
    e_filter = equipment.lower().strip()

    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        
        target = data.get("target_muscle", "").lower()
        equip = data.get("equipment", "").lower()

        if m_filter and m_filter not in target:
            continue
        if e_filter and e_filter not in equip:
            continue
        results.append(data)
    return results


def log_workout_session(exercise_name: str, sets: int, reps: int, notes: str = "") -> dict:
    """Log a completed at-home workout session into Firestore.

    Args:
        exercise_name: Name of the exercise performed.
        sets: Number of sets completed.
        reps: Number of repetitions per set.
        notes: Optional user notes or feedback about intensity/difficulty.

    Returns:
        A dictionary confirming the saved workout record.
    """
    db = _get_firestore_client()
    import time

    record = {
        "exercise_name": exercise_name,
        "sets": sets,
        "reps": reps,
        "notes": notes,
        "timestamp": time.time(),
        "date_str": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    _, doc_ref = db.collection("workout_logs").add(record)
    return {"status": "success", "log_id": doc_ref.id, "record": record}


def search_online_exercise_library(query: str) -> list[dict]:
    """Search an open public fitness database (wger REST API) for exercise definitions, muscles, and technique details.

    Args:
        query: Name or keyword of the exercise to search for (e.g., 'squat', 'plank', 'swing', 'press').

    Returns:
        A list of matching exercises with category, muscles worked, and descriptions.
    """
    import urllib.request
    import json
    import os

    api_key = os.getenv("WGER_API_KEY", "")
    url = "https://wger.de/api/v2/exerciseinfo/?limit=50"
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Token {api_key}"

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as e:
        return [{"error": f"Failed to reach online exercise database: {str(e)}"}]

    results = []
    q = query.lower().strip()

    for item in payload.get("results", []):
        cat = item.get("category", {}).get("name", "")
        muscles = [m.get("name_en") or m.get("name") for m in item.get("muscles", []) if m]
        
        for tr in item.get("translations", []):
            name = tr.get("name", "")
            desc = tr.get("description_source", "") or tr.get("description", "")
            
            # Match query in exercise name or category
            if q in name.lower() or q in cat.lower():
                results.append({
                    "name": name,
                    "category": cat,
                    "target_muscles": muscles,
                    "description": desc[:250] + "..." if len(desc) > 250 else desc,
                })
                break

        if len(results) >= 5:
            break

    return results if results else [{"message": f"No online exercises found matching '{query}'"}]


async def generate_exercise_visual(prompt: str, tool_context: ToolContext) -> dict:
    """Generate a workout or exercise visual illustration using Gemini image generation,
    save it to the agent session artifacts, and upload to public Cloud Storage.

    Args:
        prompt: Description of the exercise visual or badge to generate (e.g. 'A clean flat illustration of a push-up form').
        tool_context: The ADK tool execution context to save artifacts.

    Returns:
        A dict containing the public image URL, filename, and status.
    """
    from google import genai
    from google.cloud import storage
    import uuid

    BUCKET_NAME = "fitcraft-assets-88qvpw"
    IMAGE_MODEL = "gemini-3.1-flash-lite-image"

    # 1. Generate image with Gemini in the global location
    client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
    response = client.models.generate_content(
        model=IMAGE_MODEL,
        contents=f"High quality workout vector illustration or fitness badge for home workout: {prompt}",
    )

    image_bytes = None
    mime_type = "image/jpeg"
    for part in response.candidates[0].content.parts:
        if part.inline_data:
            image_bytes = part.inline_data.data
            mime_type = part.inline_data.mime_type or "image/jpeg"
            break

    if not image_bytes:
        return {"error": "Model did not return image data."}

    ext = "png" if "png" in mime_type else "jpg"
    filename = f"exercise_{uuid.uuid4().hex[:8]}.{ext}"

    # 2. Save artifact for the Playground Artifacts panel
    artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    await tool_context.save_artifact(filename=filename, artifact=artifact_part)


    # 3. Upload to public Cloud Storage bucket
    storage_client = storage.Client(project=PROJECT_ID)
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(filename)
    blob.upload_from_string(image_bytes, content_type=mime_type)
    public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"

    return {
        "status": "success",
        "filename": filename,
        "public_url": public_url,
        "message": f"Generated image and published to {public_url}",
    }


async def generate_exercise_video(prompt: str, tool_context: ToolContext) -> dict:
    """Generate a short video for an exercise or movement in the agent's domain using
    Google's Omni model (gemini-omni-flash-preview) in the global region.
    Saves the video to the agent's session artifacts (so it shows in the Playground Artifacts panel)
    and uploads the video bytes to public Cloud Storage, returning the public HTTPS URL.

    Args:
        prompt: Description of the exercise demonstration video (e.g. 'A clean 3-second demo of a bodyweight squat').
        tool_context: The ADK tool execution context to save artifacts.

    Returns:
        A dict containing the public video URL, filename, and status.
    """
    import base64
    import uuid
    import requests
    import google.auth
    import google.auth.transport.requests
    from google.cloud import storage

    BUCKET_NAME = "fitcraft-assets-88qvpw"
    MODEL_ID = "gemini-omni-flash-preview"

    # 1. Authenticate and query Gemini Omni via Vertex AI Interactions API
    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    auth_req = google.auth.transport.requests.Request()
    creds.refresh(auth_req)

    url = f"https://aiplatform.googleapis.com/v1beta1/projects/{PROJECT_ID}/locations/global/interactions"
    headers = {
        "Authorization": f"Bearer {creds.token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    payload = {
        "model": MODEL_ID,
        "input": [
            {
                "type": "text",
                "text": f"A short demonstration video for an at-home fitness exercise: {prompt}",
            }
        ],
        "response_format": [
            {
                "type": "video",
                "aspect_ratio": "16:9",
                "resolution": "720p",
                "duration": "3s",
            }
        ],
        "generation_config": {
            "video_config": {
                "task": "text_to_video"
            }
        },
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=240)
    if resp.status_code != 200:
        return {"error": f"Failed to generate video: {resp.text[:500]}"}

    data = resp.json()
    video_bytes = None
    mime_type = "video/mp4"

    for step in data.get("steps", []):
        for content in step.get("content", []):
            if content.get("type") == "video" and content.get("data"):
                video_bytes = base64.b64decode(content["data"])
                mime_type = content.get("mime_type") or "video/mp4"
                break
        if video_bytes:
            break

    if not video_bytes:
        return {"error": "Model did not return video bytes."}

    filename = f"exercise_video_{uuid.uuid4().hex[:8]}.mp4"

    # 2. Save artifact for the Playground's Artifacts panel
    artifact_part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
    await tool_context.save_artifact(filename=filename, artifact=artifact_part)

    # 3. Upload to public Cloud Storage bucket
    storage_client = storage.Client(project=PROJECT_ID)
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(filename)
    blob.upload_from_string(video_bytes, content_type=mime_type)
    public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"

    return {
        "status": "success",
        "filename": filename,
        "public_url": public_url,
        "message": f"Generated video and published to {public_url}",
    }


async def generate_memories_callback(callback_context: CallbackContext):
    """WRITE: after each turn, extract durable facts and user workout preferences into Memory Bank."""
    await callback_context.add_session_to_memory()
    return None


def memory_bank_service_builder() -> VertexAiMemoryBankService:
    """Provides the VertexAiMemoryBankService pointed at the Agent Engine."""
    return VertexAiMemoryBankService(
        project=PROJECT_ID,
        location=LOCATION,
        agent_engine_id=AGENT_ENGINE_ID,
    )


sandbox_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=AGENT_ENGINE_RESOURCE
)

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are FitCraft, an expert at-home workout and equipment coach. "
        "Help users design and follow effective workouts from home without needing to step outside. "
        "You remember user preferred home workouts, exercises, injuries/limitations, equipment on hand, "
        "and training goals across conversations, and use them to personalize every recommendation. "
        "Use list_home_exercises to look up movements from your local Firestore catalog matching the user's constraints, "
        "use search_online_exercise_library to query the broader public fitness exercise database for specialized movements, "
        "use generate_exercise_visual to generate visual workout illustrations or form badges and share the public image URL, "
        "use generate_exercise_video to generate demonstration videos of workouts using Gemini Omni and share the public video URL, "
        "and use log_workout_session whenever the user completes or logs a workout."
    ),
    tools=[
        PreloadMemoryTool(),
        list_home_exercises,
        log_workout_session,
        search_online_exercise_library,
        generate_exercise_visual,
        generate_exercise_video,
    ],
    code_executor=sandbox_executor,
    after_agent_callback=generate_memories_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)




