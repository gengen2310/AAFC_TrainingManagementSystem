#!/usr/bin/env python3
"""Management CLI: seed / reset / run."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    args = sys.argv[1:]
    if "--seed" in args or "--reset" in args:
        from app.seeds.seed_all import seed_all
        seed_all()
        return
    if "--init-db" in args:
        from app.database import init_db
        init_db(); print("DB initialised."); return
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    reload = "--reload" in args
    # Watch only the application package. Watching the whole backend folder
    # includes .venv, and file activity there restarted the server in a loop
    # (the setup guide used to warn Mac users off --reload because of it).
    here = os.path.dirname(os.path.abspath(__file__))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=reload,
                reload_dirs=[os.path.join(here, "app")] if reload else None)


if __name__ == "__main__":
    main()
