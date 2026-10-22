#!/usr/bin/env python3
"""Build optimized Canvas Lottie assets for course introduction pages.

The supplied SVGs stay in ``source/`` as the source of truth. This build step
rasterizes each pose once at the hero's display density, avoiding expensive SVG
decoding while the browser crossfades the two poses. The generated Lottie file
owns all timeline motion, including breathing, blinks, and smile accents.
"""

from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path

from PIL import Image
import resvg_py


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOTTIE_ROOT = PROJECT_ROOT / "landing" / "course-mascot-lottie"
SOURCE_ROOT = LOTTIE_ROOT / "source"
ASSETS_ROOT = LOTTIE_ROOT / "assets"
OUTPUT = LOTTIE_ROOT / "zito-course-mascot.json"

FRAME_RATE = 30
FRAME_COUNT = 300
COMPOSITION_WIDTH = 340
COMPOSITION_HEIGHT = 420
ASSET_WIDTH = 680
ASSET_HEIGHT = 840
POSE_RENDER_HEIGHT = 806


def static(value: list[float] | float) -> dict:
    return {"a": 0, "k": value}


def animated(points: list[tuple[int, list[float]]]) -> dict:
    frames: list[dict] = []
    for index, (frame, value) in enumerate(points):
        keyframe: dict = {"t": frame, "s": value}
        if index + 1 < len(points):
            keyframe["e"] = points[index + 1][1]
            keyframe["i"] = {"x": [0.38], "y": [1]}
            keyframe["o"] = {"x": [0.62], "y": [0]}
        frames.append(keyframe)
    return {"a": 1, "k": frames}


def render_pose(source_name: str) -> None:
    """Render a source SVG into a stable transparent canvas for Canvas Lottie."""
    source = SOURCE_ROOT / source_name
    if not source.exists():
        raise RuntimeError(f"Missing source asset: {source}")

    rendered = Image.open(
        BytesIO(
            resvg_py.svg_to_bytes(
                svg_path=str(source),
                height=POSE_RENDER_HEIGHT,
                image_rendering="optimize_quality",
            )
        )
    ).convert("RGBA")
    canvas = Image.new("RGBA", (ASSET_WIDTH, ASSET_HEIGHT), (0, 0, 0, 0))
    offset = ((ASSET_WIDTH - rendered.width) // 2, (ASSET_HEIGHT - rendered.height) // 2)
    canvas.alpha_composite(rendered, offset)
    output = ASSETS_ROOT / f"{Path(source_name).stem}.png"
    canvas.save(output, optimize=True)


def write_expression_asset(name: str, markup: str) -> None:
    """Create a transparent face overlay used by a timed Lottie image layer."""
    (ASSETS_ROOT / name).write_text(
        "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 680 840\">"
        f"{markup}</svg>\n",
        encoding="utf-8",
    )


def build_expression_assets() -> None:
    # Coordinates are measured in the 680x840 generated pose canvases. Each
    # overlay has the same anchor and transform as its matching pose, so it
    # remains attached to the face during both breathing and the handoff.
    write_expression_asset(
        "zito-state-a-eyes-open.svg",
        "<ellipse cx=\"278\" cy=\"397\" rx=\"46\" ry=\"34\" fill=\"#f7e4f3\"/>"
        "<ellipse cx=\"440\" cy=\"375\" rx=\"46\" ry=\"34\" fill=\"#f7e4f3\"/>"
        "<ellipse cx=\"278\" cy=\"397\" rx=\"16\" ry=\"23\" fill=\"#1a193b\"/>"
        "<ellipse cx=\"440\" cy=\"375\" rx=\"16\" ry=\"23\" fill=\"#1a193b\"/>"
        "<circle cx=\"272\" cy=\"389\" r=\"4\" fill=\"#fff\"/>"
        "<circle cx=\"434\" cy=\"367\" r=\"4\" fill=\"#fff\"/>",
    )
    write_expression_asset(
        "zito-state-a-mouth-open.svg",
        "<ellipse cx=\"366\" cy=\"444\" rx=\"56\" ry=\"39\" fill=\"#f7e4f3\"/>"
        "<path d=\"M332 437 Q366 458 400 437 Q396 476 366 480 Q336 476 332 437Z\" fill=\"#1a193b\"/>"
        "<path d=\"M344 466 Q366 454 388 466 Q383 475 366 477 Q349 475 344 466Z\" fill=\"#cf83a9\"/>",
    )
    write_expression_asset(
        "zito-state-b-eyes-open.svg",
        "<ellipse cx=\"214\" cy=\"383\" rx=\"46\" ry=\"34\" fill=\"#f7e4f3\"/>"
        "<ellipse cx=\"378\" cy=\"365\" rx=\"46\" ry=\"34\" fill=\"#f7e4f3\"/>"
        "<ellipse cx=\"214\" cy=\"383\" rx=\"16\" ry=\"23\" fill=\"#1a193b\"/>"
        "<ellipse cx=\"378\" cy=\"365\" rx=\"16\" ry=\"23\" fill=\"#1a193b\"/>"
        "<circle cx=\"208\" cy=\"375\" r=\"4\" fill=\"#fff\"/>"
        "<circle cx=\"372\" cy=\"357\" r=\"4\" fill=\"#fff\"/>",
    )
    write_expression_asset(
        "zito-state-b-mouth-open.svg",
        "<ellipse cx=\"301\" cy=\"437\" rx=\"57\" ry=\"39\" fill=\"#f7e4f3\"/>"
        "<path d=\"M267 430 Q301 451 335 430 Q331 470 301 474 Q271 470 267 430Z\" fill=\"#1a193b\"/>"
        "<path d=\"M279 460 Q301 448 323 460 Q318 469 301 471 Q284 469 279 460Z\" fill=\"#cf83a9\"/>",
    )


def build_transition_glow() -> None:
    """Create a small visual bridge so two full poses never ghost together."""
    glow = Image.new("RGBA", (ASSET_WIDTH, ASSET_HEIGHT), (0, 0, 0, 0))
    pixels = glow.load()
    center_x = ASSET_WIDTH / 2
    center_y = ASSET_HEIGHT / 2
    radius = min(ASSET_WIDTH, ASSET_HEIGHT) * 0.31
    for y in range(ASSET_HEIGHT):
        for x in range(ASSET_WIDTH):
            distance = ((x - center_x) ** 2 + (y - center_y) ** 2) ** 0.5
            if distance >= radius:
                continue
            strength = (1 - distance / radius) ** 2
            pixels[x, y] = (173, 132, 231, round(125 * strength))
    glow.save(ASSETS_ROOT / "zito-transition-glow.png", optimize=True)


def asset(reference: str, filename: str) -> dict:
    return {
        "id": reference,
        "w": ASSET_WIDTH,
        "h": ASSET_HEIGHT,
        "u": "assets/",
        "p": filename,
        "e": 0,
    }


def image_layer(
    *,
    index: int,
    name: str,
    reference: str,
    opacity: list[tuple[int, list[float]]],
    position: list[tuple[int, list[float]]],
    scale: list[tuple[int, list[float]]],
    rotation: list[tuple[int, list[float]]],
) -> dict:
    return {
        "ddd": 0,
        "ind": index,
        "ty": 2,
        "nm": name,
        "refId": reference,
        "sr": 1,
        "ks": {
            "o": animated(opacity),
            "r": animated(rotation),
            "p": animated(position),
            "a": static([ASSET_WIDTH / 2, ASSET_HEIGHT / 2, 0]),
            "s": animated(scale),
        },
        "ao": 0,
        "ip": 0,
        "op": FRAME_COUNT,
        "st": 0,
        "bm": 0,
    }


def build_composition() -> dict:
    center_x = COMPOSITION_WIDTH / 2
    center_y = COMPOSITION_HEIGHT / 2

    # The handoff deliberately has no full-pose overlap. Crossfading two
    # different devices made the hands look duplicated, so each pose now exits
    # behind a tiny glow and the next one settles in afterward.
    pose_a_position = [
        (0, [center_x, center_y + 3, 0]),
        (24, [center_x + 1, center_y - 3, 0]),
        (52, [center_x - 1, center_y + 3, 0]),
        (76, [center_x + 1, center_y - 1, 0]),
        (84, [center_x, center_y, 0]),
        (92, [center_x - 2, center_y - 5, 0]),
        (100, [center_x - 4, center_y - 13, 0]),
        (102, [center_x - 5, center_y - 17, 0]),
        (244, [center_x + 5, center_y - 17, 0]),
        (265, [center_x + 5, center_y - 17, 0]),
        (273, [center_x + 2, center_y - 5, 0]),
        (281, [center_x, center_y + 1, 0]),
        (299, [center_x, center_y + 3, 0]),
    ]
    pose_a_scale = [
        (0, [48.4, 48.4, 100]),
        (24, [49.6, 49.6, 100]),
        (52, [48.4, 48.4, 100]),
        (76, [49.35, 49.35, 100]),
        (84, [49.2, 49.2, 100]),
        (92, [48.2, 48.2, 100]),
        (100, [45.1, 45.1, 100]),
        (102, [44.0, 44.0, 100]),
        (244, [44.0, 44.0, 100]),
        (265, [44.0, 44.0, 100]),
        (273, [49.6, 49.6, 100]),
        (281, [50.4, 50.4, 100]),
        (299, [48.4, 48.4, 100]),
    ]
    pose_a_rotation = [
        (0, [-0.42]),
        (24, [0.28]),
        (52, [-0.35]),
        (76, [0.16]),
        (84, [0.08]),
        (92, [-0.25]),
        (100, [-0.62]),
        (102, [-0.78]),
        (244, [0.78]),
        (265, [0.78]),
        (273, [0.18]),
        (281, [-0.12]),
        (299, [-0.42]),
    ]
    pose_a_opacity = [
        (0, [100]),
        (84, [100]),
        (92, [72]),
        (102, [0]),
        (244, [0]),
        (265, [0]),
        (273, [72]),
        (281, [100]),
        (299, [100]),
    ]

    pose_b_position = [
        (0, [center_x + 5, center_y - 17, 0]),
        (105, [center_x + 5, center_y - 17, 0]),
        (113, [center_x + 2, center_y - 6, 0]),
        (121, [center_x, center_y - 2, 0]),
        (146, [center_x + 1, center_y - 8, 0]),
        (172, [center_x - 1, center_y - 2, 0]),
        (202, [center_x + 1, center_y - 7, 0]),
        (228, [center_x - 1, center_y - 2, 0]),
        (244, [center_x, center_y - 4, 0]),
        (252, [center_x + 2, center_y - 9, 0]),
        (260, [center_x + 5, center_y - 17, 0]),
        (299, [center_x + 5, center_y - 17, 0]),
    ]
    pose_b_scale = [
        (0, [44.0, 44.0, 100]),
        (105, [44.0, 44.0, 100]),
        (113, [49.7, 49.7, 100]),
        (121, [50.4, 50.4, 100]),
        (146, [48.85, 48.85, 100]),
        (172, [49.85, 49.85, 100]),
        (202, [48.85, 48.85, 100]),
        (228, [49.75, 49.75, 100]),
        (244, [49.3, 49.3, 100]),
        (252, [48.4, 48.4, 100]),
        (260, [44.0, 44.0, 100]),
        (299, [44.0, 44.0, 100]),
    ]
    pose_b_rotation = [
        (0, [0.78]),
        (105, [0.78]),
        (113, [0.18]),
        (121, [-0.12]),
        (146, [0.26]),
        (172, [-0.22]),
        (202, [0.22]),
        (228, [-0.18]),
        (244, [0.08]),
        (252, [0.38]),
        (260, [0.78]),
        (299, [0.78]),
    ]
    pose_b_opacity = [
        (0, [0]),
        (105, [0]),
        (113, [72]),
        (121, [100]),
        (244, [100]),
        (252, [72]),
        (260, [0]),
        (299, [0]),
    ]

    common_a = {
        "position": pose_a_position,
        "scale": pose_a_scale,
        "rotation": pose_a_rotation,
    }
    common_b = {
        "position": pose_b_position,
        "scale": pose_b_scale,
        "rotation": pose_b_rotation,
    }

    state_a = image_layer(
        index=1,
        name="Phone pose - breathing and handoff",
        reference="zito-state-a",
        opacity=pose_a_opacity,
        **common_a,
    )
    state_b = image_layer(
        index=2,
        name="Laptop pose - breathing and handoff",
        reference="zito-state-b",
        opacity=pose_b_opacity,
        **common_b,
    )

    # The supplied illustrations begin with smiling closed eyes. Briefly
    # revealing open eyes and a warmer mouth makes the automatic loop legible
    # even when the user does not watch a whole handoff.
    eyes_a = image_layer(
        index=3,
        name="Phone pose - open eyes",
        reference="zito-state-a-eyes-open",
        opacity=[
            (0, [0]), (10, [0]), (15, [100]), (38, [100]), (44, [0]),
            (58, [0]), (63, [100]), (74, [100]), (80, [0]), (299, [0]),
        ],
        **common_a,
    )
    mouth_a = image_layer(
        index=4,
        name="Phone pose - open smile",
        reference="zito-state-a-mouth-open",
        opacity=[(0, [0]), (35, [0]), (41, [100]), (61, [100]), (69, [0]), (299, [0])],
        **common_a,
    )
    eyes_b = image_layer(
        index=5,
        name="Laptop pose - open eyes",
        reference="zito-state-b-eyes-open",
        opacity=[
            (0, [0]), (148, [0]), (153, [100]), (178, [100]), (185, [0]),
            (201, [0]), (206, [100]), (222, [100]), (230, [0]), (299, [0]),
        ],
        **common_b,
    )
    mouth_b = image_layer(
        index=6,
        name="Laptop pose - open smile",
        reference="zito-state-b-mouth-open",
        opacity=[(0, [0]), (198, [0]), (204, [100]), (226, [100]), (235, [0]), (299, [0])],
        **common_b,
    )
    transition_glow = image_layer(
        index=7,
        name="Soft glow between course mascot poses",
        reference="zito-transition-glow",
        opacity=[
            (0, [0]), (82, [0]), (90, [38]), (98, [92]), (105, [76]),
            (121, [0]), (242, [0]), (250, [38]), (258, [92]), (265, [76]),
            (281, [0]), (299, [0]),
        ],
        position=[
            (0, [center_x, center_y, 0]), (82, [center_x, center_y, 0]),
            (105, [center_x, center_y - 4, 0]), (121, [center_x, center_y - 8, 0]),
            (242, [center_x, center_y, 0]), (265, [center_x, center_y - 4, 0]),
            (281, [center_x, center_y - 8, 0]), (299, [center_x, center_y, 0]),
        ],
        scale=[
            (0, [0, 0, 100]), (82, [0, 0, 100]), (90, [54, 54, 100]),
            (98, [92, 92, 100]), (105, [116, 116, 100]), (121, [138, 138, 100]),
            (242, [0, 0, 100]), (250, [54, 54, 100]), (258, [92, 92, 100]),
            (265, [116, 116, 100]), (281, [138, 138, 100]), (299, [0, 0, 100]),
        ],
        rotation=[(0, [0]), (82, [0]), (121, [8]), (242, [0]), (281, [-8]), (299, [0])],
    )

    return {
        "v": "5.12.2",
        "fr": FRAME_RATE,
        "ip": 0,
        "op": FRAME_COUNT,
        "w": COMPOSITION_WIDTH,
        "h": COMPOSITION_HEIGHT,
        "nm": "Zito Course Overview Mascot",
        "ddd": 0,
        "assets": [
            asset("zito-state-a", "zito-state-a.png"),
            asset("zito-state-b", "zito-state-b.png"),
            asset("zito-state-a-eyes-open", "zito-state-a-eyes-open.svg"),
            asset("zito-state-a-mouth-open", "zito-state-a-mouth-open.svg"),
            asset("zito-state-b-eyes-open", "zito-state-b-eyes-open.svg"),
            asset("zito-state-b-mouth-open", "zito-state-b-mouth-open.svg"),
            asset("zito-transition-glow", "zito-transition-glow.png"),
        ],
        "markers": [
            {"tm": 0, "cm": "phone-pose-breathing-and-face", "dr": 84},
            {"tm": 84, "cm": "soft-handoff-phone-to-laptop", "dr": 37},
            {"tm": 121, "cm": "laptop-pose-breathing-and-face", "dr": 123},
            {"tm": 244, "cm": "soft-handoff-laptop-to-phone", "dr": 37},
        ],
        "layers": [transition_glow, mouth_b, eyes_b, mouth_a, eyes_a, state_b, state_a],
    }


def main() -> None:
    ASSETS_ROOT.mkdir(parents=True, exist_ok=True)
    for stale_asset in (
        "zito-state-a-eyes-blink.svg",
        "zito-state-a-mouth-smile.svg",
        "zito-state-b-eyes-blink.svg",
        "zito-state-b-mouth-smile.svg",
    ):
        (ASSETS_ROOT / stale_asset).unlink(missing_ok=True)
    render_pose("zito-state-a.svg")
    render_pose("zito-state-b.svg")
    build_expression_assets()
    build_transition_glow()
    OUTPUT.write_text(
        json.dumps(build_composition(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT.relative_to(PROJECT_ROOT)} and optimized runtime assets")


if __name__ == "__main__":
    main()
