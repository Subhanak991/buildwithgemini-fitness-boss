"""Seed script for populating the Firestore database with initial exercise items."""

from google.cloud import firestore

# HARDCODED PROJECT ID - DO NOT USE os.getenv("GOOGLE_CLOUD_PROJECT") OR google.auth.default()
# On Agent Platform runtime, env vars return project NUMBER, which breaks Firestore.
PROJECT_ID = "qwiklabs-gcp-01-ef15483519a1"

INITIAL_EXERCISES = [
    {
        "id": "barbell-bench-press",
        "name": "Barbell Bench Press",
        "muscle_group": "Chest",
        "equipment": "Barbell",
        "difficulty": "Intermediate",
        "description": "Lie flat on the bench, grip the barbell slightly wider than shoulder width, lower the bar to mid-chest, and press explosively.",
        "sets_reps": "4 sets of 8-12 reps",
    },
    {
        "id": "bulgarian-split-squat",
        "name": "Bulgarian Split Squat",
        "muscle_group": "Legs",
        "equipment": "Dumbbell",
        "difficulty": "Intermediate",
        "description": "Place rear foot elevated on a bench, lower hips until front thigh is parallel to floor, and drive through the front heel.",
        "sets_reps": "3 sets of 10-12 reps per leg",
    },
    {
        "id": "pull-ups",
        "name": "Pull-Ups",
        "muscle_group": "Back",
        "equipment": "Bodyweight",
        "difficulty": "Intermediate",
        "description": "Grip the overhead bar with an overhand grip wider than shoulder width, pull chest to bar, and control the descent.",
        "sets_reps": "3 sets of 8-10 reps",
    },
    {
        "id": "dumbbell-overhead-press",
        "name": "Dumbbell Overhead Press",
        "muscle_group": "Shoulders",
        "equipment": "Dumbbell",
        "difficulty": "Beginner",
        "description": "Sit or stand upright holding dumbbells at shoulder level, press upward overhead until arms are extended, and lower slowly.",
        "sets_reps": "3 sets of 10-12 reps",
    },
    {
        "id": "plank",
        "name": "Forearm Plank",
        "muscle_group": "Core",
        "equipment": "Bodyweight",
        "difficulty": "Beginner",
        "description": "Maintain a straight body line resting on forearms and toes while engaging core and glutes without sagging hips.",
        "sets_reps": "3 sets of 45-60 seconds hold",
    },
]


def seed_database():
    db = firestore.Client(project=PROJECT_ID)
    collection_ref = db.collection("exercises")

    print(f"Seeding Firestore collection 'exercises' in project '{PROJECT_ID}'...")
    for item in INITIAL_EXERCISES:
        doc_id = item["id"]
        data = {k: v for k, v in item.items() if k != "id"}
        collection_ref.document(doc_id).set(data)
        print(f"  ✓ Added exercise: {item['name']} ({item['muscle_group']})")

    print("Successfully seeded Firestore database!")


if __name__ == "__main__":
    seed_database()
