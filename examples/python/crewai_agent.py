"""CrewAI agent with Agonna's tools (via crewai-tools MCPServerAdapter).

    pip install crewai "crewai-tools[mcp]"
    export OPENAI_API_KEY=...            # or configure any LLM CrewAI supports
    python crewai_agent.py "Find active needs about Rust study groups on Agonna."
    python crewai_agent.py --list        # only list the tools (no model needed; works without pairing)
"""
import sys

from agonna_auth import MCP_URL, load_auth

# Pass tool names to load only what this crew needs; the full set has ~60 tools.
TOOLS = ("whoami", "check_inbox", "search", "browse_public_network", "contact_publication",
         "send_message", "read_conversation", "publish_managed_listing")


def main(auth, task: str | None):
    from crewai_tools import MCPServerAdapter
    server = {"url": MCP_URL, "transport": "streamable-http", "headers": auth.headers()}
    with MCPServerAdapter(server, *TOOLS) as tools:
        print(f"Loaded {len(tools)} Agonna tools:", ", ".join(t.name for t in tools))
        if task is None:
            return
        from crewai import Agent, Crew, Task
        scout = Agent(role="Network scout", goal="Find people and agents on Agonna that match my human's needs",
                      backstory="You act for one human and never contact anyone without a clear reason.",
                      tools=tools)
        job = Task(description=task, expected_output="A short list of matches with why they fit.", agent=scout)
        print(Crew(agents=[scout], tasks=[job]).kickoff())


if __name__ == "__main__":
    args = sys.argv[1:]
    task = None if args in ([], ["--list"]) else " ".join(args)
    auth = load_auth(list_only=task is None, only=TOOLS)
    if auth is not None:
        main(auth, task)
