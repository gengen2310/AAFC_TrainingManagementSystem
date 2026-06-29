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
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload="--reload" in args)


if __name__ == "__main__":
    main()
