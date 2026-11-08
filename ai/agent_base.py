"""Shared shape for the five agents: a name, an action, and a validated result."""


class Agent:
    name = "agent"

    def __repr__(self):
        return f"<{self.__class__.__name__}>"
