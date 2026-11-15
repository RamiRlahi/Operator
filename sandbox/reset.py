"""
Command-line utility to reset and seed the sandbox environment.
Usage:
    python sandbox/reset.py
"""

import sys
from pathlib import Path

# Add project root to path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from sandbox.environment import SandboxEnvironment


def main():
    print("[Sandbox] Resetting sandbox database to baseline state...")
    env = SandboxEnvironment()
    env.reset()
    print("[Sandbox] Done! Database re-initialized with:")
    conn = env.get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM tickets")
    tickets_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM customers")
    cust_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM knowledge_base")
    kb_count = c.fetchone()[0]
    print(f"  - {tickets_count} tickets")
    print(f"  - {cust_count} customers")
    print(f"  - {kb_count} knowledge base articles")
    print(f"  - 0 executed actions (pristine state)")
    env.close()


if __name__ == "__main__":
    main()
