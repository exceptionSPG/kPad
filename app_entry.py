"""PyInstaller entry point. Uses absolute imports so the frozen app has proper
package context (server/main.py uses relative imports)."""

from server.main import main

if __name__ == "__main__":
    main()
