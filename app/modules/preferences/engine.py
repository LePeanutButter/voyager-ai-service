"""Rule-based adaptive questionnaire engine.

Purpose:
    Branch follow-up questions from the primary travel style (adventure, cultural,
    relax) per product rules.

Responsibilities:
    Merge step answers, derive the primary category, and return the next question
    set or completion.

Dependencies:
    Pydantic models ``AnswerItem``, ``QuestionnaireQuestion``, ``QuestionOption``.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from app.modules.preferences.schemas import AnswerItem, QuestionnaireQuestion, QuestionOption


def _q(
    qid: str,
    prompt: str,
    options: List[Tuple[str, str]],
    question_type: str = "single_choice",
) -> QuestionnaireQuestion:
    """Builds a ``QuestionnaireQuestion`` from id/prompt and (id, label) pairs.

    Args:
        qid: Stable question identifier.
        prompt: Text shown to the user.
        options: List of (option_id, display_label).
        question_type: ``single_choice`` or ``multi_choice``.

    Returns:
        Configured ``QuestionnaireQuestion``.
    """
    return QuestionnaireQuestion(
        id=qid,
        prompt=prompt,
        question_type=question_type,
        options=[QuestionOption(id=i, label=lbl) for i, lbl in options],
    )


PRIMARY = _q(
    "primary_travel_style",
    "¿Qué tipo de viaje te atrae más en esta etapa?",
    [
        ("adventure", "Aventura (naturaleza, adrenalina, exploración)"),
        ("cultural", "Cultural (historia, arte, encuentros locales)"),
        ("relax", "Relax (descanso, bienestar, ritmo calmado)"),
    ],
)

BUDGET_LABEL_ECONOMY = "Economía / ajustado"
BUDGET_LABEL_COMFORT = "Cómodo"


class AdaptiveQuestionnaireEngine:
    """Selects the next question batch from accumulated answers (stateless logic)."""

    def merge_answers(
        self,
        existing: Dict[str, List[str]],
        incoming: List[AnswerItem],
    ) -> Dict[str, List[str]]:
        """Merges new ``AnswerItem`` selections into the answer map (last write wins per question).

        Args:
            existing: Prior answers by question id.
            incoming: New selections from the current step.

        Returns:
            Updated answer dictionary.
        """
        merged = dict(existing)
        for item in incoming:
            if item.question_id and item.selected_option_ids:
                merged[item.question_id] = list(item.selected_option_ids)
        return merged

    def derive_primary_category(self, answers: Dict[str, List[str]]) -> Optional[str]:
        """Returns adventure/cultural/relax if the primary style question is answered.

        Args:
            answers: Current answer map.

        Returns:
            Primary category string or ``None`` if not yet chosen.
        """
        style = (answers.get("primary_travel_style") or [None])[0]
        if style in ("adventure", "cultural", "relax"):
            return style
        return None

    def next_questions(
        self,
        answers: Dict[str, List[str]],
    ) -> Tuple[List[QuestionnaireQuestion], bool, Optional[str]]:
        """Computes the next questions and completion state.

        Args:
            answers: All answers collected so far.

        Returns:
            Tuple of (next questions, whether flow is complete, derived primary category).
        """
        primary = self.derive_primary_category(answers)
        if primary is None:
            return [PRIMARY], False, None

        if primary == "adventure":
            if "adventure_intensity" not in answers:
                return (
                    [
                        _q(
                            "adventure_intensity",
                            "¿Qué intensidad de aventura buscas?",
                            [
                                ("soft", "Suave (senderismo ligero, scenic routes)"),
                                ("moderate", "Moderada (trekking, deportes al aire libre)"),
                                ("high", "Alta (multi-actividad, desafíos físicos)"),
                            ],
                        ),
                        _q(
                            "nature_focus",
                            "¿Cuánto peso quieres dar a naturaleza vs. ciudades?",
                            [
                                ("mostly_nature", "Mayormente naturaleza"),
                                ("balanced_nc", "Equilibrado"),
                                ("mostly_urban", "Más ciudades con escapadas cortas"),
                            ],
                        ),
                    ],
                    False,
                    primary,
                )
            if "trip_budget_band" not in answers:
                return (
                    [
                        _q(
                            "trip_budget_band",
                            "Para calibrar sugerencias, ¿cómo describirías tu presupuesto típico de viaje?",
                            [
                                ("budget", BUDGET_LABEL_ECONOMY),
                                ("mid", "Intermedio"),
                                ("comfort", BUDGET_LABEL_COMFORT),
                                ("luxury", "Premium"),
                            ],
                        ),
                    ],
                    False,
                    primary,
                )
            return [], True, primary

        if primary == "cultural":
            if "culture_depth" not in answers:
                return (
                    [
                        _q(
                            "culture_depth",
                            "¿Qué te define más en lo cultural?",
                            [
                                ("museums", "Museos, sitios históricos, guías expertos"),
                                ("local_life", "Vida local, barrios, gastronomía auténtica"),
                                ("mixed_culture", "Mezcla equilibrada de ambos"),
                            ],
                        ),
                        _q(
                            "cultural_pace",
                            "¿Qué ritmo prefieres al visitar?",
                            [
                                ("packed", "Itinerario completo (muchas paradas)"),
                                ("balanced_pace", "Equilibrado"),
                                ("slow", "Lento, tiempo para absorber"),
                            ],
                        ),
                    ],
                    False,
                    primary,
                )
            if "trip_budget_band" not in answers:
                return (
                    [
                        _q(
                            "trip_budget_band",
                            "¿Cómo describirías tu presupuesto típico de viaje?",
                            [
                                ("budget", BUDGET_LABEL_ECONOMY),
                                ("mid", "Intermedio"),
                                ("comfort", BUDGET_LABEL_COMFORT),
                                ("luxury", "Premium"),
                            ],
                        ),
                    ],
                    False,
                    primary,
                )
            return [], True, primary

        # relax
        if "relax_setting" not in answers:
            return (
                [
                    _q(
                        "relax_setting",
                        "¿Dónde te resulta más fácil desconectar?",
                        [
                            ("beach", "Costa / playa"),
                            ("mountains", "Montaña / naturaleza tranquila"),
                            ("spa_city", "Spa / hotel boutique en ciudad"),
                        ],
                    ),
                    _q(
                        "social_energy",
                        "Durante el relax, ¿prefieres…?",
                        [
                            ("quiet", "Silencio y poca gente"),
                            ("social_light", "Ambiente animado pero sin prisas"),
                            ("social", "Quiero socializar con otros viajeros"),
                        ],
                    ),
                ],
                False,
                primary,
            )
        if "trip_budget_band" not in answers:
            return (
                [
                    _q(
                        "trip_budget_band",
                        "¿Cómo describirías tu presupuesto típico de viaje?",
                        [
                            ("budget", BUDGET_LABEL_ECONOMY),
                            ("mid", "Intermedio"),
                            ("comfort", BUDGET_LABEL_COMFORT),
                            ("luxury", "Premium"),
                        ],
                    ),
                ],
                False,
                primary,
            )
        return [], True, primary
