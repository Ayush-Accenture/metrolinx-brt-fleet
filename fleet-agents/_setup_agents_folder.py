"""One-time script to restructure into agents/super_agents + agents/sub_agents."""
import os, shutil

base = os.path.dirname(os.path.abspath(__file__))
sa = os.path.join(base, "agents", "super_agents")
sb = os.path.join(base, "agents", "sub_agents")

os.makedirs(sa, exist_ok=True)
os.makedirs(sb, exist_ok=True)

open(os.path.join(base, "agents", "__init__.py"), "w").close()
open(os.path.join(sa, "__init__.py"), "w").close()
open(os.path.join(sb, "__init__.py"), "w").close()

shutil.copy(os.path.join(base, "orchestrator.py"), os.path.join(sa, "orchestrator.py"))
for f in ["base_agent.py", "parser_narrator.py", "reconciliation_narrator.py", "execution_narrator.py"]:
    shutil.copy(os.path.join(base, "sub_agents", f), os.path.join(sb, f))

print("Created:")
for r, _, files in os.walk(os.path.join(base, "agents")):
    for f in files:
        print(" ", os.path.join(r, f).replace(base + os.sep, ""))
