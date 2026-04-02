"""
Questionnaire conversation service.

Handles running structured questionnaires as natural conversations,
tracking progress through questions, parsing answers, and storing results.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from ..schemas import (
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
        
        # Create session
        session = self.repo.create_questionnaire_session(
            QuestionnaireSessionCreate(
                user_id=user_id,
                template_id=template_id,
                conversation_id=conversation_id,
            )
        )
        
        # Get first question
        first_question = template.questions[0]
        question_text = self._format_question(first_question, template, 1, len(template.questions))
        
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
        
        if session.current_question_index >= len(template.questions):
            return None, True  # Already complete
        
        current_question = template.questions[session.current_question_index]
        
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
        
        # Move to next question
        next_index = session.current_question_index + 1
        is_complete = next_index >= len(template.questions)
        
        # Update session
        self.repo.update_questionnaire_session(
            session.id,
            session.user_id,
            current_question_index=next_index,
            answers=updated_answers,
            raw_responses=updated_responses,
            status="completed" if is_complete else "in_progress",
        )
        
        if is_complete:
            # Store structured data based on answers
            self._store_questionnaire_results(session, template, updated_answers)
            return self._generate_completion_message(template, updated_answers), True
        else:
            # Ask next question
            next_question = template.questions[next_index]
            question_text = self._format_question(
                next_question, template, next_index + 1, len(template.questions)
            )
            return question_text, False
    
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
        answers: dict
    ) -> None:
        """Store questionnaire results as appropriate structured data."""
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
                session.user_id, source.id, now, answers, template.questions
            )
        
        if "activity" in template.target_objects:
            self._create_activity_from_answers(
                session.user_id, source.id, now, answers, template.questions
            )
        
        if "metric_observation" in template.target_objects:
            self._create_metrics_from_answers(
                session.user_id, source.id, now, answers, template.questions
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
        for question_id, answer in answers.items():
            if isinstance(answer, (int, float)):
                # Create a metric for numeric answers
                self.repo.create_metric_observation(
                    MetricObservationCreate(
                        user_id=user_id,
                        source_document_id=source_id,
                        effective_at=now,
                        metric_type=question_id,
                        value=str(answer),
                        unit="",
                    )
                )
    
    def _generate_completion_message(self, template: QuestionnaireTemplate, answers: dict) -> str:
        """Generate a completion message summarizing the questionnaire."""
        summary_parts = []
        
        for question in template.questions:
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
    Examples: "/morning", "/checkin", "/training"
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
    }
    
    return questionnaire_commands.get(message)