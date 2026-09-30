"""Live end-to-end check of the interior pipeline against the real vendor APIs.

Runs the FastAPI app in-process (TestClient) against a throwaway database and data
folder, so nothing touches backend/autoscape.db, and walks: create an interior project
-> generate renders -> dimension suggestions -> build sheet. Spends a few cents.

    uv run python scripts/e2e_interior.py <photo.jpg> [--image-model gpt-image-2.5-flare]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("photo")
    parser.add_argument("--image-provider", default="gpt_image")
    parser.add_argument("--image-model", default=None)
    parser.add_argument("--materials-llm", default="gpt5")
    parser.add_argument("--skip-renders", action="store_true")
    args = parser.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="autoscape-e2e-"))
    os.environ["DATABASE_URL"] = f"sqlite:///{(tmp / 'e2e.db').as_posix()}"
    os.environ["AUTOSCAPE_DATA_DIR"] = str(tmp / "data")
    os.environ["AUTOSCAPE_STARTUP_MODEL_CHECK"] = "0"

    from fastapi.testclient import TestClient

    from app import bootstrap  # noqa: F401  (loads secrets/ keys)
    from app.main import app

    photo = Path(args.photo)
    started = time.time()

    def step(name: str) -> None:
        print(f"[{time.time() - started:6.1f}s] {name}", flush=True)

    with TestClient(app) as client:
        step("GET /api/spaces")
        spaces = client.get("/api/spaces").json()["spaces"]
        interior = next(s for s in spaces if s["id"] == "interior")
        print("   interior categories:", ", ".join(interior["feature_categories"][:5]), "...")

        step("POST /api/projects (interior kitchen)")
        with photo.open("rb") as fh:
            resp = client.post(
                "/api/projects",
                data={
                    "address": "E2E · 12 Elm St · Kitchen",
                    "space_type": "interior",
                    "room_type": "Kitchen",
                    "space_details": json.dumps(
                        {"room_length_ft": 14, "room_width_ft": 12, "ceiling_height_ft": 9}
                    ),
                },
                files={"site_photo": (photo.name, fh, "image/jpeg")},
            )
        assert resp.status_code == 201, resp.text
        project_id = resp.json()["id"]
        detail = client.get(f"/api/projects/{project_id}").json()
        print("   space_label:", detail["space_label"], "| details:", detail["space_details"])
        assert detail["space_type"] == "interior" and detail["space_label"] == "Kitchen"

        if args.skip_renders:
            step("done (renders skipped)")
            return 0

        step(f"POST design request via {args.image_provider} {args.image_model or '(default)'}")
        body = {
            "image_provider": args.image_provider,
            "image_model": args.image_model,
            "feature_categories": ["Cabinets", "Countertops", "Flooring"],
            "style": "Scandinavian",
            "quality_tier": "Mid-range",
            "composed_prompt": (
                "Redesign this kitchen as a mid-range scandinavian interior featuring "
                "Cabinets, Countertops, Flooring. Keep the walls, windows, doors, and camera "
                "angle. Show a photorealistic, buildable finished room with realistic materials, "
                "coherent lighting, correctly scaled furniture, and no labels or text."
            ),
            "parent_render_id": None,
        }
        resp = client.post(f"/api/projects/{project_id}/design-requests", json=body)
        assert resp.status_code == 201, resp.text
        dr = resp.json()
        render_id = dr["renders"][0]["id"]
        print(f"   {len(dr['renders'])} renders via {dr['image_model']}; first render id {render_id}")

        step("POST dimension-defaults")
        resp = client.post(
            f"/api/renders/{render_id}/dimension-defaults",
            json={"materials_llm": args.materials_llm},
        )
        assert resp.status_code == 200, resp.text
        dims = resp.json()
        print("   dims:", dims)
        for key in ("cabinet_linear_ft", "countertop_sqft", "floor_sqft"):
            assert key in dims, f"missing {key}"

        step("PATCH choose + POST build-sheet")
        client.patch(f"/api/renders/{render_id}/choose")
        resp = client.post(
            f"/api/renders/{render_id}/build-sheet",
            json={"materials_llm": args.materials_llm, "dimensions": dims},
        )
        assert resp.status_code == 201, resp.text
        sheet = resp.json()
        vendors = sorted({item["vendor"] for item in sheet["material_items"]})
        print(f"   {len(sheet['material_items'])} items | steps {len(sheet['build_steps'])} | "
              f"total {sheet['total_cost_range']} | vendors {vendors}")
        for item in sheet["material_items"][:4]:
            print("    -", item["name"], "|", item["vendor"], "|", item["product_url"][:60])
        domains = {item["product_url"].split("/")[2].removeprefix("www.") for item in sheet["material_items"]}
        interior_domains = {r["domain"] for r in interior["retailers"]}
        assert domains <= interior_domains, f"unexpected domains {domains - interior_domains}"
        step("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
