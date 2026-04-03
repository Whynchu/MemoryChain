"""Default questionnaire templates for onboarding and daily check-ins."""
from __future__ import annotations

from ..schemas import QuestionnaireTemplateCreate, QuestionDef


def _onboarding_questions() -> list[QuestionDef]:
    return [
        QuestionDef(id="ob_name", question_text="What should I call you?", question_type="text", required=True, target_field="display_name"),
        QuestionDef(id="ob_schedule", question_text="What's your typical work/school schedule? (e.g., '7am-3:30pm Mon-Fri')", question_type="text", required=False, target_field="schedule"),
        QuestionDef(id="ob_wake", question_text="What time do you usually wake up?", question_type="text", required=False, target_field="wake_time"),
        QuestionDef(id="ob_sleep_target", question_text="How many hours of sleep do you aim for?", question_type="numeric", required=True, min_value=4, max_value=12, target_field="sleep_target"),
        QuestionDef(id="ob_training", question_text="Any regular training or exercise? (e.g., 'muay thai Mon/Wed 6-7pm, running 3x/week')", question_type="text", required=False, target_field="training"),
        QuestionDef(id="ob_goals", question_text="What are your top 3 goals right now? (one per line or comma-separated)", question_type="text", required=True, target_field="goals"),
        QuestionDef(id="ob_track", question_text="What do you want to track daily?\n  1. Sleep  2. Mood  3. Energy  4. Weight\n  5. Stress  6. Soreness  7. Dreams  8. Hydration\n  9. Custom (tell me what!)\nList the numbers or names:", question_type="text", required=True, target_field="tracking_preferences"),
        QuestionDef(id="ob_baseline", question_text="Any health baselines to note? (current weight, conditions, medications, etc.)", question_type="text", required=False, target_field="health_baseline"),
        QuestionDef(id="ob_checkin_time", question_text="When do you prefer to check in?", question_type="choice", required=True, choices=["morning", "evening", "both"], target_field="checkin_time_pref"),
    ]


def _daily_checkin_questions() -> list[QuestionDef]:
    """Adaptive daily check-in. Questions with show_if conditions are handled by the adaptive logic."""
    return [
        # Core rapid-fire
        QuestionDef(id="dc_sleep", question_text="How many hours did you sleep?", question_type="numeric", required=True, min_value=0, max_value=24, target_field="sleep_hours"),
        QuestionDef(id="dc_sleep_quality", question_text="Sleep quality? (1-10)", question_type="scale", required=True, min_value=1, max_value=10, target_field="sleep_quality"),
        QuestionDef(id="dc_mood", question_text="Mood? (1-10)", question_type="scale", required=True, min_value=1, max_value=10, target_field="mood"),
        QuestionDef(id="dc_energy", question_text="Energy level? (1-10)", question_type="scale", required=True, min_value=1, max_value=10, target_field="energy"),
        QuestionDef(id="dc_weight", question_text="Body weight? (or 'skip')", question_type="text", required=False, target_field="body_weight"),
        # Adaptive follow-ups
        QuestionDef(id="dc_dreams", question_text="Any dreams or trouble sleeping last night?", question_type="text", required=False, target_field="dreams", show_if={"question_id": "dc_sleep_quality", "operator": "lt", "value": 6}),
        QuestionDef(id="dc_mood_why", question_text="What's weighing on you?", question_type="text", required=False, target_field="immediate_thoughts", show_if={"question_id": "dc_mood", "operator": "lt", "value": 5}),
        QuestionDef(id="dc_stress", question_text="Stress level? (1-10)", question_type="scale", required=False, min_value=1, max_value=10, target_field="stress_level"),
        QuestionDef(id="dc_soreness", question_text="Any soreness or pain? Where and how bad? (1-10)", question_type="text", required=False, target_field="pain_notes"),
        # Open-ended
        QuestionDef(id="dc_thought_loops", question_text="Any thought loops or things stuck in your head?", question_type="text", required=False, target_field="thought_loops"),
        QuestionDef(id="dc_today_goal", question_text="What's your #1 goal for today?", question_type="text", required=False, target_field="daily_goal"),
        QuestionDef(id="dc_notes", question_text="Anything else to note?", question_type="text", required=False, target_field="notes"),
    ]


ONBOARDING_TEMPLATE = QuestionnaireTemplateCreate(
    user_id="system",
    name="onboarding",
    description="First-time setup — learn about you, your schedule, and what to track",
    questions=_onboarding_questions(),
    target_objects=["user_profile"],
)

DAILY_CHECKIN_TEMPLATE = QuestionnaireTemplateCreate(
    user_id="system",
    name="daily_checkin",
    description="Adaptive daily check-in covering sleep, mood, energy, and more",
    questions=_daily_checkin_questions(),
    target_objects=["daily_checkin", "metric_observation"],
)


def seed_default_templates(repo, user_id: str = "system") -> dict[str, str]:
    """Create default templates if they don't exist. Returns dict of template name -> id."""
    result = {}
    existing = repo.list_questionnaire_templates(user_id, active_only=False)
    # Also check system templates
    system_templates = repo.list_questionnaire_templates("system", active_only=False)
    all_templates = existing + system_templates
    existing_names = {t.name.lower() for t in all_templates}

    if "onboarding" not in existing_names:
        t = repo.create_questionnaire_template(ONBOARDING_TEMPLATE)
        result["onboarding"] = t.id

    if "daily_checkin" not in existing_names:
        t = repo.create_questionnaire_template(DAILY_CHECKIN_TEMPLATE)
        result["daily_checkin"] = t.id

    return result
