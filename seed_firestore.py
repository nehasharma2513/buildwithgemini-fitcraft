#!/usr/bin/env python3
"""Seed script for FitCraft at-home exercises in Firestore."""
from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-03-fff23bb90df6"

SEED_EXERCISES = [
    {
        "id": "pushup-classic",
        "name": "Standard Push-Up",
        "target_muscle": "Chest & Triceps",
        "equipment": "Bodyweight",
        "difficulty": "Beginner",
        "instructions": "Place hands shoulder-width apart. Lower body until chest nearly touches the floor, keeping back flat. Push back up.",
        "recommended_reps": "3 sets of 10-15 reps"
    },
    {
        "id": "doorframe-inverted-row",
        "name": "Doorframe / Towel Row",
        "target_muscle": "Back & Biceps",
        "equipment": "Towel or Doorframe",
        "difficulty": "Beginner",
        "instructions": "Wrap towel around sturdy door handle or grip doorframe. Lean back with straight arms and pull chest toward anchor.",
        "recommended_reps": "3 sets of 8-12 reps"
    },
    {
        "id": "bodyweight-squat",
        "name": "Air Squats",
        "target_muscle": "Quads & Glutes",
        "equipment": "Bodyweight",
        "difficulty": "Beginner",
        "instructions": "Stand feet shoulder-width apart. Hinge at hips and bend knees until thighs are parallel to ground. Drive through heels to stand.",
        "recommended_reps": "3 sets of 15-20 reps"
    },
    {
        "id": "chair-tricep-dips",
        "name": "Living Room Chair Dips",
        "target_muscle": "Triceps & Shoulders",
        "equipment": "Sturdy Chair / Couch",
        "difficulty": "Intermediate",
        "instructions": "Grip chair edge with hands beside hips. Extend legs forward and lower hips by bending elbows to 90 degrees. Press back up.",
        "recommended_reps": "3 sets of 10-12 reps"
    },
    {
        "id": "resistance-band-overhead-press",
        "name": "Resistance Band Overhead Press",
        "target_muscle": "Shoulders & Core",
        "equipment": "Resistance Band",
        "difficulty": "Intermediate",
        "instructions": "Stand on loop band with feet hip-width. Press handles/band upward overhead until arms fully extend. Lower with control.",
        "recommended_reps": "3 sets of 10-12 reps"
    },
    {
        "id": "plank-hold",
        "name": "Forearm Plank",
        "target_muscle": "Core & Abs",
        "equipment": "Bodyweight / Mat",
        "difficulty": "Beginner",
        "instructions": "Rest on forearms and toes. Keep spine neutral, glutes engaged, and hold without sagging hips.",
        "recommended_reps": "3 sets of 45-60 seconds"
    }
]

def seed():
    print(f"Connecting to Firestore with PROJECT_ID: {PROJECT_ID}...")
    db = firestore.Client(project=PROJECT_ID)
    collection = db.collection("home_exercises")
    
    for item in SEED_EXERCISES:
        doc_id = item["id"]
        doc_ref = collection.document(doc_id)
        doc_ref.set(item)
        print(f"Seeded: {item['name']} ({doc_id})")
        
    print(f"Successfully seeded {len(SEED_EXERCISES)} at-home exercises into 'home_exercises'.")

if __name__ == "__main__":
    seed()
