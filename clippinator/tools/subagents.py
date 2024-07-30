from __future__ import annotations

import typing

from beartype import beartype as typed

from clippinator.project import Project
from ..minions import extract_agent_name
from .terminal import end_sessions, get_pids
from .tool import SimpleTool
from .utils import get_input_from_editor, trim_extra, yes_no_prompt

if typing.TYPE_CHECKING:
    from clippinator.minions.executioner import Executioner, SpecializedExecutioner


class Subagent(SimpleTool):
    name = "Subagent"
    description = (
        "call subagents to perform tasks. Use 'Action: Subagent' for the general agent "
        "or 'Action: Subagent @AgentName', for example 'Action: Subagent @Writer'"
    )

    @typed
    def __init__(
        self,
        project: Project,
        agents: dict[str, SpecializedExecutioner],
        default: Executioner,
    ):
        self.agents = agents
        self.default = default
        self.project = project
        super().__init__()

    @typed
    def func(self, args: str) -> str:
        pids = get_pids()
        task, agent = extract_agent_name(args)
        if agent.strip() and agent not in self.agents:
            return f"Unknown agent '{agent}', please choose from: {', '.join(self.agents.keys())}"
        runner = self.agents.get(agent, self.default)
        prev_memories = self.project.memories.copy()
        print(
            f'Running task "{task}" with agent "{getattr(runner, "name", "default")}"'
        )
        try:
            result = runner.execute(task, self.project)
        except Exception as e:
            result = f"Error running agent, retry with another task or agent: {e}"
        result = trim_extra(result, 1200)
        new_memories = [
            mem for mem in self.project.memories if mem not in prev_memories
        ]
        if agent == "Architect":
            if yes_no_prompt("Do you want to edit the project architecture?"):
                self.project.architecture = get_input_from_editor(
                    self.project.architecture
                )
            result = "Architecture declared: " + self.project.architecture + "\n"
        result = (
            f"Completed, result: {result}\n\n"
            f"Current project state:\n{self.project.get_project_summary()}\n"
        )
        if new_memories:
            result += "New memories:\n  - " + "\n  - ".join(new_memories)
        end_sessions(pids)
        return result
