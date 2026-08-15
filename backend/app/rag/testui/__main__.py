from __future__ import annotations

import uvicorn


def main() -> None:
    uvicorn.run("app.rag.testui.app:app", host="127.0.0.1", port=8010, reload=False)


if __name__ == "__main__":
    main()
