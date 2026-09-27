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
"""Unit tests for FitFlex Coach AI Firestore tools."""

from app.agent import (
    add_exercise,
    calculate_fitness_metrics,
    find_nearby_places,
    generate_fitness_image,
    geocode_address,
    get_exercise_details,
    list_exercises,
    search_food_nutrition,
)


class DummyToolContext:
    def __init__(self):
        self.saved_artifacts = []

    def save_artifact(self, filename: str, artifact, custom_metadata=None):
        self.saved_artifacts.append((filename, artifact))
        return 1


def test_list_exercises() -> None:
    """Test retrieving exercises from Firestore."""
    result = list_exercises()
    assert "Exercise Catalog" in result
    assert "Barbell Bench Press" in result or "Pull-Ups" in result


def test_list_exercises_filtered() -> None:
    """Test filtering exercises by muscle group."""
    result = list_exercises(muscle_group="Chest")
    assert "Chest" in result or "Barbell Bench Press" in result


def test_get_exercise_details() -> None:
    """Test fetching exercise details by name."""
    result = get_exercise_details("Plank")
    assert "Forearm Plank" in result or "Core" in result


def test_add_and_query_exercise() -> None:
    """Test adding a new exercise to Firestore and retrieving it."""
    add_res = add_exercise(
        name="Cable Face Pull",
        muscle_group="Shoulders",
        equipment="Cable",
        difficulty="Beginner",
        description="Attach rope to high pulley, pull towards face while flaring elbows outwards.",
        sets_reps="3 sets of 15 reps",
    )
    assert "Successfully added 'Cable Face Pull'" in add_res

    details = get_exercise_details("Cable Face Pull")
    assert "Cable Face Pull" in details
    assert "Shoulders" in details


def test_calculate_fitness_metrics() -> None:
    """Test 1RM and macro calculations."""
    res = calculate_fitness_metrics(
        weight_lbs=225, reps=5, bodyweight_lbs=180, goal="muscle_gain"
    )
    assert "Estimated 1-Rep Max (1RM): 262.5 lbs" in res
    assert "Daily Target Macros" in res
    assert "Muscle Gain" in res


def test_search_food_nutrition() -> None:
    """Test searching Open Food Facts API."""
    res = search_food_nutrition("oats")
    assert "Nutritional Information" in res or "Error fetching" in res or "No nutritional data" in res


def test_geocode_address() -> None:
    """Test geocoding address with Google Geocoding API."""
    res = geocode_address("1600 Amphitheatre Pkwy, Mountain View, CA")
    assert "Mountain View" in res or "37.422" in res


def test_find_nearby_places() -> None:
    """Test finding nearby places with Google Places API (New)."""
    res = find_nearby_places(latitude=37.4224864, longitude=-122.0855962, place_type="gym")
    assert "Nearby Places" in res or "Gym" in res


def test_generate_fitness_image() -> None:
    """Test generating a fitness image using gemini-3.1-flash-lite-image."""
    dummy_ctx = DummyToolContext()
    url = generate_fitness_image("A high protein salmon salad bowl", tool_context=dummy_ctx)
    assert "https://storage.googleapis.com/fitflex-coach-images-qwiklabs-gcp-01-ef15483519a1/" in url
    assert len(dummy_ctx.saved_artifacts) == 1





