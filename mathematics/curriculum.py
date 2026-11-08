"""GDD 18: the mastery categories, the four difficulty bands and how every question topic in the
game (templates, the older generators and the Trials question engine) maps onto them."""

# The categories a learner's mastery is tracked in (GDD 9.3 / 18).
MASTERY_TOPICS = ("addition", "subtraction", "multiplication", "division", "fractions", "ratios",
                  "integers", "algebra", "geometry", "sequences")

LABELS = {"addition": "Addition", "subtraction": "Subtraction", "multiplication": "Multiplication",
          "division": "Division", "fractions": "Fractions", "ratios": "Ratios", "integers": "Integers",
          "algebra": "Algebra", "geometry": "Geometry", "sequences": "Sequences", "reasoning": "Reasoning"}

SHORT = {"addition": "ADD", "subtraction": "SUB", "multiplication": "MUL", "division": "DIV",
         "fractions": "FRAC", "ratios": "RATIO", "integers": "INT", "algebra": "ALG",
         "geometry": "GEOM", "sequences": "SEQ", "reasoning": "LOGIC"}

# Number Forest's own topics (GDD 2.2, World 1).
REGION_TOPICS = {"number_forest": ("addition", "subtraction", "multiplication", "division", "fractions"),
                 "crystal_realm": MASTERY_TOPICS}

# GDD 14, Agent 3: four difficulty bands.
DIFFICULTIES = ("foundation", "intermediate", "advanced", "mastery")
DIFFICULTY_LABELS = {"foundation": "Foundation", "intermediate": "Intermediate", "advanced": "Advanced",
                     "mastery": "Mastery"}
# Older code (arena, trials, question_history.difficulty) used three labels.
LEGACY_DIFFICULTY = {"easy": "foundation", "intermediate": "intermediate", "advanced": "advanced"}

# Everything else a question can be tagged with -> its mastery category.
ALIASES = {
    "percentages": "ratios", "proportion": "ratios", "proportions": "ratios", "ratio": "ratios",
    "negative_numbers": "integers", "integer_arithmetic": "integers",
    "equations": "algebra", "expressions": "algebra", "variables": "algebra", "unknowns": "algebra",
    "angles": "geometry", "shapes": "geometry", "area": "geometry", "perimeter": "geometry", "volume": "geometry",
    "patterns": "sequences", "exponents": "sequences", "time": "sequences", "time_money": "sequences",
    "large_numbers": "addition", "place_value": "addition",
    "mixed_operations": "reasoning", "logic": "reasoning", "combined": "reasoning",
}


def mastery_topic(topic):
    """The mastery category for any topic name ('equations' -> 'algebra')."""
    topic = str(topic or "").lower().replace(" ", "_")
    if topic in MASTERY_TOPICS:
        return topic
    return ALIASES.get(topic, "reasoning")


def label(topic):
    return LABELS.get(topic, str(topic).replace("_", " ").title())


def normalise_difficulty(difficulty):
    difficulty = str(difficulty or "foundation").lower()
    if difficulty in DIFFICULTIES:
        return difficulty
    return LEGACY_DIFFICULTY.get(difficulty, "foundation")


def legacy_difficulty(difficulty):
    """'mastery' -> 'advanced' etc., for screens that only know three levels."""
    return {"foundation": "easy", "intermediate": "intermediate", "advanced": "advanced",
            "mastery": "advanced"}[normalise_difficulty(difficulty)]
