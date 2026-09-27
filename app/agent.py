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

import json
import os
import re
import time
import urllib.parse
import urllib.request
from typing import Optional

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from google import genai
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.memory import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import firestore, storage
from google.genai import types

from .a2ui_utils import a2ui_callback

# HARDCODED PROJECT ID - DO NOT USE os.getenv("GOOGLE_CLOUD_PROJECT") OR google.auth.default()
# On Agent Platform, those env vars return project NUMBER, which breaks Firestore.
PROJECT_ID = "qwiklabs-gcp-01-ef15483519a1"

# HARDCODED BUCKET NAME FOR PUBLIC FITNESS IMAGES
BUCKET_NAME = "fitflex-coach-images-qwiklabs-gcp-01-ef15483519a1"

# Initialize Firestore client
db = firestore.Client(project=PROJECT_ID)

# Initialize AgentEngineSandboxCodeExecutor using deployment_metadata.json
metadata_file = os.path.join(os.path.dirname(__file__), "..", "deployment_metadata.json")
sandbox_resource_name = None
agent_engine_resource_name = None

if os.path.exists(metadata_file):
    try:
        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)
            sandbox_resource_name = metadata.get("sandbox_resource_name")
            agent_engine_resource_name = metadata.get("remote_agent_runtime_id") or metadata.get("agent_engine_resource_name")
    except Exception:
        pass

if sandbox_resource_name:
    code_executor = AgentEngineSandboxCodeExecutor(sandbox_resource_name=sandbox_resource_name)
elif agent_engine_resource_name:
    code_executor = AgentEngineSandboxCodeExecutor(agent_engine_resource_name=agent_engine_resource_name)
else:
    code_executor = AgentEngineSandboxCodeExecutor(
        agent_engine_resource_name=f"projects/1053705018633/locations/us-east1/reasoningEngines/1424393124527996928"
    )



def list_exercises(muscle_group: str = "", equipment: str = "") -> str:
    """List available exercises from the Firestore database with optional filtering.

    Args:
        muscle_group: Filter exercises by targeted muscle group (e.g., 'Chest', 'Legs', 'Back', 'Shoulders', 'Core').
        equipment: Filter exercises by required equipment (e.g., 'Barbell', 'Dumbbell', 'Bodyweight').

    Returns:
        A string listing matching exercises and their details.
    """
    try:
        collection_ref = db.collection("exercises")
        docs = collection_ref.stream()

        results = []
        for doc in docs:
            data = doc.to_dict()
            doc_mg = data.get("muscle_group", "")
            doc_eq = data.get("equipment", "")

            # Apply filters if provided
            if muscle_group and muscle_group.lower() not in doc_mg.lower():
                continue
            if equipment and equipment.lower() not in doc_eq.lower():
                continue

            results.append(
                f"- Name: {data.get('name')}\n"
                f"  Muscle Group: {doc_mg}\n"
                f"  Equipment: {doc_eq}\n"
                f"  Difficulty: {data.get('difficulty')}\n"
                f"  Sets & Reps: {data.get('sets_reps')}\n"
                f"  Description: {data.get('description')}"
            )

        if not results:
            return "No exercises found matching the specified filters."

        return "Exercise Catalog:\n\n" + "\n\n".join(results)
    except Exception as e:
        return f"Error retrieving exercises from Firestore: {str(e)}"


def get_exercise_details(exercise_name: str) -> str:
    """Get detailed information about a specific exercise by name.

    Args:
        exercise_name: The name or partial name of the exercise to search for (e.g., 'Bench Press', 'Squat').

    Returns:
        A string containing full details for the exercise.
    """
    try:
        collection_ref = db.collection("exercises")
        docs = collection_ref.stream()

        matches = []
        for doc in docs:
            data = doc.to_dict()
            name = data.get("name", "")
            if exercise_name.lower() in name.lower():
                matches.append(
                    f"Exercise: {name}\n"
                    f"ID: {doc.id}\n"
                    f"Muscle Group: {data.get('muscle_group')}\n"
                    f"Equipment: {data.get('equipment')}\n"
                    f"Difficulty: {data.get('difficulty')}\n"
                    f"Recommended Sets & Reps: {data.get('sets_reps')}\n"
                    f"Description & Form Guidance: {data.get('description')}"
                )

        if not matches:
            return f"No exercise found matching '{exercise_name}' in the database."

        return "\n\n---\n\n".join(matches)
    except Exception as e:
        return f"Error looking up exercise details in Firestore: {str(e)}"


def add_exercise(
    name: str,
    muscle_group: str,
    equipment: str,
    difficulty: str,
    description: str,
    sets_reps: str,
) -> str:
    """Add a new exercise to the Firestore database catalog.

    Args:
        name: Name of the exercise (e.g., 'Incline Dumbbell Press').
        muscle_group: Targeted muscle group (e.g., 'Chest', 'Triceps', 'Hamstrings').
        equipment: Required equipment (e.g., 'Dumbbell', 'Machine', 'Kettlebell').
        difficulty: Difficulty level ('Beginner', 'Intermediate', or 'Advanced').
        description: Step-by-step description and form instructions for performing the exercise.
        sets_reps: Recommended set and rep scheme (e.g., '3 sets of 10 reps').

    Returns:
        A success message confirming the addition of the exercise.
    """
    try:
        doc_id = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        doc_ref = db.collection("exercises").document(doc_id)

        exercise_data = {
            "name": name,
            "muscle_group": muscle_group,
            "equipment": equipment,
            "difficulty": difficulty,
            "description": description,
            "sets_reps": sets_reps,
        }

        doc_ref.set(exercise_data)
        return f"Successfully added '{name}' (ID: {doc_id}) to the exercise catalog in Firestore!"
    except Exception as e:
        return f"Error adding exercise to Firestore: {str(e)}"


def calculate_fitness_metrics(
    weight_lbs: float,
    reps: int,
    bodyweight_lbs: float = 0.0,
    goal: str = "maintenance",
) -> str:
    """Calculate 1-Rep Max (1RM), intensity training brackets, and daily target macros/calories.

    Args:
        weight_lbs: Weight lifted in pounds (lbs).
        reps: Number of repetitions performed (e.g., 5 or 8).
        bodyweight_lbs: Optional user body weight in pounds for caloric target calculations.
        goal: Training goal ('fat_loss', 'maintenance', or 'muscle_gain').

    Returns:
        A string with calculated 1RM projections, intensity percentages, and daily macro guidelines.
    """
    if reps <= 0 or weight_lbs <= 0:
        return "Please provide positive non-zero values for weight and reps."

    # Epley formula for 1RM: weight * (1 + reps / 30)
    if reps == 1:
        epley_1rm = weight_lbs
    else:
        epley_1rm = weight_lbs * (1.0 + reps / 30.0)

    p90 = epley_1rm * 0.90
    p80 = epley_1rm * 0.80
    p70 = epley_1rm * 0.70

    output = [
        "--- Fitness Metrics & Training Math ---",
        f"Input: {weight_lbs} lbs for {reps} reps",
        f"Estimated 1-Rep Max (1RM): {round(epley_1rm, 1)} lbs",
        "Training Load Brackets:",
        f"  - 90% 1RM (Heavy Strength): {round(p90, 1)} lbs",
        f"  - 80% 1RM (Hypertrophy): {round(p80, 1)} lbs",
        f"  - 70% 1RM (Endurance/Volume): {round(p70, 1)} lbs",
    ]

    if bodyweight_lbs > 0:
        base_cals = bodyweight_lbs * 15.0
        if goal == "fat_loss":
            target_cals = base_cals - 500
        elif goal == "muscle_gain":
            target_cals = base_cals + 300
        else:
            target_cals = base_cals

        protein_g = bodyweight_lbs * 1.0
        fats_g = (target_cals * 0.25) / 9.0
        carbs_g = (target_cals - (protein_g * 4 + fats_g * 9)) / 4.0

        output.extend([
            f"\nDaily Target Macros ({goal.replace('_', ' ').title()} @ {bodyweight_lbs} lbs):",
            f"  - Target Calories: {int(round(target_cals))} kcal/day",
            f"  - Protein: {int(round(protein_g))} g",
            f"  - Carbs: {int(round(carbs_g))} g",
            f"  - Fats: {int(round(fats_g))} g",
        ])

    return "\n".join(output)


def search_food_nutrition(food_item: str) -> str:
    """Search the Open Food Facts public API for real-time nutritional details of a food item or ingredient.

    Args:
        food_item: Name of the food or ingredient to search for (e.g., 'greek yogurt', 'chicken breast', 'oats').

    Returns:
        A string summarizing nutritional values (calories, protein, carbs, fat per 100g) for matching foods.
    """
    if not food_item.strip():
        return "Please specify a food item to search for."

    api_key = os.getenv("OPENFOODFACTS_API_KEY", "")
    query = urllib.parse.quote(food_item.strip())
    url = f"https://world.openfoodfacts.org/cgi/search.pl?search_terms={query}&search_simple=1&action=process&json=1&page_size=3"

    headers = {"User-Agent": "FitFlexCoachAI/1.0"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())

        products = data.get("products", [])
        if not products:
            return f"No nutritional data found for '{food_item}'."

        results = []
        for prod in products[:3]:
            name = prod.get("product_name") or prod.get("generic_name") or food_item
            nutriments = prod.get("nutriments", {})
            cals = nutriments.get("energy-kcal_100g") or "N/A"
            protein = nutriments.get("proteins_100g") or "N/A"
            carbs = nutriments.get("carbohydrates_100g") or "N/A"
            fats = nutriments.get("fat_100g") or "N/A"

            results.append(
                f"- Food Item: {name}\n"
                f"  Calories (per 100g): {cals} kcal\n"
                f"  Protein: {protein} g | Carbs: {carbs} g | Fat: {fats} g"
            )

        return f"Nutritional Information for '{food_item}':\n\n" + "\n\n".join(results)
    except Exception as e:
        return f"Error fetching nutrition data for '{food_item}': {str(e)}"


def geocode_address(address: str) -> str:
    """Convert an address string into geographical latitude and longitude coordinates using Google Geocoding API.

    Args:
        address: The physical address or landmark to geocode (e.g., '1600 Amphitheatre Pkwy, Mountain View, CA').

    Returns:
        A string containing formatted address, latitude, and longitude.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        return "Error: GOOGLE_MAPS_API_KEY environment variable is not set."

    if not address.strip():
        return "Please specify an address to geocode."

    try:
        encoded_address = urllib.parse.quote(address.strip())
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded_address}&key={api_key}"

        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())

        if data.get("status") != "OK" or not data.get("results"):
            return f"Geocoding failed for '{address}'. Status: {data.get('status')}"

        first = data["results"][0]
        formatted = first.get("formatted_address", address)
        location = first.get("geometry", {}).get("location", {})
        lat = location.get("lat")
        lng = location.get("lng")

        return (
            f"Geocoding Result for '{address}':\n"
            f"- Formatted Address: {formatted}\n"
            f"- Location Coordinates: Latitude {lat}, Longitude {lng}"
        )
    except Exception as e:
        return f"Error executing Geocoding API request: {str(e)}"


def find_nearby_places(
    latitude: float,
    longitude: float,
    place_type: str = "gym",
    radius_meters: float = 5000.0,
) -> str:
    """Search for nearby places (e.g. gyms, fitness centers, parks) using the Google Places API (New).

    Args:
        latitude: Latitude coordinate of the center location.
        longitude: Longitude coordinate of the center location.
        place_type: Type of places to search for (e.g., 'gym', 'fitness_center', 'park').
        radius_meters: Search radius in meters (default is 5000 meters / 5km).

    Returns:
        A string listing nearby places with key fields (Name, Address, Location).
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        return "Error: GOOGLE_MAPS_API_KEY environment variable is not set."

    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location",
    }
    payload = {
        "includedTypes": [place_type.strip()],
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": float(latitude),
                    "longitude": float(longitude),
                },
                "radius": float(radius_meters),
            }
        },
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())

        places = data.get("places", [])
        if not places:
            return f"No nearby places of type '{place_type}' found within {radius_meters}m of ({latitude}, {longitude})."

        results = []
        for p in places[:5]:
            display_name = p.get("displayName", {}).get("text", "Unknown Name")
            formatted_address = p.get("formattedAddress", "N/A")
            loc = p.get("location", {})
            lat = loc.get("latitude", "N/A")
            lng = loc.get("longitude", "N/A")

            results.append(
                f"- Name: {display_name}\n"
                f"  Address: {formatted_address}\n"
                f"  Location: Latitude {lat}, Longitude {lng}"
            )

        return f"Nearby Places ({place_type.title()}):\n\n" + "\n\n".join(results)
    except Exception as e:
        return f"Error executing Places API (New) request: {str(e)}"


def generate_fitness_image(prompt: str, tool_context: ToolContext) -> str:
    """Generate an image for an item in the fitness domain (e.g. exercise form, meal prep, fitness food) using gemini-3.1-flash-lite-image in the global region.

    Saves the image to the session artifacts panel and uploads it directly to public Cloud Storage.

    Args:
        prompt: Description of the fitness image to generate (e.g., 'A photo of a healthy protein meal with grilled chicken, rice, and broccoli').
        tool_context: ToolContext object injected by ADK to save session artifacts.

    Returns:
        The public HTTPS Cloud Storage URL of the generated image (https://storage.googleapis.com/<bucket>/<object>).
    """
    if not prompt.strip():
        return "Please provide a valid prompt for image generation."

    try:
        genai_client = genai.Client(
            vertexai=True,
            project=PROJECT_ID,
            location="global",
        )

        response = genai_client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt.strip(),
        )

        image_bytes = None
        mime_type = "image/jpeg"
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    image_bytes = part.inline_data.data
                    if part.inline_data.mime_type:
                        mime_type = part.inline_data.mime_type
                    break

        if not image_bytes:
            return f"Failed to generate image bytes for prompt: '{prompt}'."

        clean_prompt = re.sub(r"[^a-z0-9]+", "_", prompt.lower()[:30]).strip("_")
        timestamp = int(time.time())
        extension = "jpg" if "jpeg" in mime_type else "png"
        filename = f"fitness_{clean_prompt}_{timestamp}.{extension}"

        # 1. Save with tool_context.save_artifact so it shows up in Playground's Artifacts panel
        artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # 2. Upload the same image bytes to public GCS bucket and return public HTTPS URL
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(image_bytes, content_type=mime_type)

        return f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"
    except Exception as e:
        return f"Error generating fitness image: {str(e)}"


def generate_fitness_video(prompt: str, tool_context: ToolContext) -> str:
    """Generate a short video demonstration for an item in the fitness domain (e.g. exercise technique, workout motion, workout tip) using gemini-omni-flash-preview in the global region.

    Saves the video to the session artifacts panel and uploads it directly to public Cloud Storage.

    Args:
        prompt: Description of the fitness video to generate (e.g., 'A 2-second video demonstration of proper barbell squat form').
        tool_context: ToolContext object injected by ADK to save session artifacts.

    Returns:
        The public HTTPS Cloud Storage URL of the generated video (https://storage.googleapis.com/<bucket>/<object>).
    """
    if not prompt.strip():
        return "Please provide a valid prompt for video generation."

    try:
        genai_client = genai.Client(
            vertexai=True,
            project=PROJECT_ID,
            location="global",
        )

        response = genai_client.interactions.create(
            model="gemini-omni-flash-preview",
            input=prompt.strip(),
        )

        video_bytes = None
        mime_type = "video/mp4"

        # Check response for video output
        if hasattr(response, "output_video") and response.output_video:
            out_vid = response.output_video
            if hasattr(out_vid, "data") and out_vid.data:
                video_bytes = out_vid.data
            elif hasattr(out_vid, "bytes") and out_vid.bytes:
                video_bytes = out_vid.bytes

        if not video_bytes and hasattr(response, "outputs") and response.outputs:
            for out in response.outputs:
                if hasattr(out, "video") and out.video:
                    video_bytes = getattr(out.video, "data", None) or getattr(out.video, "bytes", None)
                    if video_bytes:
                        break

        if not video_bytes:
            return f"Failed to extract video bytes from gemini-omni-flash-preview response for prompt: '{prompt}'."

        clean_prompt = re.sub(r"[^a-z0-9]+", "_", prompt.lower()[:30]).strip("_")
        timestamp = int(time.time())
        filename = f"fitness_video_{clean_prompt}_{timestamp}.mp4"

        # 1. Save with tool_context.save_artifact so it shows up in Playground's Artifacts panel
        artifact_part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
        tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # 2. Upload the same video bytes to public GCS bucket and return public HTTPS URL
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(video_bytes, content_type=mime_type)

        return f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"
    except Exception as e:
        return f"Error generating fitness video: {str(e)}"


async def generate_memories_callback(callback_context: CallbackContext):
    """Callback triggered after each turn to extract and persist long-term user memories."""
    try:
        await callback_context.add_session_to_memory()
    except ValueError:
        pass
    return None


def memory_bank_service_builder():
    """Build VertexAiMemoryBankService targeting the deployed Agent Engine Memory Bank."""
    return VertexAiMemoryBankService(
        project=PROJECT_ID,
        location="us-east1",
        agent_engine_id="1424393124527996928",
    )


schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are FitFlex Coach AI, an expert AI fitness coach and personal trainer. "
        "You help users discover exercises, customize workout routines, calculate training math (1RM & macros), "
        "look up food nutrition info, geocode locations, locate nearby gyms, generate visual fitness/meal images or videos, "
        "and execute Python code for complex calculations."
    ),
    workflow_description="Analyze the request, call tools if needed, and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        '{"Image": {"url": {"literalString": "https://..."}}}. Never point an '
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "ALLERGY & MEMORY SAFETY: Track and remember all user allergies (peanuts, tree nuts, dairy, gluten, shellfish, soy, eggs, penicillin) and dietary restrictions mentioned in previous sessions. NEVER suggest recipes or meals containing ingredients the user is allergic to.\n"
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=instruction,
    code_executor=code_executor,
    tools=[
        PreloadMemoryTool(),
        list_exercises,
        get_exercise_details,
        add_exercise,
        calculate_fitness_metrics,
        search_food_nutrition,
        geocode_address,
        find_nearby_places,
        generate_fitness_image,
        generate_fitness_video,
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)





