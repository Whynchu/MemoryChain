"""
Questionnaire conversation service.

Handles running structured questionnaires as natural conversations,
tracking progress through questions, parsing answers, and storing results.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from ..schemas import (
    QuestionDef,
    QuestionnaireSession,
    QuestionnaireSessionCreate,
    QuestionnaireTemplate,
    DailyCheckinCreate,
    ActivityCreate,
    MetricObservationCreate,
)
from ..storage.repository import Repository
from .answer_parser import parse_answer, AnswerParsingError


class QuestionnaireService:
    """Service for managing questionnaire conversations."""
    
    def __init__(self, repo: Repository):
        self.repo = repo
    
    def check_active_session(self, user_id: str, conversation_id: str) -> Optional[QuestionnaireSession]:
        """Check if there's an active questionnaire session in this conversation."""
        return self.repo.get_active_questionnaire_session(user_id, conversation_id)
    
    def _get_effective_questions(
        self, template: QuestionnaireTemplate, user_id: str
    ) -> list[QuestionDef]:
        """Return template questions extended with custom dimension questions for daily check-ins."""
        questions = list(template.questions)
        if template.name == "daily_checkin":
            profile = self.repo.get_user_profile(user_id)
            if profile and profile.custom_dimensions:
                for dim in profile.custom_dimensions:
                    slug = dim["name"].lower().replace(" ", "_")
                    unit = dim.get("unit", "")
                    q_text = f"{dim['name']}? ({unit})" if unit else f"{dim['name']}?"
                    q_type = "numeric" if dim.get("type") in ("numeric", "number") else "text"
                    questions.append(
                        QuestionDef(
                            id=f"custom_{slug}",
                            question_text=q_text,
                            question_type=q_type,
                            required=False,
                            target_field=f"custom_{slug}",
                        )
                    )
        return questions

    def start_questionnaire(
        self, 
        user_id: str, 
        template_id: str, 
        conversation_id: str
    ) -> tuple[QuestionnaireSession, str]:
        """
        Start a new questionnaire session.
        
        Returns:
            (session, first_question_text)
        """
        # Get the template
        template = self.repo.get_questionnaire_template(template_id, user_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        if not template.questions:
            raise ValueError("Template has no questions")
        
        questions = self._get_effective_questions(template, user_id)
        
        # Create session
        session = self.repo.create_questionnaire_session(
            QuestionnaireSessionCreate(
                user_id=user_id,
                template_id=template_id,
                conversation_id=conversation_id,
            )
        )
        
        # Get first question (skip any that have unsatisfied show_if — unlikely for first questions)
        first_index = self._find_next_showable_question(questions, 0, {})
        if first_index is None:
            raise ValueError("Template has no showable questions")

        first_question = questions[first_index]
        visible_total = self._count_visible_questions(questions, {})
        question_text = self._format_question(first_question, template, 1, visible_total)
        
        # If the first showable question is not index 0, update the session
        if first_index != 0:
            self.repo.update_questionnaire_session(
                session.id, session.user_id,
                current_question_index=first_index,
            )
        
        return session, question_text
    
    def process_answer(
        self, 
        session: QuestionnaireSession, 
        user_response: str
    ) -> tuple[Optional[str], bool]:
        """
        Process user's answer to current question.
        
        Returns:
            (next_question_text_or_none, is_complete)
        """
        # Get template and current question
        template = self.repo.get_questionnaire_template(session.template_id, session.user_id)
        if not template:
            raise ValueError("Template not found")
        
        questions = self._get_effective_questions(template, session.user_id)
        
        if session.current_question_index >= len(questions):
            return None, True  # Already complete
        
        current_question = questions[session.current_question_index]
        
        # Parse the answer
        try:
            parsed_value = parse_answer(
                raw_text=user_response,
                question_type=current_question.question_type,
                choices=current_question.choices,
                min_value=current_question.min_value,
                max_value=current_question.max_value,
            )
        except AnswerParsingError as e:
            # Return error message as next question (retry)
            retry_text = (
                f"I couldn't understand '{user_response}' for that question. {str(e)}. "
                f"Let me ask again:\n\n{current_question.question_text}"
            )
            if current_question.help_text:
                retry_text += f"\n\n{current_question.help_text}"
            return retry_text, False
        
        # Store the answer
        updated_answers = session.answers.copy()
        updated_answers[current_question.id] = parsed_value
        
        updated_responses = session.raw_responses.copy()
        updated_responses[current_question.id] = user_response
        
        # Find next showable question (skip those whose show_if condition is not met)
        next_index = self._find_next_showable_question(
            questions,
            session.current_question_index + 1,
            updated_answers,
        )
        is_complete = next_index is None
        
        # Update session
        self.repo.update_questionnaire_session(
            session.id,
            session.user_id,
            current_question_index=next_index if not is_complete else len(questions),
            answers=updated_answers,
            raw_responses=updated_responses,
            status="completed" if is_complete else "in_progress",
        )
        
        if is_complete:
            # Store structured data based on answers
            self._store_questionnaire_results(session, template, updated_answers, questions)
            return self._generate_completion_message(template, updated_answers, questions), True
        else:
            # Ask next question
            next_question = questions[next_index]
            answered_so_far = sum(
                1 for i in range(next_index)
                if self._should_show_question(questions[i], updated_answers)
                or questions[i].id in updated_answers
            )
            visible_total = self._count_visible_questions(questions, updated_answers)
            question_text = self._format_question(
                next_question, template, answered_so_far + 1, visible_total
            )
            return question_text, False

    # ── Adaptive question helpers ────────────────────────────

    def _should_show_question(self, question: QuestionDef, answers: dict[str, object]) -> bool:
        """Evaluate whether a conditional question should be shown."""
        if not question.show_if:
            return True  # No condition = always show

        condition = question.show_if
        dep_id = condition.get("question_id")
        operator = condition.get("operator", "lt")
        threshold = condition.get("value", 5)

        dep_answer = answers.get(dep_id)
        if dep_answer is None:
            return False  # Dependency not answered, skip

        try:
            dep_value = float(dep_answer)
        except (ValueError, TypeError):
            return True  # Non-numeric answer, show anyway

        if operator == "lt":
            return dep_value < threshold
        elif operator == "lte":
            return dep_value <= threshold
        elif operator == "gt":
            return dep_value > threshold
        elif operator == "gte":
            return dep_value >= threshold
        elif operator == "eq":
            return dep_value == threshold
        return True

    def _find_next_showable_question(
        self,
        questions: list[QuestionDef],
        start_index: int,
        answers: dict[str, object],
    ) -> int | None:
        """Return the index of the next question to show, or None if done."""
        idx = start_index
        while idx < len(questions):
            if self._should_show_question(questions[idx], answers):
                return idx
            idx += 1
        return None

    def _count_visible_questions(
        self,
        questions: list[QuestionDef],
        answers: dict[str, object],
    ) -> int:
        """Estimate the number of visible questions given current answers."""
        return sum(1 for q in questions if self._should_show_question(q, answers))
    
    def _format_question(self, question, template, question_num: int, total_questions: int) -> str:
        """Format a question for conversational presentation."""
        text = f"**{question.question_text}**"
        
        if question.help_text:
            text += f"\n\n*{question.help_text}*"
        
        # Add context based on question type
        if question.question_type == "scale" and question.min_value and question.max_value:
            text += f"\n\n(Scale: {question.min_value}-{question.max_value})"
        elif question.question_type == "choice" and question.choices:
            text += f"\n\nOptions: {', '.join(question.choices)}"
        elif question.question_type == "boolean":
            text += f"\n\n(Answer: yes/no)"
        
        # Add progress indicator
        if total_questions > 1:
            text += f"\n\n*Question {question_num} of {total_questions}*"
        
        return text
    
    def _store_questionnaire_results(
        self, 
        session: QuestionnaireSession, 
        template: QuestionnaireTemplate, 
        answers: dict,
        questions: list[QuestionDef] | None = None,
    ) -> None:
        """Store questionnaire results as appropriate structured data."""
        questions = questions or list(template.questions)
        now = datetime.now(timezone.utc)
        
        # Create a source document for the questionnaire completion
        from ..schemas import SourceDocumentCreate
        source = self.repo.create_source_document(
            SourceDocumentCreate(
                user_id=session.user_id,
                source_type="manual_log",
                effective_at=now,
                title=f"Questionnaire: {template.name}",
                raw_text=f"Completed questionnaire '{template.name}'",
                metadata={
                    "questionnaire_session_id": session.id,
                    "template_id": template.id,
                    "answers": answers,
                },
            )
        )
        
        # Based on target objects, create appropriate structured data
        if "daily_checkin" in template.target_objects:
            self._create_daily_checkin_from_answers(
                session.user_id, source.id, now, answers, questions
            )
        
        if "activity" in template.target_objects:
            self._create_activity_from_answers(
                session.user_id, source.id, now, answers, questions
            )
        
        if "metric_observation" in template.target_objects:
            self._create_metrics_from_answers(
                session.user_id, source.id, now, answers, questions
            )

        if "user_profile" in template.target_objects:
            self._create_user_profile_from_answers(
                session.user_id, answers, questions
            )
    
    def _create_daily_checkin_from_answers(self, user_id: str, source_id: str, now: datetime, answers: dict, questions) -> None:
        """Map questionnaire answers to daily checkin fields."""
        checkin_data = {}
        
        # Map common question IDs to checkin fields
        field_mapping = {
            "sleep_hours": "sleep_hours",
            "sleep": "sleep_hours", 
            "sleep_quality": "sleep_quality",
            "quality": "sleep_quality",
            "mood": "mood",
            "energy": "energy",
            "weight": "body_weight",
            "body_weight": "body_weight",
        }
        
        for question_id, answer in answers.items():
            if question_id in field_mapping:
                checkin_data[field_mapping[question_id]] = answer
        
        if checkin_data:
            self.repo.create_checkin(
                DailyCheckinCreate(
                    user_id=user_id,
                    source_document_id=source_id,
                    date=now.date(),
                    effective_at=now,
                    **checkin_data,
                )
            )
    
    def _create_activity_from_answers(self, user_id: str, source_id: str, now: datetime, answers: dict, questions) -> None:
        """Create activity records from questionnaire answers."""
        # Look for activity-related questions
        activity_type = answers.get("activity_type", "workout")
        title = answers.get("activity", answers.get("title", "Training Session"))
        duration = answers.get("duration")
        notes_parts = []
        
        # Gather relevant answer text
        for question_id, answer in answers.items():
            if question_id not in ["activity_type", "activity", "title", "duration"]:
                # Add other answers as notes
                notes_parts.append(f"{question_id}: {answer}")
        
        notes = "; ".join(notes_parts) if notes_parts else None
        
        self.repo.create_activity(
            ActivityCreate(
                user_id=user_id,
                source_document_id=source_id,
                effective_at=now,
                activity_type=activity_type,
                title=title,
                notes=notes,
                metadata={"duration_minutes": duration} if duration else {},
            )
        )
    
    def _create_metrics_from_answers(self, user_id: str, source_id: str, now: datetime, answers: dict, questions) -> None:
        """Create metric observations from numeric answers."""
        question_map = {q.id: q for q in questions}
        for question_id, answer in answers.items():
            if isinstance(answer, (int, float)):
                q = question_map.get(question_id)
                # Use target_field as metric name for custom dims, fall back to question_id
                metric_name = (q.target_field if q and q.target_field else question_id)
                self.repo.create_metric_observation(
                    MetricObservationCreate(
                        user_id=user_id,
                        source_document_id=source_id,
                        effective_at=now,
                        metric_type=metric_name,
                        value=str(answer),
                        unit="",
                    )
                )

    def _create_user_profile_from_answers(self, user_id: str, answers: dict, questions: list) -> None:
        """Map onboarding answers to a UserProfile."""
        field_map: dict[str, str] = {}
        for q in questions:
            if q.target_field and q.id in answers:
                field_map[q.target_field] = answers[q.id]

        # Parse tracking preferences into custom dimensions
        custom_dims = self._parse_tracking_preferences(field_map.get("tracking_preferences", ""))

        sleep_target_raw = field_map.get("sleep_target")
        try:
            sleep_target = float(sleep_target_raw) if sleep_target_raw is not None else 8.0
        except (ValueError, TypeError):
            sleep_target = 8.0

        schedule = {}
        if field_map.get("schedule"):
            schedule["work"] = field_map["schedule"]
        if field_map.get("training"):
            schedule["training"] = field_map["training"]

        existing = self.repo.get_user_profile(user_id)
        if existing:
            self.repo.update_user_profile(
                user_id,
                display_name=field_map.get("display_name"),
                schedule=schedule,
                sleep_target=sleep_target,
                wake_time=field_map.get("wake_time"),
                checkin_time_pref=field_map.get("checkin_time_pref", "morning"),
                custom_dimensions=custom_dims,
                onboarded_at=datetime.now(timezone.utc),
            )
        else:
            from ..schemas import UserProfileCreate
            self.repo.create_user_profile(UserProfileCreate(
                user_id=user_id,
                display_name=field_map.get("display_name"),
                schedule=schedule,
                sleep_target=sleep_target,
                wake_time=field_map.get("wake_time"),
                checkin_time_pref=field_map.get("checkin_time_pref", "morning"),
                custom_dimensions=custom_dims,
            ))
            self.repo.update_user_profile(user_id, onboarded_at=datetime.now(timezone.utc))

        # Create goals from goals text
        goals_text = field_map.get("goals", "")
        if goals_text:
            self._create_goals_from_text(user_id, goals_text)

    @staticmethod
    def _parse_tracking_preferences(text: str) -> list[dict]:
        """Convert free-text tracking preferences into custom dimension dicts.

        Predefined dimensions (sleep, mood, energy, etc.) are already covered
        by the daily check-in template, so only truly custom items are returned.
        """
        if not text:
            return []
        PREDEFINED = {
            "1": "sleep", "sleep": "sleep",
            "2": "mood", "mood": "mood",
            "3": "energy", "energy": "energy",
            "4": "weight", "weight": "weight",
            "5": "stress", "stress": "stress",
            "6": "soreness", "soreness": "soreness",
            "7": "dreams", "dreams": "dreams",
            "8": "hydration", "hydration": "hydration",
        }
        parts = [p.strip().lower() for p in text.replace(",", " ").split() if p.strip()]
        customs: list[dict] = []
        seen: set[str] = set()
        for part in parts:
            if part in PREDEFINED:
                continue  # Predefined — already in the check-in template
            if part not in seen:
                customs.append({"name": part, "unit": "", "type": "numeric"})
                seen.add(part)
        return customs

    def _create_goals_from_text(self, user_id: str, text: str) -> None:
        """Create Goal objects from comma/newline separated text."""
        from ..schemas import GoalCreate
        lines = [l.strip().strip("-•*").strip() for l in text.replace(",", "\n").splitlines()]
        for line in lines:
            if line:
                self.repo.create_goal(GoalCreate(
                    user_id=user_id,
                    title=line,
                    status="active",
                    priority="medium",
                ))
    
    def _generate_completion_message(
        self,
        template: QuestionnaireTemplate,
        answers: dict,
        questions: list[QuestionDef] | None = None,
    ) -> str:
        """Generate a completion message summarizing the questionnaire."""
        questions = questions or list(template.questions)
        summary_parts = []
        
        for question in questions:
            answer = answers.get(question.id)
            if answer is not None:
                if question.question_type == "scale":
                    summary_parts.append(f"{question.question_text}: {answer}")
                elif question.question_type == "numeric":
                    summary_parts.append(f"{question.question_text}: {answer}")
                elif question.question_type == "boolean":
                    summary_parts.append(f"{question.question_text}: {'Yes' if answer else 'No'}")
                else:
                    summary_parts.append(f"{question.question_text}: {answer}")
        
        message = f"✅ **{template.name} completed!**\n\n"
        if summary_parts:
            message += "**Summary:**\n" + "\n".join(f"• {part}" for part in summary_parts)
        
        return message


def is_questionnaire_command(message: str) -> Optional[str]:
    """
    Check if a message is a questionnaire start command.
    
    Returns template name if found, None otherwise.
    Examples: "/morning", "/checkin", "/training", "/onboard"
    """
    message = message.strip().lower()
    
    # Simple command patterns
    questionnaire_commands = {
        "/morning": "morning_checkin",
        "/checkin": "daily_checkin", 
        "/training": "post_training",
        "/workout": "post_training",
        "/sleep": "sleep_review",
        "/mood": "mood_checkin",
        "/onboard": "onboarding",
    }
    
    return questionnaire_commands.get(message)